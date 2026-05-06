## 1. C++ Core Development

- [x] 1.1 Implement Global Memory Manager (mmap wrapper)
- [x] 1.2 Implement Thread Pool and Parallel Scanner
- [x] 1.3 Add atomic cancellation support
- [x] 1.4 Expose GMM and Scanner to Python via pybind11 (with detailed comments)

## 2. Python Orchestrator Enhancements

- [x] 2.1 Implement `asyncio.Queue` for instruction processing
- [x] 2.2 Add tool dispatcher for C++ and Python tools
- [x] 2.3 Verify zero-copy data flow from C++ to Python
- [x] 2.4 Test parallel scanning and cancellation

## 4. Build and Verification

- [x] 4.1 Build the C++ project using CMake
- [x] 4.2 Run the orchestrator and verify parallel scanning on a sample large file
- [x] 4.3 Verify that both C++ and Python tools can access the same memory mapping via GMM
- [x] 4.4 Verify the cancellation mechanism by stopping a long-running scan
- [x] 4.5 Add a basic test case for the C++ extension and GMM using `pytest`
