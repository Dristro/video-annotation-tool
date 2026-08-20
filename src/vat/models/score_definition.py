from __future__ import annotations

from dataclasses import dataclass

DTYPE_FLOAT = "float"
DTYPE_INT = "int"
VALID_DTYPES = (DTYPE_FLOAT, DTYPE_INT)


@dataclass
class ScoreDefinition:
    """A named, ranged numeric field that can be recorded alongside a cut's
    label (e.g. "Technique": 0-100 float, "Confidence": 1-5 int).

    Each score has its own independent range and dtype, entirely separate
    from every other score defined in the project. The optional description
    is shown in the score editor (and as a tooltip where the value is
    entered) so the user can see what a score means.
    """

    name: str
    minimum: float = 0.0
    maximum: float = 100.0
    dtype: str = DTYPE_FLOAT
    description: str = ""

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Score name must not be empty")
        if self.dtype not in VALID_DTYPES:
            raise ValueError(f"dtype must be one of {VALID_DTYPES}, got '{self.dtype}'")
        self.minimum = float(self.minimum)
        self.maximum = float(self.maximum)
        if self.minimum >= self.maximum:
            raise ValueError("minimum must be less than maximum")
        if self.dtype == DTYPE_INT and (not self.minimum.is_integer() or not self.maximum.is_integer()):
            raise ValueError("minimum/maximum must be whole numbers when dtype is 'int'")
        self.description = self.description.strip()

    def coerce(self, raw: str) -> float | int:
        """Parse and range-check a raw text value. Raises ValueError if the
        text isn't a number, isn't a whole number for an 'int' score, or is
        outside [minimum, maximum].
        """
        raw = raw.strip()
        if not raw:
            raise ValueError(f"'{self.name}' is required")
        try:
            value = float(raw)
        except ValueError:
            raise ValueError(f"'{self.name}' must be a number") from None
        if self.dtype == DTYPE_INT:
            if not value.is_integer():
                raise ValueError(f"'{self.name}' must be a whole number")
            value = int(value)
        if not (self.minimum <= value <= self.maximum):
            raise ValueError(f"'{self.name}' must be between {self.minimum:g} and {self.maximum:g}")
        return value

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "dtype": self.dtype,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScoreDefinition":
        return cls(
            name=data["name"],
            minimum=data.get("minimum", 0.0),
            maximum=data.get("maximum", 100.0),
            dtype=data.get("dtype", DTYPE_FLOAT),
            description=data.get("description", ""),
        )
