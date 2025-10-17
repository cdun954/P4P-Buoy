from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Dict, Deque
from collections import deque
import math
import json
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon as MplPolygon

Coordinate = Tuple[float, float]  # (lat, lon)
Bounds = Tuple[float, float, float, float]  # (min_lat, min_lon, max_lat, max_lon)

# -------------------- Geometry helpers --------------------
def point_in_polygon(point: Coordinate, polygon: Sequence[Coordinate]) -> bool:
    """Ray-casting test (lat,lon order)."""
    x, y = point
    inside = False
    verts = list(polygon)
    if len(verts) < 3:
        return False
    for (x1, y1), (x2, y2) in zip(verts, verts[1:] + verts[:1]):
        if ((y1 > y) != (y2 > y)):
            xinters = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1
            if x < xinters:
                inside = not inside
    return inside

# ---- NZ-accurate geodesy helpers (WGS-84) ----
# Source: standard m/deg formulas with cos(phi) corrections; ~sub-meter accuracy at NZ latitudes.
# Good for local gridding & planning without extra deps.
WGS84_A = 6378137.0          # major axis
WGS84_B = 6356752.314245     # minor axis
WGS84_E2 = 1 - (WGS84_B**2 / WGS84_A**2)

def meters_per_deg_lat(phi_rad: float) -> float:
    """Meters per degree latitude at latitude phi (radians)."""
    # Using a high-accuracy series approximation
    sin2 = math.sin(phi_rad) ** 2
    # meridional radius of curvature
    M = (WGS84_A * (1 - WGS84_E2)) / (1 - WGS84_E2 * sin2) ** 1.5
    return (math.pi / 180.0) * M

def meters_per_deg_lon(phi_rad: float) -> float:
    """Meters per degree longitude at latitude phi (radians)."""
    sin2 = math.sin(phi_rad) ** 2
    # prime vertical radius of curvature
    N = WGS84_A / math.sqrt(1 - WGS84_E2 * sin2)
    return (math.pi / 180.0) * N * math.cos(phi_rad)

def deg_lat_per_meter(phi_rad: float) -> float:
    return 1.0 / meters_per_deg_lat(phi_rad)

def deg_lon_per_meter(phi_rad: float) -> float:
    mpd_lon = meters_per_deg_lon(phi_rad)
    # protect against cos ~ 0, but NZ is far from poles
    return 0.0 if mpd_lon == 0 else 1.0 / mpd_lon


# --- NEW: coverage helpers ---
def fraction_rect_inside_polygon(bounds: Bounds, polygon: Sequence[Coordinate], samples_per_side: int = 5) -> float:
    """Estimate what fraction of a rectangle's area lies within a polygon by uniform sampling."""
    min_lat, min_lon, max_lat, max_lon = bounds
    s = max(2, int(samples_per_side))
    inside = 0
    total = s * s
    dlat = (max_lat - min_lat) / s
    dlon = (max_lon - min_lon) / s
    # sample at cell-centered points
    for i in range(s):
        lat = min_lat + (i + 0.5) * dlat
        for j in range(s):
            lon = min_lon + (j + 0.5) * dlon
            if point_in_polygon((lat, lon), polygon):
                inside += 1
    return inside / total


def tile_passes(bounds: Bounds, polygon: Sequence[Coordinate],
                coverage_threshold: float, samples_per_side: int) -> bool:
    """Return True if estimated coverage >= threshold. 0.0 acts like center-only."""
    thr = max(0.0, min(1.0, coverage_threshold))
    if thr <= 0.0:
        # center-only for speed/compat
        min_lat, min_lon, max_lat, max_lon = bounds
        center = ((min_lat + max_lat) / 2.0, (min_lon + max_lon) / 2.0)
        return point_in_polygon(center, polygon)
    frac = fraction_rect_inside_polygon(bounds, polygon, samples_per_side)
    return frac >= thr


# -------------------- Grid structures --------------------
@dataclass(frozen=True)
class GridTile:
    row: int
    col: int
    center: Coordinate
    bounds: Bounds

class GridMap:
    def __init__(self, tiles: List[List[Optional[GridTile]]], geofence: Sequence[Coordinate]):
        self.tiles = tiles
        self.geofence = list(geofence)
        # Precompute lawnmower order as (row, col) pairs for existing tiles only
        order: List[Tuple[int, int]] = []
        for r, row in enumerate(self.tiles):
            idxs = [c for c, t in enumerate(row) if t is not None]
            if r % 2 == 1:
                idxs.reverse()
            order.extend([(r, c) for c in idxs])
        self._lawnmower_order = order

    def iter_tiles(self) -> List[GridTile]:
        return [t for row in self.tiles for t in row if t is not None]

    def get_tile(self, r: int, c: int) -> Optional[GridTile]:
        if r < 0 or r >= len(self.tiles):
            return None
        row = self.tiles[r]
        if c < 0 or c >= len(row):
            return None
        return row[c]

    def neighbors4(self, r: int, c: int) -> List[GridTile]:
        out: List[GridTile] = []
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            t = self.get_tile(r+dr, c+dc)
            if t is not None:
                out.append(t)
        return out

def build_grid_map(
    geofence: Sequence[Coordinate],
    tile_size_lat: float,
    tile_size_lon: Optional[float] = None,
    coverage_threshold: float = 0.0,   # NEW: fraction of tile that must be inside
    samples_per_side: int = 5          # NEW: sampling density per tile side
) -> GridMap:
    """Cover the geofence bbox with a grid. Keep tiles meeting coverage (0.0 => center-only)."""
    if len(geofence) < 3:
        raise ValueError("Geofence must contain at least three vertices")

    tile_size_lon = tile_size_lat if tile_size_lon is None else tile_size_lon
    lats = [lat for lat, _ in geofence];  lons = [lon for _, lon in geofence]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    rows = max(1, math.ceil((max_lat - min_lat) / tile_size_lat))
    cols = max(1, math.ceil((max_lon - min_lon) / tile_size_lon))
    lat_step = (max_lat - min_lat) / rows
    lon_step = (max_lon - min_lon) / cols

    tiles: List[List[Optional[GridTile]]] = []
    for r in range(rows):
        row_tiles: List[Optional[GridTile]] = []
        for c in range(cols):
            cell_min_lat = min_lat + r * lat_step
            cell_max_lat = cell_min_lat + lat_step
            cell_min_lon = min_lon + c * lon_step
            cell_max_lon = cell_min_lon + lon_step
            bounds = (cell_min_lat, cell_min_lon, cell_max_lat, cell_max_lon)
            center = ((cell_min_lat + cell_max_lat)/2.0, (cell_min_lon + cell_max_lon)/2.0)

            if tile_passes(bounds, geofence, coverage_threshold, samples_per_side):
                row_tiles.append(GridTile(r, c, center, bounds))
            else:
                row_tiles.append(None)
        tiles.append(row_tiles)

    if not any(t is not None for row in tiles for t in row):
        raise ValueError("Geofence too small or threshold too high; no tiles kept.")
    return GridMap(tiles=tiles, geofence=geofence)

def build_grid_map_meters(
    geofence: Sequence[Coordinate],
    tile_size_m: float,
    coverage_threshold: float = 0.0,
    samples_per_side: int = 5
) -> GridMap:
    """
    Build a grid of ~square tiles in meters over the geofence bbox.
    Square size is tile_size_m x tile_size_m in local ground distance.
    Accurate for NZ using WGS-84 per-row degree step conversion.

    coverage_threshold:
        0.0 -> center-only inclusion (fast)
        (0,1] -> require that fraction of tile area be inside polygon (via sampling)
    """
    if len(geofence) < 3:
        raise ValueError("Geofence must contain at least three vertices")

    lats = [lat for lat, _ in geofence]
    lons = [lon for _, lon in geofence]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    # Use mid-latitude for initial sizing decisions
    mid_lat = 0.5 * (min_lat + max_lat)
    mid_phi = math.radians(mid_lat)

    # Compute overall N-S and E-W extents in meters using local m/deg at mid-lat
    ns_m = abs((max_lat - min_lat) * meters_per_deg_lat(mid_phi))
    # For E-W, use longitude span converted at mid-lat
    ew_m = abs((max_lon - min_lon) * meters_per_deg_lon(mid_phi))

    # Min-guard if user gives tiny geofence
    if ns_m < 1e-6 or ew_m < 1e-6:
        raise ValueError("Geofence bbox is degenerate or extremely small.")

    rows = max(1, math.ceil(ns_m / tile_size_m))
    cols = max(1, math.ceil(ew_m / tile_size_m))

    tiles: List[List[Optional[GridTile]]] = []
    # We'll ascend in latitude; compute per-row lat step in degrees at the row latitude
    lat_cursor = min_lat
    for r in range(rows):
        # Use the *current* row's latitude to compute how many degrees of lat correspond to tile_size_m
        phi_row = math.radians(lat_cursor)
        dlat_deg = tile_size_m * deg_lat_per_meter(phi_row)

        # Guard if deg step underflows (won't happen in NZ, but be safe)
        if dlat_deg <= 0:
            dlat_deg = tile_size_m * deg_lat_per_meter(mid_phi)

        row_min_lat = lat_cursor
        row_max_lat = row_min_lat + dlat_deg
        row_center_lat = 0.5 * (row_min_lat + row_max_lat)
        phi_center = math.radians(row_center_lat)

        # For this row, compute how many degrees of longitude equal tile_size_m at the row center
        dlon_deg = tile_size_m * deg_lon_per_meter(phi_center)
        if dlon_deg <= 0:
            dlon_deg = tile_size_m * deg_lon_per_meter(mid_phi)

        # Now lay out columns across the fixed lon range using constant dlon for this row
        row_tiles: List[Optional[GridTile]] = []
        lon_cursor = min_lon
        for c in range(cols):
            cell_min_lat = row_min_lat
            cell_max_lat = row_max_lat
            cell_min_lon = lon_cursor
            cell_max_lon = cell_min_lon + dlon_deg

            bounds = (cell_min_lat, cell_min_lon, cell_max_lat, cell_max_lon)
            center = ((cell_min_lat + cell_max_lat) / 2.0, (cell_min_lon + cell_max_lon) / 2.0)

            if tile_passes(bounds, geofence, coverage_threshold, samples_per_side):
                row_tiles.append(GridTile(r, c, center, bounds))
            else:
                row_tiles.append(None)

            lon_cursor = cell_max_lon
        tiles.append(row_tiles)

        lat_cursor = row_max_lat

    if not any(t is not None for row in tiles for t in row):
        raise ValueError("Geofence too small vs tile size/threshold; no tiles kept.")
    return GridMap(tiles=tiles, geofence=geofence)



# -------------------- Lawn-mower path (start nearest to hint) --------------------
def _grid_index_map(g: GridMap) -> Dict[Tuple[int,int], GridTile]:
    return {(t.row, t.col): t for t in g.iter_tiles()}

def _bfs_path(g: GridMap, start: GridTile, goal: GridTile) -> List[GridTile]:
    """Shortest path on 4-neighbor grid across existing tiles. Returns list including start & goal."""
    if start == goal:
        return [start]
    q: Deque[Tuple[int,int]] = deque()
    came: Dict[Tuple[int,int], Optional[Tuple[int,int]]] = {}
    s = (start.row, start.col)
    t = (goal.row, goal.col)
    q.append(s)
    came[s] = None
    while q:
        r, c = q.popleft()
        for nb in g.neighbors4(r, c):
            key = (nb.row, nb.col)
            if key in came:
                continue
            came[key] = (r, c)
            if key == t:
                # reconstruct
                path: List[Tuple[int,int]] = [t]
                while path[-1] is not None:
                    prev = came[path[-1]]
                    if prev is None:
                        break
                    path.append(prev)
                path.reverse()
                idx = _grid_index_map(g)
                return [idx[k] for k in [s] + path[1:]]
            q.append(key)
    return [start]

def _nearest_tile_to_point(g: GridMap, p: Coordinate) -> Optional[GridTile]:
    """Euclidean in (lat,lon)."""
    if not g._lawnmower_order:
        return None
    best = None
    best_d2 = float("inf")
    for t in g.iter_tiles():
        dlat = t.center[0] - p[0]
        dlon = t.center[1] - p[1]
        d2 = dlat*dlat + dlon*dlon
        if d2 < best_d2:
            best_d2 = d2
            best = t
    return best

def plan_lawnmower_path(g: GridMap, start_hint: Optional[Coordinate] = None) -> List[Coordinate]:
    """Continuous lawnmower route that stays inside by walking the grid graph.
       If start_hint is given, begin from the tile whose CENTER is nearest to that hint."""
    order = g._lawnmower_order[:]
    if not order:
        return []

    idx = _grid_index_map(g)

    # Rotate order so the nearest tile to start_hint is first
    if start_hint is not None:
        nearest = _nearest_tile_to_point(g, start_hint)
        if nearest is not None:
            try:
                k = order.index((nearest.row, nearest.col))
                order = order[k:] + order[:k]
            except ValueError:
                pass

    seq_tiles: List[GridTile] = [idx[order[0]]]
    for a_key, b_key in zip(order, order[1:]):
        a = idx[a_key]
        b = idx[b_key]
        if abs(a.row - b.row) + abs(a.col - b.col) == 1:
            seq_tiles.append(b)
        else:
            seq_tiles.extend(_bfs_path(g, a, b)[1:])

    return [t.center for t in seq_tiles]

# -------------------- Visualisation --------------------
def plot_grid_and_path(
    g: GridMap,
    path: Optional[List[Coordinate]] = None,
    title: Optional[str] = None,
    start_dot: Optional[Coordinate] = None,
    end_dot: Optional[Coordinate] = None,
):
    fig, ax = plt.subplots()

    # Draw grid tiles as thin black outlines (no fill)
    for t in g.iter_tiles():
        min_lat, min_lon, max_lat, max_lon = t.bounds
        rect = Rectangle((min_lon, min_lat), max_lon - min_lon, max_lat - min_lat,
                         fill=False, edgecolor="black", linewidth=0.6)
        ax.add_patch(rect)

    # Geofence outline: bright red dashed/dotted line
    poly = MplPolygon([(lon, lat) for (lat, lon) in g.geofence], closed=True,
                      fill=False, edgecolor="#E20000", linewidth=1.8, linestyle="--")
    ax.add_patch(poly)

    # Path overlay in lilac
    if path and len(path) >= 2:
        xs = [lon for (lat, lon) in path]
        ys = [lat for (lat, lon) in path]
        ax.plot(xs, ys, '-', linewidth=1.6, color="#C8A2C8")  # lilac

    # Start (green) and End (red) dots at tile centers
    if start_dot is not None:
        ax.scatter([start_dot[1]], [start_dot[0]], s=30, c="#00C853", zorder=5)  # green
    if end_dot is not None:
        ax.scatter([end_dot[1]], [end_dot[0]], s=30, c="#E53935", zorder=5)      # red

    lats = [lat for lat, _ in g.geofence]
    lons = [lon for _, lon in g.geofence]
    ax.set_xlim(min(lons), max(lons))
    ax.set_ylim(min(lats), max(lats))
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect('equal', adjustable='box')
    ax.set_title(title or "Grid Decomposition and Path Planning of Geofenced Environment")
    plt.tight_layout()
    plt.show()
    return fig, ax

# -------------------- I/O helpers --------------------
def read_poly_file(path: str) -> List[Coordinate]:
    with open(path, 'r', encoding='utf-8') as f:
        lines = [ln.strip() for ln in f]
    coords: List[Coordinate] = []
    for ln in lines:
        if not ln or ln.startswith('#'):
            continue
        lat, lon = map(float, ln.split())
        coords.append((lat, lon))
    return coords

def export_state(g: GridMap) -> Dict:
    return {
        "geofence": g.geofence,
        "tiles": [
            [None if t is None else {
                "row": t.row, "col": t.col, "center": t.center, "bounds": t.bounds
            } for t in row]
            for row in g.tiles
        ]
    }

def grid_from_state(state: Dict) -> GridMap:
    geofence = [(float(lat), float(lon)) for lat, lon in state["geofence"]]
    tiles_state = state["tiles"]
    tiles: List[List[Optional[GridTile]]] = []
    for r, row_state in enumerate(tiles_state):
        row: List[Optional[GridTile]] = []
        for c, ts in enumerate(row_state):
            if ts is None:
                row.append(None)
            else:
                t = GridTile(
                    row=int(ts["row"]), col=int(ts["col"]),
                    center=tuple(ts["center"]), bounds=tuple(ts["bounds"])
                )
                row.append(t)
        tiles.append(row)
    return GridMap(tiles, geofence)

# -------------------- Minimal demo --------------------
if __name__ == "__main__":
    # Example: replace with your path
    path = "taka_lake.fen"
    geofence = read_poly_file(path)

    grid = build_grid_map_meters(geofence, tile_size_m=15, coverage_threshold=0.65)  # adjust as needed
    start_hint = geofence[0]  # first coordinate in the file

    route = plan_lawnmower_path(grid, start_hint)

    start_tile = _nearest_tile_to_point(grid, start_hint)
    start_center = start_tile.center if start_tile else None
    end_center = route[-1] if route else None

    plot_grid_and_path(
        grid, route,
        title="Grid Decomposition and Path Planning of Geofenced Environment",
        start_dot=start_center,
        end_dot=end_center,
    )
