"""Validation Report — summary of knowledge pack health."""
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ValidationReport:
    counts: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def status(self) -> str:
        return "PASS" if not self.errors else "FAIL"

    def print(self) -> str:
        lines = ["", "Knowledge Pack Summary", "─" * 34]
        for cat, count in sorted(self.counts.items()):
            lines.append(f"  {cat:<22} {count:>4}")
        lines += ["─" * 34, f"  {'Total Objects':<22} {self.total:>4}", "─" * 34,
                  "", "Validation"]
        missing = sum(1 for e in self.errors if "MISSING_REF" in e)
        broken  = sum(1 for e in self.errors if "BROKEN" in e)
        dup_id  = sum(1 for e in self.errors if "DUPLICATE_ID" in e)
        circular = sum(1 for e in self.errors if "CIRCULAR" in e)
        orphans  = sum(1 for w in self.warnings if "ORPHAN" in w)
        lines += [
            f"  Missing References   {missing:>4}",
            f"  Broken Links         {broken:>4}",
            f"  Duplicate IDs        {dup_id:>4}",
            f"  Circular Dependency  {circular:>4}",
            f"  Orphan Objects       {orphans:>4}  (warnings)",
            f"  Total Errors         {len(self.errors):>4}",
            f"  Total Warnings       {len(self.warnings):>4}",
            "", f"STATUS: {self.status}", "",
        ]
        return "\n".join(lines)
