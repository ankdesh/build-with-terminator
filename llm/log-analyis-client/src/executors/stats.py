import os
from typing import Dict, Any, List
from executors.base import BaseExecutor

class StatsExecutor(BaseExecutor):
    """
    A Python worker responsible for extracting general statistics and preview 
    samples from log files.
    
    Rationale:
    Before engaging in heavy parsing operations (like Drain or C++ scanning), 
    the Orchestrator or LLM Planner needs to understand the basic characteristics 
    of the log file. This worker provides a lightweight, non-blocking way to 
    get this metadata and a preview without loading the entire file into memory.
    """
    def __init__(self, default_n: int = 10):
        """
        Initializes the StatsWorker.
        
        Args:
            default_n (int): The default number of lines to return in get_sample 
                             if no limit is explicitly provided in the instruction.
        """
        self.default_n = default_n

    @property
    def name(self) -> str:
        """
        The identifier used in instructions. By standardizing this name, 
        the Orchestrator knows exactly how to route 'stats' instructions.
        """
        return "stats"

    def capabilities(self) -> List[str]:
        """
        Returns the list of actions this worker supports. 
        This is used for Worker Capability Discovery by the Orchestrator.
        """
        return ["get_stats", "get_sample"]

    def execute(self, action: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Unified execute interface. 
        
        Rationale:
        This conforms to the WorkerBase contract, ensuring deterministic 
        and replayable instruction execution from the Orchestrator.
        """
        target_file = args.get("target_file")
        if not target_file or not os.path.exists(target_file):
            raise ValueError("Invalid target_file. A valid file path is required for all stats operations.")

        if action == "get_stats":
            return self._get_stats(target_file)
        elif action == "get_sample":
            limit = args.get("limit", self.default_n)
            return self._get_sample(target_file, limit)
        else:
            raise ValueError(f"Unsupported action: {action}")

    def _get_stats(self, target_file: str) -> Dict[str, Any]:
        """
        Calculates basic file statistics (file size and total line count).
        
        Rationale:
        We count lines by iterating over the file object in binary mode. 
        This is significantly faster and uses far less memory than `readlines()` 
        or `read().count('\\n')` for large log files, ensuring the worker remains 
        lightweight and responsive even for gigabyte-sized files.
        """
        file_size = os.path.getsize(target_file)
        
        line_count = 0
        # Binary mode is generally faster for raw iteration when we only care about line breaks.
        with open(target_file, 'rb') as f:
            for _ in f:
                line_count += 1
                
        return {
            "status": "success",
            "file_size_bytes": file_size,
            "line_count": line_count
        }

    def _get_sample(self, target_file: str, limit: int) -> Dict[str, Any]:
        """
        Reads and returns up to `limit` lines from the file.
        
        Rationale:
        We break out of the loop exactly when the limit is reached. 
        This ensures O(1) memory usage (dependent only on the limit) and 
        O(limit) time complexity, making previews instantaneous regardless 
        of the actual file size.
        """
        lines = []
        # We use utf-8 with ignore to gracefully handle any bad bytes in logs
        # without crashing the worker execution.
        with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if i >= limit:
                    break
                lines.append(line.rstrip('\n'))
                
        return {
            "status": "success",
            "lines": lines,
            "returned_count": len(lines)
        }
