"""Errors raised by the Hot Pepper adapter.

Every subclass here must surface to the browser only as the safe, generic
``503 PROVIDER_UNAVAILABLE`` problem (ADR-0002 decision 7, ADR-0005 decision
5): none of their messages or attributes may be shown to a browser. Callers
that need to log them must first redact any provider URL with
``dining_radar.integrations.hotpepper.client.redact_query``.
"""


class ProviderUnavailableError(RuntimeError):
    """Base class for any Hot Pepper adapter failure."""


class HotPepperConfigurationError(ProviderUnavailableError):
    """The private runtime search configuration is missing or invalid."""


class HotPepperCommunicationError(ProviderUnavailableError):
    """The provider request failed, timed out, or returned a non-success status."""


class HotPepperResponseError(ProviderUnavailableError):
    """The provider response could not be parsed as the expected shape."""
