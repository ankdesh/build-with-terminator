#include <pybind11/pybind11.h>

std::string hello() {
    return "Hello from C++!";
}

PYBIND11_MODULE(worker, m) {
    m.doc() = "Worker C++ extension";
    m.def("hello", &hello, "A function that returns a hello message");
}
