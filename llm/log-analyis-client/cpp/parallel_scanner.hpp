#pragma once

#include <string>
#include <vector>
#include <thread>
#include <atomic>
#include <mutex>
#include <memory>
#include "gmm.hpp"

namespace worker {

/**
 * @struct Match
 * @brief Represents a single log line match.
 */
struct Match {
    size_t offset; ///< Byte offset from start of file.
    size_t length; ///< Length of the line in bytes.
};

/**
 * @class ParallelScanner
 * @brief Multi-core Search Engine for Memory-Mapped Files.
 * 
 * ARCHITECTURAL RATIONALE:
 * Large logs are "embarrassingly parallel." By dividing the memory mapping 
 * into "Slabs" (one per CPU core), we can saturate the hardware's 
 * computation capacity. This scanner handles the boundary complexity 
 * of line-splits between slabs.
 */
class ParallelScanner {
public:
    /**
     * @brief Initializes scanner with a shared memory mapping.
     * @param mapping Pointer to the GMM-provided mapping.
     */
    ParallelScanner(std::shared_ptr<MemoryMapping> mapping);

    /**
     * @brief Executes a parallel search.
     * @param pattern The string to search for.
     * @param stop_flag Atomic flag to interrupt long-running scans.
     * @return Vector of Match objects containing results.
     */
    std::vector<Match> scan(const std::string& pattern, std::atomic<bool>& stop_flag);

private:
    /**
     * @brief Core worker function for a single thread.
     * @param start Byte offset where this thread should start.
     * @param end Byte offset where this thread should stop.
     * @param pattern String to look for.
     * @param local_matches Thread-local storage for results to avoid mutex contention.
     * @param stop_flag Monitored for cancellation requests.
     */
    void scan_slab(size_t start, size_t end, const std::string& pattern, 
                   std::vector<Match>& local_matches, std::atomic<bool>& stop_flag);

    std::shared_ptr<MemoryMapping> mapping_;
};

} // namespace worker
