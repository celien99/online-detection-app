"""EfficientAD 纹理异常检测入口。"""

from __future__ import annotations

from .config import EfficientADConfig

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "EfficientADService": (".engine", "EfficientADService"),
}


def __getattr__(name: str):
    """Lazily load EfficientADService (heavy engine imports)."""
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    module_name, attr_name = _LAZY_EXPORTS[name]
    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value


__all__ = [
    "EfficientADConfig",
    "EfficientADService",
]
