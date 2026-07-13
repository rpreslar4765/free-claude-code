"""Local-first routing: try a local model before falling back to another provider."""

from .client import LocalFirstProvider

__all__ = ["LocalFirstProvider"]
