from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseExecutor(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """The identifier used in instructions (e.g., 'logparser', 'scanner')."""
        pass

    @abstractmethod
    def capabilities(self) -> List[str]:
        """Returns the list of actions this executor supports."""
        pass

    @abstractmethod
    def execute(self, action: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a specific action.
        Returns a dictionary containing the results.
        Raises an exception if the action fails or is unsupported.
        """
        pass
