"""Application-safe errors shared across architectural boundaries."""

from enum import StrEnum


class RagError(Exception):
    """Base error for expected RAG failures."""


class ConfigurationError(RagError):
    """Raised when required runtime configuration is missing or invalid."""


class GuardrailRule(StrEnum):
    INPUT_EMPTY = "input.empty"
    INPUT_MAX_CHARACTERS = "input.max_characters"
    OUTPUT_EMPTY = "output.empty"
    OUTPUT_MAX_CHARACTERS = "output.max_characters"
    SECRET = "privacy.secret"
    INJECTION = "input.injection_signal"
    CONTEXT_LIMIT = "context.max_bytes"
    CITATION = "output.invalid_citation"
    RATE_LIMIT = "request.rate_limit"
    TOKEN_QUOTA = "request.token_quota"
    CUSTOM = "custom"


class GuardrailViolation(RagError):
    """Raised when a request or response violates an application guardrail."""

    def __init__(self, *args: object, rule: GuardrailRule = GuardrailRule.CUSTOM) -> None:
        super().__init__(*args)
        self.rule = rule


class RagTimeoutError(RagError):
    """Raised when retrieval or generation exceeds its allowed deadline."""


class ProviderResponseError(RagError):
    """Raised when a provider returns a response the application cannot interpret."""
