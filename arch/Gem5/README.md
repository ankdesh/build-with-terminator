# Gem5 Architecture Exploration Walkthrough

This walkthrough guides you through running the parameterized architecture exploration studies for RISC-V using the provided Docker environment.

## Prerequisites

- Docker installed and running.
- `gem5-riscv` Docker image built (see below).

## 1. Build Docker Image

If you haven't already, build the Docker image containing Gem5 RISC-V:

```bash
docker build -t gem5-riscv .
```

## 2. Verify Setup

Run a quick test with the default Hello World binary:

```bash
docker run --rm -v $(pwd):/workspace -w /workspace gem5-riscv \
    /gem5/build/RISCV/gem5.opt configs/study_1_ilp_wall.py \
    --issue_width 2 --num_rob_entries 40 \
    --workload /gem5/tests/test-progs/hello/bin/riscv/linux/hello
```

Check that `m5out/stats.txt` is generated in your current directory.

## 3. Running Studies

All studies require a workload binary. You can use your own RISC-V binaries or standard benchmarks (e.g., SPEC CPU).

### Study 1: ILP Wall
Sweeps Issue Width and ROB Entries.

```bash
docker run --rm -v $(pwd):/workspace -w /workspace gem5-riscv \
    /gem5/build/RISCV/gem5.opt configs/study_1_ilp_wall.py \
    --issue_width 4 \
    --num_rob_entries 128 \
    --workload /path/to/your/workload
```

### Study 2: Branch Predictor
Sweeps Branch Predictor types and Pipeline Depth.

```bash
docker run --rm -v $(pwd):/workspace -w /workspace gem5-riscv \
    /gem5/build/RISCV/gem5.opt configs/study_2_branch_pred.py \
    --bp_type TAGE \
    --depth_factor 2 \
    --workload /path/to/your/workload
```

### Study 3: Cache Sensitivity
Sweeps L1 Cache parameters.

```bash
docker run --rm -v $(pwd):/workspace -w /workspace gem5-riscv \
    /gem5/build/RISCV/gem5.opt configs/study_3_cache_sensitivity.py \
    --l1d_size 64kB \
    --l1d_assoc 8 \
    --mshrs 16 \
    --workload /path/to/your/workload
```

### Study 4: Power Model
Runs with math-based power model.

```bash
docker run --rm -v $(pwd):/workspace -w /workspace gem5-riscv \
    /gem5/build/RISCV/gem5.opt configs/study_4_ppa.py \
    --workload /path/to/your/workload
```

## 4. Analyzing Results

The scripts generate `m5out/stats.txt`. parsed results can be viewed using:

```bash
python3 analyze_results.py --stats_dir m5out
```

> [!NOTE]
> Ensure `pandas` is installed locally (`pip install pandas`) for advanced analysis features if enabled in the script.
