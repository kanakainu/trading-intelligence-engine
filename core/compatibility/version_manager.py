"""Version manager — SDK version tracking, evolution detection."""
from dataclasses import dataclass
from typing import Optional


CURRENT_VERSION = "3.0.0"
TARGET_VERSION  = "4.0.0"


@dataclass
class Version:
    major: int
    minor: int
    patch: int

    @staticmethod
    def parse(v: str) -> "Version":
        parts = v.split(".")
        return Version(int(parts[0]), int(parts[1]), int(parts[2]))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def is_compatible_with(self, other: "Version") -> bool:
        return self.major == other.major


def current() -> Version:   return Version.parse(CURRENT_VERSION)
def target()  -> Version:   return Version.parse(TARGET_VERSION)
def compatible(a: str, b: str) -> bool:
    return Version.parse(a).is_compatible_with(Version.parse(b))
