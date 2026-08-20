from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Label:
    """A named tag that can be applied to a cut, with an optional keyboard shortcut."""

    name: str
    shortcut: str = ""

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Label name must not be empty")
        self.shortcut = self.shortcut.strip()

    def to_dict(self) -> dict:
        return {"name": self.name, "shortcut": self.shortcut}

    @classmethod
    def from_dict(cls, data: dict) -> "Label":
        return cls(name=data["name"], shortcut=data.get("shortcut", ""))
