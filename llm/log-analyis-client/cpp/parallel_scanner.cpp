#include "parallel_scanner.hpp"
#include <algorithm>
#include <cstring>

namespace worker {

ParallelScanner::ParallelScanner(std::shared_ptr<MemoryMapping> mapping) : mapping_(mapping) {}

std::vector<Match> ParallelScanner::scan(const std::string& pattern, std::atomic<bool>& stop_flag) {
    if (pattern.empty()) return {};

    // Determine hardware parallelism (number of cores).
    size_t num_threads = std::thread::hardware_concurrency();
    if (num_threads == 0) num_threads = 1;

    size_t total_size = mapping_->size();
    size_t slab_size = total_size / num_threads;

    std::vector<std::thread> threads;
    
    // THREAD-LOCAL STORAGE:
    // To maximize performance, each thread writes its results to its own vector.
    // This prevents "false sharing" and eliminates mutex contention during the scan.
    std::vector<std::vector<Match>> results(num_threads);

    for (size_t i = 0; i < num_threads; ++i) {
        size_t start = i * slab_size;
        size_t end = (i == num_threads - 1) ? total_size : (i + 1) * slab_size;
        
        threads.emplace_back(&ParallelScanner::scan_slab, this, start, end, pattern, std::ref(results[i]), std::ref(stop_flag));
    }

    // Wait for all cores to finish.
    for (auto& t : threads) {
        t.join();
    }

    // If cancellation was requested, return an empty set.
    if (stop_flag) return {};

    // GATHER PHASE:
    // Merge the thread-local results into a single batch.
    std::vector<Match> final_results;
    for (const auto& local_matches : results) {
        final_results.insert(final_results.end(), local_matches.begin(), local_matches.end());
    }

    return final_results;
}

void ParallelScanner::scan_slab(size_t start, size_t end, const std::string& pattern, 
                               std::vector<Match>& local_matches, std::atomic<bool>& stop_flag) {
    const char* data = mapping_->data();
    size_t total_size = mapping_->size();

    // BOUNDARY HANDLING (Slab Alignment):
    // 1. If we are not the first slab, skip the current partial line.
    //    We scan forward to the first '\n'.
    if (start > 0) {
        while (start < end && data[start - 1] != '\n') {
            start++;
        }
    }

    // 2. If we are not the last slab, ensure we finish the current line 
    //    even if it extends past our 'end' boundary.
    if (end < total_size) {
        while (end < total_size && data[end - 1] != '\n') {
            end++;
        }
    }

    if (start >= end) return;

    const char* current = data + start;
    const char* slab_end = data + end;

    // SCANN LOOP:
    // We use std::search for efficient pattern matching.
    while (current < slab_end && !stop_flag) {
        const char* match_ptr = std::search(current, slab_end, pattern.begin(), pattern.end());
        
        if (match_ptr == slab_end) break;

        // Found a match! Determine the full line boundaries (start to \n).
        const char* line_start = match_ptr;
        while (line_start > data && *(line_start - 1) != '\n') {
            line_start--;
        }

        const char* line_end = match_ptr;
        while (line_end < data + total_size && *line_end != '\n') {
            line_end++;
        }

        // Record the match metadata (offset and length).
        local_matches.push_back({static_cast<size_t>(line_start - data), static_cast<size_t>(line_end - line_start)});
        
        // Skip to the next line to avoid double-matching the same line.
        current = line_end + 1;
    }
}

} // namespace worker
