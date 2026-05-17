from abc import ABC, abstractmethod
from typing import Any


class BaseExecutor(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """The identifier used in instructions (e.g., 'logparser', 'scanner')."""
        pass

    @abstractmethod
    def capabilities(self) -> list[str]:
        """Returns the list of actions this executor supports."""
        pass

    @abstractmethod
    def execute(self, action: str, args: dict[str, Any]) -> dict[str, Any]:
        """
        Executes a specific action.
        Returns a dictionary containing the results.
        Raises an exception if the action fails or is unsupported.
        """
        pass
