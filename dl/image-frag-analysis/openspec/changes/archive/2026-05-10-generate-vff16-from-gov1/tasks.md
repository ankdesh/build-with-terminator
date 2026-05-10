## 1. Setup and Infrastructure

- [x] 1.1 Add `pandas` and `tqdm` to project requirements (if not present)
- [x] 1.2 Create `generate_vff16.py` scaffold with argument parsing (source_dir, output_dir, sector_size, max_mb)

## 2. Core VFF-16 Generation Logic

- [x] 2.1 Implement file-to-sectors padding logic with `os.urandom`
- [x] 2.2 Implement variable-length fragmentation logic (random partition of $N$ sectors into $K$ fragments)
- [x] 2.3 Implement fragment-level shuffling and assembly
- [x] 2.4 Implement sector extraction and saving as individual `.bin` files

## 3. Metadata and Tracking

- [x] 3.1 Implement metadata collection during fragmentation (file, offset, is_padding, frag_id)
- [x] 3.2 Implement CSV export for metadata using `pandas`
- [x] 3.3 Ensure metadata remains synchronized after shuffling fragments

## 4. Verification and Testing

- [x] 4.1 Create a verification script to check metadata consistency (e.g., total size vs. sector count)
- [x] 4.2 Test with a small sample of GovDocs1 files to verify compatibility with `VFF16Dataset`
