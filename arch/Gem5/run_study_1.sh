#!/bin/bash
WORKLOAD=${1:-/gem5/tests/test-progs/hello/bin/riscv/linux/hello}
OUTDIR_BASE="m5out/study1"

echo "Running Study 1: ILP Wall Parameter Sweep"
echo "Workload: $WORKLOAD"

# Sweep combinations: 5 issue widths * 5 ROB sizes = 25 configurations
for width in 2 4 8 12 16; do
    for rob in 64 128 192 256 384; do
        OUTDIR="${OUTDIR_BASE}_w${width}_r${rob}"
        echo "--> Running Study 1: Width $width, ROB $rob (outputting to $OUTDIR)"
        docker run --rm -v $(pwd):/workspace -w /workspace gem5-riscv \
            /gem5/build/RISCV/gem5.opt -d $OUTDIR configs/study_1_ilp_wall.py \
            --issue_width $width --num_rob_entries $rob --workload $WORKLOAD
    done
done
echo "Study 1 Sweep Complete."
