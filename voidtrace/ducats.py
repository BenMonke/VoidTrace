"""Ducanator: which prime parts are worth more as ducats than as plat.

Warframe.Market works this out for every prime part from the last day's trades; one call fetches it all
(v1 /tools/ducats). Parts are matched to the catalog by item id; sets are left out (Baro takes parts only).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .items import CatalogItem, is_relic_reward


@dataclass(frozen=True)
class DucatRow:
    name: str
    slug: str
    ducats: int
    plat: float      # volume-weighted average sale price over the last day
    per_plat: float  # ducats per plat at that price
    volume: int      # trades in the last day


def ducat_rows(payload: dict, catalog: Sequence[CatalogItem]) -> list[DucatRow]:
    """Prime parts from a /tools/ducats payload, best ducats per plat first."""
    by_id = {item.id: item for item in catalog if item.id}
    rows = []
    for entry in payload.get("previous_day") or []:
        item = by_id.get(entry.get("item"))
        plat = entry.get("wa_price") or 0
        if item is None or plat <= 0 or not is_relic_reward({"tags": item.tags}):
            continue
        rows.append(DucatRow(item.name, item.slug, int(entry.get("ducats") or 0), float(plat),
                             float(entry.get("ducats_per_platinum_wa") or 0), int(entry.get("volume") or 0)))
    return sorted(rows, key=lambda r: r.per_plat, reverse=True)
