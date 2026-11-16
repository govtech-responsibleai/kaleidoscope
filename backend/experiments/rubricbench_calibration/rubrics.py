"""RubricBench rubric definitions in the shape the judge prompt template expects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from experiments.rubricbench_calibration.config import EXPERIMENT_DIR


@dataclass(frozen=True)
class RubricOption:
    """One selectable label with its description."""

    option: str
    description: str


@dataclass(frozen=True)
class Rubric:
    """A binary RubricBench rubric.

    Attributes:
        key: Stable identifier used in predictions and result tables.
        name: Human-readable dimension name shown to the judge.
        criteria: One-sentence question the judge answers.
        options: The two labels with descriptions, in the order the dataset card lists them (use ``best_option`` to find the positive label).
        best_option: The desirable label; used to express aggregated verdicts.
    """

    key: str
    name: str
    criteria: str
    options: tuple[RubricOption, ...]
    best_option: str

    @property
    def option_values(self) -> tuple[str, ...]:
        """Labels in declared order."""
        return tuple(option.option for option in self.options)

    def canonicalize(self, value: str | None) -> str | None:
        """Map a free-text label onto one of the rubric's options.

        Args:
            value: Raw label from a judge or an annotator.

        Returns:
            The matching option (case- and whitespace-insensitive) or ``None``.
        """
        if value is None:
            return None
        needle = " ".join(str(value).strip().lower().split())
        for option in self.option_values:
            if " ".join(option.lower().split()) == needle:
                return option
        return None

    def options_as_dicts(self) -> list[dict[str, str]]:
        """Options in the ``{"option", "description"}`` shape used by the judge template."""
        return [{"option": o.option, "description": o.description} for o in self.options]


def load_rubrics(path: Path | None = None) -> list[Rubric]:
    """Load rubric definitions from YAML.

    Args:
        path: YAML file; defaults to ``rubrics.yaml`` next to this module.

    Returns:
        Rubrics in file order.
    """
    source = path or EXPERIMENT_DIR / "rubrics.yaml"
    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    rubrics: list[Rubric] = []
    for item in raw.get("rubrics", []):
        options = tuple(RubricOption(option=o["option"], description=o["description"]) for o in item["options"])
        rubric = Rubric(
            key=item["key"],
            name=item["name"],
            criteria=item["criteria"],
            options=options,
            best_option=item["best_option"],
        )
        if rubric.best_option not in rubric.option_values:
            raise ValueError(f"Rubric '{rubric.key}': best_option '{rubric.best_option}' is not an option.")
        rubrics.append(rubric)
    return rubrics
