"""Lógica sin dependencias de UI/servidor (testeable en cualquier entorno)."""
from __future__ import annotations


def validate_url(raw: str) -> str:
    """Normaliza y valida. Lanza ValueError si no es http(s)."""
    url = (raw or "").strip().rstrip("/")
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("La dirección debe empezar por http:// o https://")
    return url
