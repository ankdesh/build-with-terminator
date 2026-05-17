import asyncio
import os
import time
import concurrent.futures

class Orchestrator:
    def __init__(self, log_path):
        self.log_path = os.path.abspath(log_path)
        self.queue = asyncio.Queue()
        self.executors = {}
        self._load_executors()
        self.executor_task = None
        self.last_results = []

    def _load_executors(self):
        """Load all available executors into the registry."""
        try:
            from executors.cpp_scanner import CppScannerExecutor
            scanner_executor = CppScannerExecutor(self.log_path)
            self.executors[scanner_executor.name] = scanner_executor
            print(f"[*] Loaded executor: {scanner_executor.name}")
        except Exception as e:
            print(f"[!] Warning: Could not load C++ executor module: {e}")
            
        try:
            from executors.logparser import LogparserExecutor
            logparser_executor = LogparserExecutor()
            self.executors[logparser_executor.name] = logparser_executor
            print(f"[*] Loaded executor: {logparser_executor.name}")
        except Exception as e:
            print(f"[!] Warning: Could not load Logparser executor: {e}")

        try:
            from executors.stats import StatsExecutor
            stats_executor = StatsExecutor()
            self.executors[stats_executor.name] = stats_executor
            print(f"[*] Loaded executor: {stats_executor.name}")
        except Exception as e:
            print(f"[!] Warning: Could not load Stats executor: {e}")

    async def start(self):
        """Starts the Orchestrator consumer loop in the background."""
        print("[*] Orchestrator started. Waiting for instructions...")
        self.executor_task = asyncio.create_task(self._instruction_consumer())

    async def stop(self):
        """Gracefully shuts down the Orchestrator."""
        await self.queue.put({"action": "exit"})
        if self.executor_task:
            await self.executor_task
        print("[*] Orchestrator shutdown complete.")

    async def send_instruction(self, instruction: dict):
        """Enqueue an instruction for the Orchestrator to process."""
        await self.queue.put(instruction)

    async def wait_until_idle(self):
        """Wait until all queued instructions are processed."""
        await self.queue.join()

    async def _instruction_consumer(self):
        """Processes the command queue sequentially."""
        while True:
            cmd = await self.queue.get()
            action = cmd.get("action")
            executor_name = cmd.get("executor")
            
            if action == "exit":
                self.queue.task_done()
                break
            
            print(f"\n[Queue] Processing action: {action} on executor: {executor_name}")
            
            try:
                if not executor_name or executor_name not in self.executors:
                    print(f"[!] Error: Executor '{executor_name}' not found.")
                    self.queue.task_done()
                    continue

                executor = self.executors[executor_name]
                if action not in executor.capabilities():
                    print(f"[!] Error: Executor '{executor_name}' does not support action '{action}'.")
                    self.queue.task_done()
                    continue

                # Run executor execution in a thread pool to avoid blocking the event loop
                loop = asyncio.get_running_loop()
                start_ts = time.time()
                
                # Extract args (everything except 'action' and 'executor')
                args = {k: v for k, v in cmd.items() if k not in ("action", "executor")}
                
                result = await loop.run_in_executor(None, executor.execute, action, args)
                
                elapsed = time.time() - start_ts
                print(f"[*] Executor '{executor_name}' completed '{action}' in {elapsed:.4f}s")
                print(f"[*] Result: {result}")
                
                # Save raw results for potential downstream operations
                if action == "scan" and "raw_results" in result:
                    self.last_results = result["raw_results"]
                
            except Exception as e:
                print(f"[!] Error processing instruction {action}: {e}")
            
            self.queue.task_done()
