#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include "gmm.hpp"
#include "parallel_scanner.hpp"

namespace py = pybind11;

namespace worker {

/**
 * @class PythonScanner
 * @brief High-level bridge between Python and C++ Scanner.
 * 
 * Provides an idiomatic Python interface to the multi-threaded C++ backend.
 */
class PythonScanner {
public:
    /**
     * @brief Constructor. Requests a mapping from the Global Memory Manager.
     */
    PythonScanner(const std::string& path) {
        mapping_ = GlobalMemoryManager::instance().get_mapping(path);
        scanner_ = std::make_unique<ParallelScanner>(mapping_);
        stop_flag_ = false;
    }

    /**
     * @brief Executes a search while releasing the Python GIL.
     * 
     * RATIONALE:
     * We use 'py::call_guard<py::gil_scoped_release>()' in the binding below. 
     * This allows the C++ threads to run in parallel with the Python 
     * event loop, ensuring the Orchestrator remains responsive.
     */
    std::vector<Match> scan(const std::string& pattern) {
        stop_flag_ = false;
        return scanner_->scan(pattern, stop_flag_);
    }

    /**
     * @brief Signals background threads to stop.
     */
    void cancel() {
        stop_flag_ = true;
    }

    /**
     * @brief Returns a zero-copy slice of the log file.
     * 
     * RATIONALE:
     * Instead of creating a new Python 'str', we return a 'memoryview'.
     * This is a direct window into our mmap buffer. Python code can read 
     * the data, but no byte-copying occurs until Python explicitly 
     * converts it (e.g., calling .tobytes() or decoding to string).
     */
    py::memoryview get_data(size_t offset, size_t length) {
        if (offset + length > mapping_->size()) {
            throw std::out_of_range("Offset/length out of range");
        }
        return py::memoryview::from_buffer(
            const_cast<char*>(mapping_->data() + offset),
            {length},
            {sizeof(char)}
        );
    }

private:
    std::shared_ptr<MemoryMapping> mapping_;
    std::unique_ptr<ParallelScanner> scanner_;
    std::atomic<bool> stop_flag_; ///< Shared between Python and C++ threads.
};

} // namespace worker

/**
 * pybind11 Module Declaration
 */
PYBIND11_MODULE(executor, m) {
    m.doc() = "High-performance worker runtime with Shared Memory and Parallel Scanning.";

    // Export the Match struct as a simple Python object.
    py::class_<worker::Match>(m, "Match")
        .def_readonly("offset", &worker::Match::offset)
        .def_readonly("length", &worker::Match::length);

    // Export the Scanner class.
    py::class_<worker::PythonScanner>(m, "Scanner")
        .def(py::init<const std::string&>())
        // Release GIL during scan to allow true parallelism.
        .def("scan", &worker::PythonScanner::scan, py::call_guard<py::gil_scoped_release>())
        .def("cancel", &worker::PythonScanner::cancel)
        .def("get_data", &worker::PythonScanner::get_data);
}
