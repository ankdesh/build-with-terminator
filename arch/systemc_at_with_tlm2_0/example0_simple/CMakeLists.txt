add_executable(example0_simple main.cpp)
target_link_libraries(example0_simple PRIVATE SystemC::systemc)
set_target_properties(example0_simple PROPERTIES CXX_STANDARD 17)
