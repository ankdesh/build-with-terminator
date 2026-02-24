#!/bin/bash
WORKLOAD=${1:-/gem5/tests/test-progs/hello/bin/riscv/linux/hello}
OUTDIR_BASE="m5out/study3"

echo "Running Study 3: Cache Sensitivity Parameter Sweep"
echo "Workload: $WORKLOAD"

# Sweep combinations: 3 Sizes * 3 Assoc * 3 MSHRs = 27 configurations
for size in "16kB" "32kB" "64kB"; do
    for assoc in 2 4 8; do
        for mshr in 4 8 16; do
            OUTDIR="${OUTDIR_BASE}_size${size}_assoc${assoc}_mshr${mshr}"
            echo "--> Running Study 3: L1D Size $size, Assoc $assoc, MSHRs $mshr (outputting to $OUTDIR)"
            docker run --rm -v $(pwd):/workspace -w /workspace gem5-riscv \
                /gem5/build/RISCV/gem5.opt -d $OUTDIR configs/study_3_cache_sensitivity.py \
                --l1d_size $size --l1d_assoc $assoc --mshrs $mshr --workload $WORKLOAD
        done
    done
done
echo "Study 3 Sweep Complete."
