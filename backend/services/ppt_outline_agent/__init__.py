"""PPT Outline Agent - Advanced outline generation with research capabilities."""

# 使用延迟导入，避免循环导入问题
def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name == "generate_outline_single_shot_sync":
        from .wrapper import generate_outline_single_shot_sync
        return generate_outline_single_shot_sync
    elif name == "convert_outline_to_pages":
        from .wrapper import convert_outline_to_pages
        return convert_outline_to_pages
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "generate_outline_single_shot_sync",
    "convert_outline_to_pages",
]
