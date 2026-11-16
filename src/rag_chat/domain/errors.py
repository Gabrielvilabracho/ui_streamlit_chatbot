"""Application-safe errors shared across architectural boundaries."""


class RagError(Exception):
    """Base error for expected RAG failures."""


class ConfigurationError(RagError):
    """Raised when required runtime configuration is missing or invalid."""


class GuardrailViolation(RagError):
    """Raised when a request or response violates an application guardrail."""


class RagTimeoutError(RagError):
    """Raised when retrieval or generation exceeds its allowed deadline."""


class ProviderResponseError(RagError):
    """Raised when a provider returns a response the application cannot interpret."""
