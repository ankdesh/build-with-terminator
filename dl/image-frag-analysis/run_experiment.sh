#!/bin/bash

# Experiment configuration
CLASSES_LIST=(3 5 7 10)
LAYERS_LIST=(4 8)
EPOCHS=10
MODEL="fifty" # Options: "cnn_4l" or "fifty"
RESULTS_CSV="experiment_results.csv"

# Clear previous results
rm -f $RESULTS_CSV

echo "Starting Experiment..."
echo "Config: Classes=${CLASSES_LIST[*]}, Layers=${LAYERS_LIST[*]}, Epochs=$EPOCHS"

for num_classes in "${CLASSES_LIST[@]}"; do
    for num_layers in "${LAYERS_LIST[@]}"; do
        echo "------------------------------------------------"
        echo "Running: Classes=$num_classes, Layers=$num_layers"
        echo "------------------------------------------------"

        # 1. Clean previous run data
        rm -rf data/generated data/FFT models/ output/

        # 2. Generate Data
        python src/data_preparation.py generate \
            --source-dir ./gov1_dataset \
            --sector-size 512 \
            --num-classes $num_classes \
            --max-mb-per-class 1000

        # 3. Train Model
        python src/train.py \
            --model $MODEL \
            --data-dir ./data/generated/512 \
            --sector-size 512 \
            --batch-size 256 \
            --epochs $EPOCHS \
            --num-layers $num_layers \
            --log-csv $RESULTS_CSV

        echo "Completed: Classes=$num_classes, Layers=$num_layers"
    done
done

echo "------------------------------------------------"
echo "Experiment Complete! Generating plots..."
python src/plot_results.py --input-csv $RESULTS_CSV
echo "Plots saved to output/plots/"
