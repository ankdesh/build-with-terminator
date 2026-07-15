cmake_minimum_required(VERSION 3.12)
project(SystemC_TLM_AT_Examples CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Configure compiler flags
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    add_compile_options(-Wall -Wextra)
endif()

# Point CMake to the local SystemC installation prefix
list(APPEND CMAKE_PREFIX_PATH "/home/ankdesh/explore/build-with-terminator/arch/systemc_at_with_tlm2_0/systemc-dist")

# Find SystemC package
find_package(SystemCLanguage REQUIRED)

# No need for manual include_directories when linking with SystemC::systemc

# Add Example Subdirectories
add_subdirectory(example0_simple)
add_subdirectory(example1_pipeline)
add_subdirectory(example2_backpressure)
add_subdirectory(example3_arbitration)
