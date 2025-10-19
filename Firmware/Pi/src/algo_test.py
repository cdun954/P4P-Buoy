#!/usr/bin/env python3
"""
Full-coverage runner for ArduRover SITL.

Flow: GUIDED -> approach tile center -> LOITER wait -> next ... -> RTL

Deps:
- mavlink_cmd.py (your helper with connect_fc, arm, set_mode, send_guided_waypoint, read_gps, is_at_wp, etc.)
- coverage_grid.py (your grid/planner module with build_grid_map, plan_lawnmower_path, read_poly_file, _nearest_tile_to_point)

Run:
    python cover_geofence_run.py --fen Firmware/Pi/Algorithm/taka_lake.fen
"""

from __future__ import annotations
import time
import math
import argparse
from typing import Dict, List, Tuple, Optional

import mav2 as m
from grid_2 import (
    read_poly_file,
    build_grid_map_meters,
    plan_lawnmower_path,
    expand_route_with_refinements,
    _nearest_tile_to_point,
    refine_every_ten_tile,
)

EARTH_R = 6371000.0  # meters
Coordinate = Tuple[float, float]  # (lat, lon)


# -------------------- convenience / safety --------------------
def wait_heartbeat(master, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        hb = master.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if hb:
            return True
    return False

def _norm(pt: Tuple[float, float], nd=7) -> Tuple[float, float]:
    # stable float key for centers
    return (round(pt[0], nd), round(pt[1], nd))

def _center_to_key_map(grid) -> Dict[Tuple[float,float], Tuple[int,int]]:
    # maps (center_lat, center_lon) -> (row, col)
    m = {}
    for t in grid.iter_tiles():
        m[_norm(t.center)] = (t.row, t.col)
    return m

def _tile_key_for_coord(grid, center_to_key, lat, lon) -> Tuple[int,int]:
    # fast exact/rounded center lookup, fallback to nearest tile
    key = center_to_key.get(_norm((lat, lon)))
    if key:
        return key
    t = _nearest_tile_to_point(grid, (lat, lon))
    return (t.row, t.col) if t else (-1, -1)



# -------------------- main coverage routine --------------------
def run_coverage(
    fen_path: str,
    mavproxy_on: bool = True,
    tile_size_lat: float = 0.00015,
    tile_size_lon: Optional[float] = None,
    tile_size_m: float = 10,
    coverage_threshold: float = 0.75,
    samples_per_side: int = 5,
    wp_accept_m: float = 1,
    loiter_sec: float = 1.0,
    loiter_radius: int = 5,
    wp_speed: float = 1.0,
    max_wp_time_s: float = 2.0,
    rtl_at_end: bool = True,
) -> None:
    
    # 1) Load geofence + grid
    geofence = read_poly_file(fen_path)
    grid = build_grid_map_meters(
        geofence,
        tile_size_m=tile_size_m,
        coverage_threshold=coverage_threshold,
    )

    # 2) Connect to FC
    master = m.connect_fc(mavproxy_on)

    # Ensure GUIDED + armed + GPS
    if m.read_mode(master) != "GUIDED":
        m.set_mode(master, "GUIDED")
    if m.is_armed(master) is False:
        m.arm(master)
        while not m.is_armed(master):
            time.sleep(0.05)

    gps = m.read_gps(master)
    if not gps:
        raise RuntimeError("No GPS fix from FC.")

    # 3) Pick start as nearest tile to current GPS
    nearest_tile = _nearest_tile_to_point(grid, (gps["lat"], gps["lon"]))
    start_hint = nearest_tile.center if nearest_tile else geofence[0]

    # 4) Plan route (lawnmower) from start_hint
    route: List[Coordinate] = plan_lawnmower_path(grid, start_hint=start_hint)
    if not route:
        raise RuntimeError("No route generated from geofence/grid settings.")
    print(f"[COVER] Waypoints in coverage path: {len(route)}")

    refinement = refine_every_ten_tile(
        g=grid,
        n=3,                      # split each selected tile into 3x3 subtiles
        coverage_threshold=0.80,  # keep only subtiles sufficiently inside polygon
        samples_per_side=5,
    )
    route = expand_route_with_refinements(grid, route, refinement)

    # 5) Set desired groundspeed + loiter radius + wp acceptance
    m.set_wp_speed(master, wp_speed)
    m.set_loiter_radius(master, loiter_radius)
    m.set_wp_acceptance_radius(master, wp_accept_m)

    center_to_key = _center_to_key_map(grid)
    visited: set[Tuple[int,int]] = set()

# March through the route
    for idx, (lat, lon) in enumerate(route, start=1):
        tile_key = _tile_key_for_coord(grid, center_to_key, lat, lon)
        first_time_here = tile_key not in visited

        print(f"[COVER] {idx}/{len(route)} -> ({lat:.7f}, {lon:.7f}) "
              f"{'(new tile)' if first_time_here else '(revisit)'}")

        if not m.read_mode(master) == "GUIDED":
            m.set_mode(master, "GUIDED")
        m.send_guided_waypoint(master, lat, lon)

        # Wait until arrived or timeout
        t0 = time.time()
        while not m.is_at_wp(master, lat, lon):
            if time.time() - t0 > max_wp_time_s:
                print(f"[COVER] WARNING: WP timeout after {max_wp_time_s} sec, continuing.")
                break
            time.sleep(0.2)

        # Mark visited *after* arrival attempt
        print(f"[COVER] Arrived at tile center.")
        if tile_key != (-1, -1):
            visited.add(tile_key)

        # Loiter only on first visit
        if first_time_here:
            m.set_mode(master, "LOITER")
            print(f"[COVER] Loitering for {loiter_sec} sec...")
            time.sleep(loiter_sec)
        else:
            print("[COVER] Skipping loiter (already visited).")

    # Finish
    if rtl_at_end:
        print("[FC] Switching to RTL.")
        m.set_mode(master, "RTL")
    else:
        print("[FC] Coverage complete. Disarming.")
        m.disarm(master)
    print("[COVER] Done.")


# -------------------- CLI --------------------
def parse_args():
    p = argparse.ArgumentParser(description="Coverage runner for ArduRover SITL")
    p.add_argument("--fen", default="taka_lake.fen", help="Path to geofence .fen file (lat lon per line)")
    p.add_argument("--tile-size-lat", type=float, default=0.00015, help="Tile size in degrees latitude")
    p.add_argument("--tile-size-lon", type=float, default=None, help="Tile size in degrees longitude (default = same as lat)")
    p.add_argument("--tile-size-m", type=float, default=10, help="Tile size in meters (overrides degree settings)")
    p.add_argument("--coverage-threshold", type=float, default=0.75, help="Fraction of tile that must be inside geofence")
    p.add_argument("--samples-per-side", type=int, default=5, help="Sampling density per side for coverage estimation")
    p.add_argument("--wp-accept-m", type=float, default=1, help="Acceptance radius (m) for tile center")
    p.add_argument("--loiter-sec", type=float, default=1.0, help="Seconds to pause at each tile center")
    p.add_argument("--loiter-radius", type=int, default=5, help="Loitering radius (m) at each tile center")
    p.add_argument("--mavproxy", action="store_true", help="Connect via MAVProxy UDP (else serial)")
    p.add_argument("--wp_speed", type=float, default=1.0, help="Speed (m/s) for guided waypoints")
    p.add_argument("--max-wp-time-s", type=float, default=1.0, help="Per-WP timeout (s) before continuing anyway")
    p.add_argument("--no-rtl", action="store_true", help="Do not RTL; disarm at the end instead")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_coverage(
        fen_path=args.fen,
        tile_size_lat=args.tile_size_lat,
        tile_size_lon=args.tile_size_lon,
        coverage_threshold=args.coverage_threshold,
        samples_per_side=args.samples_per_side,
        wp_accept_m=args.wp_accept_m,
        loiter_sec=args.loiter_sec,
        loiter_radius=args.loiter_radius,
        mavproxy_on=args.mavproxy,
        wp_speed=args.wp_speed,
        max_wp_time_s=args.max_wp_time_s,
        rtl_at_end=(not args.no_rtl),
    )
