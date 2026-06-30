import asyncio
import os
import time


class Orchestrator:
    def __init__(self, log_path):
        self.log_path = os.path.abspath(log_path)
        self.queue = asyncio.Queue()
        self.executors = {}
        self.context = {}
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
            from executors.template_extractor import TemplateExtractorExecutor

            template_extractor = TemplateExtractorExecutor()
            self.executors[template_extractor.name] = template_extractor
            print(f"[*] Loaded executor: {template_extractor.name}")
        except Exception as e:
            print(f"[!] Warning: Could not load Template Extractor executor: {e}")

        try:
            from executors.stats import StatsExecutor

            stats_executor = StatsExecutor()
            self.executors[stats_executor.name] = stats_executor
            print(f"[*] Loaded executor: {stats_executor.name}")
        except Exception as e:
            print(f"[!] Warning: Could not load Stats executor: {e}")

        try:
            from executors.llm import LlmExecutor

            llm_executor = LlmExecutor()
            self.executors[llm_executor.name] = llm_executor
            print(f"[*] Loaded executor: {llm_executor.name}")
        except Exception as e:
            print(f"[!] Warning: Could not load LLM executor: {e}")

        try:
            from executors.python_runner import PythonRunnerExecutor

            python_runner = PythonRunnerExecutor()
            self.executors[python_runner.name] = python_runner
            print(f"[*] Loaded executor: {python_runner.name}")
        except Exception as e:
            print(f"[!] Warning: Could not load Python Runner executor: {e}")

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

                # Extract args (everything except 'action', 'executor', and 'output_key')
                args = {k: v for k, v in cmd.items() if k not in ("action", "executor", "output_key")}

                # Resolve any context references ($var) in args
                resolved_args = self._resolve_val(args)

                # Global Log Path Injection: inject self.log_path as target_file if not provided
                if not resolved_args.get("target_file"):
                    resolved_args["target_file"] = self.log_path

                result = await loop.run_in_executor(None, executor.execute, action, resolved_args)

                elapsed = time.time() - start_ts
                print(f"[*] Executor '{executor_name}' completed '{action}' in {elapsed:.4f}s")

                # Print result outputs if they exist in the return dict
                if isinstance(result, dict):
                    if "result" in result and result["result"] is not None:
                        print(f"[*] Result Value:\n{result['result']}")
                    if result.get("stdout"):
                        print(f"[*] Standard Output:\n{result['stdout']}")
                    if result.get("stderr"):
                        print(f"[!] Standard Error:\n{result['stderr']}")
                    if result.get("code"):
                        print(f"[*] Generated Code:\n{result['code']}")

                # Save to context if output_key is provided
                output_key = cmd.get("output_key")
                if output_key:
                    self.context[output_key] = result
                    print(f"[*] Saved output to context key: '{output_key}'")

                # Save raw results for potential downstream operations
                if action == "scan" and "raw_results" in result:
                    self.last_results = result["raw_results"]

            except Exception as e:
                print(f"[!] Error processing instruction {action}: {e}")

            self.queue.task_done()

    def _resolve_val(self, val):
        """Recursively resolves $ context variables in arguments."""
        if isinstance(val, str) and val.startswith("$"):
            # Extract path (remove '$' prefix)
            path = val[1:]
            parts = path.split(".")
            current = self.context
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
            return current
        elif isinstance(val, dict):
            return {k: self._resolve_val(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [self._resolve_val(v) for v in val]
        return val
