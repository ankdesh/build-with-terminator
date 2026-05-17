import sys
import os
from typing import Dict, Any, List
from executors.base import BaseExecutor

class CppScannerExecutor(BaseExecutor):
    def __init__(self, log_path: str):
        self.log_path = os.path.abspath(log_path)
        self.scanner = None
        self._load_worker()

    def _load_worker(self):
        """Dynamic loading of the C++ shared library."""
        # Find the project root build directory (assumes we are in src/executors)
        build_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "build"))
        if build_dir not in sys.path:
            sys.path.append(build_dir)
        
        try:
            import executor
            self.scanner = executor.Scanner(self.log_path)
        except ImportError as e:
            raise RuntimeError(f"Could not load C++ executor module: {e}")

    @property
    def name(self) -> str:
        return "scanner"

    def capabilities(self) -> List[str]:
        return ["scan", "get_data"]

    def execute(self, action: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if action == "scan":
            pattern = args.get("pattern", "")
            results = self.scanner.scan(pattern)
            return {"status": "success", "matches": len(results), "raw_results": results}
        elif action == "get_data":
            offset = args.get("offset")
            length = args.get("length")
            mview = self.scanner.get_data(offset, length)
            return {"status": "success", "data": mview}
        else:
            raise ValueError(f"Unsupported action: {action}")
