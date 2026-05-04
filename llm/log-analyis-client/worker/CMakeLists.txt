cmake_minimum_required(VERSION 3.10)
project(worker_runtime)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find pybind11
find_package(pybind11 REQUIRED)

# Create the module
pybind11_add_module(worker main.cpp)

# Install destination (optional, but good for structure)
install(TARGETS worker DESTINATION .)
