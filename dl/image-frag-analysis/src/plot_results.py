import pandas as pd
import matplotlib.pyplot as plt
import os
import argparse

def plot_results(input_csv, output_dir="output/plots"):
    os.makedirs(output_dir, exist_ok=True)
    
    if not os.path.exists(input_csv):
        print(f"Error: {input_csv} not found.")
        return

    df = pd.read_csv(input_csv)
    
    # 1. Validation Accuracy vs Layers for each Class count
    plt.figure(figsize=(10, 6))
    for num_classes in df['num_classes'].unique():
        subset = df[df['num_classes'] == num_classes]
        plt.plot(subset['num_layers'], subset['val_acc'], marker='o', label=f'{num_classes} Classes')
    
    plt.title('Validation Accuracy vs Model Depth')
    plt.xlabel('Number of Layers')
    plt.ylabel('Validation Accuracy (%)')
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, 'val_accuracy_vs_layers.png'))
    plt.close()

    # 2. Validation Accuracy vs Number of Classes for each Depth
    plt.figure(figsize=(10, 6))
    for num_layers in df['num_layers'].unique():
        subset = df[df['num_layers'] == num_layers]
        plt.plot(subset['num_classes'], subset['val_acc'], marker='s', label=f'{num_layers} Layers')
    
    plt.title('Validation Accuracy vs Task Complexity')
    plt.xlabel('Number of Classes')
    plt.ylabel('Validation Accuracy (%)')
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, 'val_accuracy_vs_classes.png'))
    plt.close()

    # 3. Training vs Validation Accuracy
    plt.figure(figsize=(10, 6))
    plt.scatter(df['train_acc'], df['val_acc'], c=df['num_layers'], cmap='viridis', s=100)
    plt.colorbar(label='Num Layers')
    plt.title('Training vs Validation Accuracy Correlation')
    plt.xlabel('Training Accuracy (%)')
    plt.ylabel('Validation Accuracy (%)')
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, 'accuracy_correlation.png'))
    plt.close()

    print(f"Plots generated in {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", default="experiment_results.csv")
    args = parser.parse_args()
    
    # Ensure pandas and matplotlib are available
    try:
        plot_results(args.input_csv)
    except ImportError:
        print("Required libraries (pandas, matplotlib) not found. Please install them to generate plots.")
