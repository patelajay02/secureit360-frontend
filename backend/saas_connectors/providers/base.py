"""Base provider class and registry for the Universal SaaS Connector.

Every concrete SaaS integration subclasses BaseProvider and registers
itself via @register_provider("slug"). scan_runner and the OAuth routes
resolve providers through PROVIDER_REGISTRY.

Flow context
------------
Provider instances are created per HTTP request, so anything that needs
to survive between build_auth_url and exchange_code (e.g. a PKCE
code_verifier) is stashed in self.flow_context and re-hydrated from the
state cache on the callback side. Anything from callback query-string
(Zoho's accounts-server, etc.) is also merged into flow_context before
exchange_code() is called.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    slug: str = ""

    def __init__(self) -> None:
        self.flow_context: dict[str, Any] = {}

    @abstractmethod
    def build_auth_url(self, state: str) -> str:
        """Return the authorization URL the user should be redirected to."""

    @abstractmethod
    def exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange an authorization code for tokens.

        Returns a dict with:
            access_token, refresh_token, expires_at (ISO-8601 UTC),
            tenant_id_or_org_id, extra (provider-specific extras)
        """

    @abstractmethod
    def refresh_tokens(self, refresh_token: str) -> dict[str, Any]:
        """Refresh an expired access token. Returns the same shape as
        exchange_code()."""

    @abstractmethod
    def fetch_payloads(
        self,
        credentials: dict[str, Any],
        capabilities: list[str],
    ) -> dict[str, Any]:
        """Call the SaaS APIs and return normalized payloads keyed by the
        generic check capability (e.g. admin_ratio, mfa_coverage)."""


PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {}


def register_provider(slug: str):
    def decorator(cls: type[BaseProvider]) -> type[BaseProvider]:
        cls.slug = slug
        PROVIDER_REGISTRY[slug] = cls
        return cls

    return decorator
