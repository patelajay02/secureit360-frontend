"""Provider package — import concrete providers so their @register_provider
decorators fire and populate PROVIDER_REGISTRY."""

from . import xero  # noqa: F401 — registers "xero"
from . import zoho  # noqa: F401 — registers "zoho"
from .base import PROVIDER_REGISTRY, BaseProvider, register_provider  # re-export

__all__ = ["PROVIDER_REGISTRY", "BaseProvider", "register_provider"]
