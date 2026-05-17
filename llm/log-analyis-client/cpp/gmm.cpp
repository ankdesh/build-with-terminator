#include "gmm.hpp"
#include <iostream>

namespace worker {

MemoryMapping::MemoryMapping(const std::string& path) : fd_(-1), size_(0), data_(nullptr) {
    // Open file in read-only mode.
    fd_ = open(path.c_str(), O_RDONLY);
    if (fd_ == -1) {
        throw std::runtime_error("Could not open file: " + path);
    }

    // Retrieve file metadata to determine size for mapping.
    struct stat sb;
    if (fstat(fd_, &sb) == -1) {
        close(fd_);
        throw std::runtime_error("Could not get file size: " + path);
    }
    size_ = sb.st_size;

    // mmap with size 0 is an error.
    if (size_ == 0) {
        close(fd_);
        throw std::runtime_error("File is empty: " + path);
    }

    // MEMORY MAPPING LOGIC:
    // PROT_READ: We only need to read.
    // MAP_PRIVATE: Copy-on-write (though we won't write).
    // This call does NOT load the file into RAM immediately. It sets up 
    // page table entries. The OS will load pages from disk as we access them.
    data_ = static_cast<char*>(mmap(NULL, size_, PROT_READ, MAP_PRIVATE, fd_, 0));
    if (data_ == MAP_FAILED) {
        close(fd_);
        throw std::runtime_error("mmap failed for file: " + path);
    }
}

MemoryMapping::~MemoryMapping() {
    // Release the virtual memory region.
    if (data_ != nullptr && data_ != MAP_FAILED) {
        munmap(data_, size_);
    }
    // Close the file descriptor.
    if (fd_ != -1) {
        close(fd_);
    }
}

std::shared_ptr<MemoryMapping> GlobalMemoryManager::get_mapping(const std::string& path) {
    // Ensure thread-safety for the singleton cache.
    std::lock_guard<std::mutex> lock(mutex_);
    
    auto it = mappings_.find(path);
    if (it != mappings_.end()) {
        // Return existing mapping if already in cache.
        return it->second;
    }

    // Create a new mapping and store it in the cache.
    auto mapping = std::make_shared<MemoryMapping>(path);
    mappings_[path] = mapping;
    return mapping;
}

} // namespace worker
