"""The origin destination structure that links the cost layer and the math.

Kept dependency light, only pandas, so the SFCA engine can import it without
pulling in geopandas or scipy.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Column names used throughout the OD structure.
ORIGIN = "origin_id"
SUPPLY = "supply_id"
COST = "cost"


@dataclass(frozen=True)
class ODStructure:
    """A sparse within-catchment origin destination cost set.

    pairs has columns origin_id, supply_id, cost. Only pairs within the
    threshold are present. cost_unit is minutes for drive time or meters for
    euclidean distance. threshold is d0 in the same unit. backend records which
    provider produced it.
    """

    pairs: pd.DataFrame
    cost_unit: str
    threshold: float
    backend: str

    def __post_init__(self) -> None:
        missing = {ORIGIN, SUPPLY, COST} - set(self.pairs.columns)
        if missing:
            raise ValueError(f"OD pairs missing columns {missing}")

    @property
    def origins(self) -> list[str]:
        return list(pd.unique(self.pairs[ORIGIN].astype(str)))

    @property
    def supplies(self) -> list[str]:
        return list(pd.unique(self.pairs[SUPPLY].astype(str)))

    def is_empty(self) -> bool:
        return self.pairs.empty
