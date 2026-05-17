#pragma once

#include <string>
#include <unordered_map>
#include <mutex>
#include <memory>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdexcept>

/**
 * @namespace worker
 * @brief High-performance log processing components using C++17.
 */
namespace worker {

/**
 * @class MemoryMapping
 * @brief Zero-Copy File Interface using Memory-Mapped Files (mmap).
 * 
 * ARCHITECTURAL RATIONALE:
 * To handle multi-gigabyte logs, we must avoid the "Double Copy" problem 
 * (Disk -> Kernel -> User Space -> Python). mmap allows the OS to map the 
 * file directly into our virtual address space. The data remains in the 
 * OS Page Cache, and we touch only the physical RAM we actually read.
 */
class MemoryMapping {
public:
    /**
     * @brief Maps a file into the process's address space.
     * @param path Absolute path to the file.
     * @throws std::runtime_error if file access or mapping fails.
     */
    MemoryMapping(const std::string& path);
    
    /**
     * @brief RAII Cleanup: Unmaps memory and closes the file descriptor.
     */
    ~MemoryMapping();

    /** @return Pointer to the raw memory (disk-backed). */
    const char* data() const { return data_; }
    
    /** @return Size of the file in bytes. */
    size_t size() const { return size_; }

private:
    int fd_;      ///< File descriptor.
    size_t size_; ///< Cached file size.
    char* data_;  ///< Start of the mapped memory region.
};

/**
 * @class GlobalMemoryManager
 * @brief Singleton Registry for Shared Memory Mappings.
 * 
 * ARCHITECTURAL RATIONALE:
 * Prevents redundant mappings. If a C++ Scanner and a Python Aggregator 
 * both need 'system.log', this manager ensures they share the same physical 
 * memory pages, reducing RAM pressure and cache misses.
 */
class GlobalMemoryManager {
public:
    /** @return Reference to the singleton instance. */
    static GlobalMemoryManager& instance() {
        static GlobalMemoryManager instance;
        return instance;
    }

    /**
     * @brief Retrieves an existing mapping or creates a new one.
     * @param path Path to the file.
     * @return Thread-safe shared pointer to the mapping.
     */
    std::shared_ptr<MemoryMapping> get_mapping(const std::string& path);

private:
    GlobalMemoryManager() = default;
    ~GlobalMemoryManager() = default;
    
    // Explicitly non-copyable.
    GlobalMemoryManager(const GlobalMemoryManager&) = delete;
    GlobalMemoryManager& operator=(const GlobalMemoryManager&) = delete;

    std::unordered_map<std::string, std::shared_ptr<MemoryMapping>> mappings_;
    std::mutex mutex_; ///< Guards the mappings registry.
};

} // namespace worker
