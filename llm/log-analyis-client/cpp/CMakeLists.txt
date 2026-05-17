cmake_minimum_required(VERSION 3.10)
project(worker_runtime)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find pybind11 using the active python environment
execute_process(
    COMMAND python3 -m pybind11 --cmakedir
    OUTPUT_VARIABLE PYBIND11_CMAKE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
list(APPEND CMAKE_PREFIX_PATH "${PYBIND11_CMAKE_DIR}")
find_package(pybind11 REQUIRED)

# Create the module
pybind11_add_module(executor 
    main.cpp 
    gmm.cpp 
    parallel_scanner.cpp
)

# Install destination
install(TARGETS executor DESTINATION .)
