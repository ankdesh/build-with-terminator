cmake_minimum_required(VERSION 3.12)
project(timer_block CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find SystemC
find_package(SystemC REQUIRED)

# Component library
add_library(timer_block
    timer_block.cpp
)

target_include_directories(timer_block PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(timer_block PRIVATE
    SystemC::systemc
)

# Testbench executable
add_executable(timer_block_tb
    timer_block_tb.cpp
)

target_link_libraries(timer_block_tb PRIVATE
    timer_block
    SystemC::systemc
)