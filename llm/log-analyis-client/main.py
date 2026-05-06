import asyncio
import sys
import os
import time
import concurrent.futures

# --- Mock Python Tool ---

async def python_aggregation_tool(scanner, results):
    """
    A mock Python tool that demonstrates zero-copy access to the GMM-mapped memory.
    It takes raw offsets from C++ and reads the data directly via memoryview.
    """
    print(f"\n[Python Tool] Starting aggregation of {len(results)} matches...")
    
    # We only process a few to keep the output clean
    limit = 5
    aggregated_data = []
    
    for i, match in enumerate(results[:limit]):
        # ZERO-COPY ACCESS:
        # We call get_data() which returns a memoryview pointing to the shared mmap buffer.
        mview = scanner.get_data(match.offset, match.length)
        
        # We only decode to string when we actually need to print/process it.
        line_text = bytes(mview).decode('utf-8', errors='ignore').strip()
        aggregated_data.append(line_text)
        print(f"  [Aggregator] Processed line {i+1}: {line_text[:60]}...")

    return {
        "status": "success",
        "processed_count": min(len(results), limit),
        "total_available": len(results)
    }

# --- Orchestrator Implementation ---

class Orchestrator:
    def __init__(self, log_path):
        self.log_path = os.path.abspath(log_path)
        self.queue = asyncio.Queue()
        self.workers = {}
        self._load_workers()

    def _load_workers(self):
        """Load all available workers into the registry."""
        try:
            from cpp_scanner_worker import CppScannerWorker
            scanner_worker = CppScannerWorker(self.log_path)
            self.workers[scanner_worker.name] = scanner_worker
            print(f"[*] Loaded worker: {scanner_worker.name}")
        except Exception as e:
            print(f"[!] Warning: Could not load C++ worker module: {e}")
            
        try:
            from logparser_worker import LogparserWorker
            logparser_worker = LogparserWorker()
            self.workers[logparser_worker.name] = logparser_worker
            print(f"[*] Loaded worker: {logparser_worker.name}")
        except Exception as e:
            print(f"[!] Warning: Could not load Logparser worker: {e}")

    async def start(self):
        """Starts the Orchestrator loop."""
        print("[*] Orchestrator started. Waiting for instructions...")
        
        # Start the background consumer task for the instruction queue
        self.worker_task = asyncio.create_task(self._instruction_consumer())
        
        # Simulate Agent instructions using the new worker format
        print("[Agent] Sending instruction: SCAN for 'ERROR' on C++ worker")
        await self.queue.put({"action": "scan", "worker": "scanner", "pattern": "ERROR"})
        
        print("[Agent] Sending instruction: AGGREGATE results using Python tool")
        await self.queue.put({"action": "aggregate"})
        
        # Wait for queue to be processed
        await self.queue.join()
        
        # Shutdown
        await self.queue.put({"action": "exit"})
        await self.worker_task
        print("[*] Orchestrator shutdown complete.")

    async def _instruction_consumer(self):
        """Processes the command queue sequentially."""
        last_results = []
        
        while True:
            cmd = await self.queue.get()
            action = cmd.get("action")
            worker_name = cmd.get("worker")
            
            if action == "exit":
                self.queue.task_done()
                break
            
            print(f"\n[Queue] Processing action: {action} on worker: {worker_name}")
            
            try:
                # Handle old mock instructions explicitly for now or adapt them
                if action == "aggregate":
                    if not last_results:
                        print("[!] No scan results available to aggregate.")
                    else:
                        # Polyglot Dispatch: Hand off the C++ scanner and results to the Python tool
                        scanner_worker = self.workers.get("scanner")
                        if scanner_worker:
                            await python_aggregation_tool(scanner_worker.scanner, last_results)
                    self.queue.task_done()
                    continue

                if not worker_name or worker_name not in self.workers:
                    print(f"[!] Error: Worker '{worker_name}' not found.")
                    self.queue.task_done()
                    continue

                worker = self.workers[worker_name]
                if action not in worker.capabilities():
                    print(f"[!] Error: Worker '{worker_name}' does not support action '{action}'.")
                    self.queue.task_done()
                    continue

                # Run worker execution in a thread pool to avoid blocking the event loop
                loop = asyncio.get_running_loop()
                start_ts = time.time()
                
                # Extract args (everything except 'action' and 'worker')
                args = {k: v for k, v in cmd.items() if k not in ("action", "worker")}
                
                result = await loop.run_in_executor(None, worker.execute, action, args)
                
                elapsed = time.time() - start_ts
                print(f"[*] Worker '{worker_name}' completed '{action}' in {elapsed:.4f}s")
                print(f"[*] Result: {result}")
                
                # Save raw results for legacy aggregate step if this was a scan
                if action == "scan" and "raw_results" in result:
                    last_results = result["raw_results"]
                
            except Exception as e:
                print(f"[!] Error processing instruction {action}: {e}")
            
            self.queue.task_done()

# --- Setup and Execution ---

async def setup_test_environment():
    """Creates a dummy log file to verify parallel scanning."""
    log_file = "large_test.log"
    print(f"[*] Generating test log: {log_file}...")
    
    with open(log_file, "w") as f:
        for i in range(50000):
            if i % 5000 == 0:
                f.write(f"TIMESTAMP-{i} [ERROR] Critical failure in subsystem {i//5000}\n")
            elif i % 1000 == 0:
                f.write(f"TIMESTAMP-{i} [WARN] Unusual latency detected\n")
            else:
                f.write(f"TIMESTAMP-{i} [INFO] System heartbeat healthy\n")
    
    return log_file

async def main():
    test_log = await setup_test_environment()
    
    orchestrator = Orchestrator(test_log)
    await orchestrator.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
