from typing import Any


class SchemaEncoder:
    """ISP: just enough to transform dicts to wire bytes."""

    def encode(self, topic: str, value: Any) -> bytes:  # pragma: no cover - interface only
        raise NotImplementedError

