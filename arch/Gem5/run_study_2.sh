#!/bin/bash
WORKLOAD=${1:-/gem5/tests/test-progs/hello/bin/riscv/linux/hello}
OUTDIR_BASE="m5out/study2"

echo "Running Study 2: Branch Predictor parameter Sweep"
echo "Workload: $WORKLOAD"

# Sweep combinations: 4 Branch Predictors * 6 Depth factors = 24 configurations
for bp in TournamentBP BiModeBP TAGE TAGE_SC_L; do
    for depth in 0 1 2 3 4 5; do
        OUTDIR="${OUTDIR_BASE}_${bp}_dep${depth}"
        echo "--> Running Study 2: BP $bp, Depth Pipeline Factor $depth (outputting to $OUTDIR)"
        docker run --rm -v $(pwd):/workspace -w /workspace gem5-riscv \
            /gem5/build/RISCV/gem5.opt -d $OUTDIR configs/study_2_branch_pred.py \
            --bp_type $bp --depth_factor $depth --workload $WORKLOAD
    done
done
echo "Study 2 Sweep Complete."
