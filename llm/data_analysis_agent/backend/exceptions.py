"""
Domain-specific exceptions for WPS-AI application.

Fail explicitly with actionable error context rather than generic exceptions.
"""


class WPSAIBaseException(Exception):
    """Base exception for all WPS-AI domain errors."""

    def __init__(self, message: str, details: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class SessionNotFoundError(WPSAIBaseException):
    """Raised when a requested session identifier does not exist."""

    def __init__(self, session_id: str) -> None:
        super().__init__(
            message=f"Session with ID '{session_id}' not found.",
            details=f"The session ID '{session_id}' does not exist on disk or has been deleted."
        )
        self.session_id = session_id


class DatasetNotLoadedError(WPSAIBaseException):
    """Raised when analysis is requested on a session without an uploaded dataset."""

    def __init__(self, session_id: str) -> None:
        super().__init__(
            message=f"No dataset loaded for session '{session_id}'.",
            details="Upload a CSV and column description file before initiating queries."
        )
        self.session_id = session_id


class InvalidFileFormatError(WPSAIBaseException):
    """Raised when an uploaded file is invalid or not parseable as CSV/text."""

    def __init__(self, filename: str, reason: str) -> None:
        super().__init__(
            message=f"Invalid file '{filename}': {reason}",
            details=reason
        )
        self.filename = filename


class DataProfilingError(WPSAIBaseException):
    """Raised when automated profiling fails on an uploaded dataset."""

    def __init__(self, filename: str, reason: str) -> None:
        super().__init__(
            message=f"Failed to profile dataset '{filename}': {reason}",
            details=reason
        )
        self.filename = filename


class CodeExecutionError(WPSAIBaseException):
    """Raised when generated Python data analysis code fails to execute."""

    def __init__(self, code: str, traceback_str: str) -> None:
        super().__init__(
            message="Data analysis code execution failed.",
            details=traceback_str
        )
        self.code = code
        self.traceback_str = traceback_str


class CodeExecutionTimeoutError(WPSAIBaseException):
    """Raised when generated Python code exceeds execution time limit."""

    def __init__(self, timeout_seconds: int) -> None:
        super().__init__(
            message=f"Code execution timed out after {timeout_seconds} seconds.",
            details=f"The query exceeded the maximum allowed computation time ({timeout_seconds}s)."
        )
        self.timeout_seconds = timeout_seconds


class LLMServiceError(WPSAIBaseException):
    """Raised when calls to the OpenAI-compatible endpoint fail."""

    def __init__(self, status_code: int, response_text: str) -> None:
        super().__init__(
            message=f"LLM API request failed with HTTP {status_code}.",
            details=response_text
        )
        self.status_code = status_code
        self.response_text = response_text


class LLMConfigurationError(WPSAIBaseException):
    """Raised when the LLM service is required but unconfigured."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            details="Ensure OPENAI_API_BASE and OPENAI_API_KEY are configured in the environment."
        )
