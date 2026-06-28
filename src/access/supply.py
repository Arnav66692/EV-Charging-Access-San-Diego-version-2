"""Charging supply, by charger type, from the AFDC stations and ports.

Supply for a charger type is the set of stations that have ports of that type.
The capacity is the port count. The geometry is the station point. This is the
S_j that the SFCA engine divides demand into.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from src.access.od_types import SUPPLY

PORT_CLASS = {"dcfc": "DCFC", "l2": "L2"}


def station_points(stations_df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Build station point geometry in EPSG:4326 from AFDC station coordinates."""
    df = stations_df.copy()
    df["station_id"] = df["station_id"].astype(str)
    lat = pd.to_numeric(df["latitude"], errors="coerce")
    lon = pd.to_numeric(df["longitude"], errors="coerce")
    valid = lat.notna() & lon.notna()
    df = df[valid]
    geometry = [Point(x, y) for x, y in zip(lon[valid], lat[valid])]
    return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")


def supply_by_type(
    ports_df: pd.DataFrame, stations_df: pd.DataFrame, charger_type: str
) -> gpd.GeoDataFrame:
    """Stations with their port count for one charger type.

    Returns a GeoDataFrame with supply_id, capacity, and point geometry. Only
    stations that actually have ports of this type are included.
    """
    if charger_type not in PORT_CLASS:
        raise ValueError(f"unknown charger_type {charger_type}, expected dcfc or l2")
    port_class = PORT_CLASS[charger_type]

    ports = ports_df.copy()
    ports["station_id"] = ports["station_id"].astype(str)
    typed = ports[ports["port_class"] == port_class]
    capacity = typed.groupby("station_id")["port_count"].sum()

    stations = station_points(stations_df)
    stations = stations[stations["station_id"].isin(capacity.index)].copy()
    stations[SUPPLY] = stations["station_id"].astype(str)
    stations["capacity"] = stations[SUPPLY].map(capacity).astype(float)
    return stations[[SUPPLY, "capacity", "geometry"]].reset_index(drop=True)


def capacity_series(supply_gdf: gpd.GeoDataFrame) -> pd.Series:
    """Supply capacity as a series indexed by supply_id, for the SFCA engine."""
    s = pd.Series(
        supply_gdf["capacity"].to_numpy(),
        index=supply_gdf[SUPPLY].astype(str),
        name="capacity",
    )
    return s
