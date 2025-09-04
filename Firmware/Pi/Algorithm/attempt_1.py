import matplotlib.pyplot as plt
from shapely.geometry import Polygon, box
from shapely.ops import transform
from shapely.prepared import prep
from shapely.geometry import Point
from collections import deque
import time
import matplotlib.cm as cm
from matplotlib import colors 
import numpy as np
import pyproj
from collections import defaultdict

# Works perfectly
def read_geofence(poly_file="Lake_poly.poly"):
    """Reads a .poly file and returns a Shapely polygon in meters."""
    poly_latlon = []
    with open(poly_file, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                lon, lat = map(float, line.split())
                poly_latlon.append((lon, lat))

    polygon_ll = Polygon([(lon, lat) for lat, lon in poly_latlon])
    proj_fwd = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform
    polygon_m = transform(proj_fwd, polygon_ll).simplify(1, preserve_topology=True)

    if polygon_m.is_empty:
        raise ValueError("Simplified polygon is empty — try reducing simplify tolerance.")
    if polygon_m.geom_type == "MultiPolygon":
        polygon_m = max(polygon_m.geoms, key=lambda p: p.area)

    return polygon_m

# Works perfectly
def decompose_geofence(polygon_m, cell_size=50):
    """
    Decomposes the polygon into a structured 2D grid.
    Returns:
        - grid_cells_2d: 2D numpy array of Shapely cells (None for gaps)
        - grid_centers_2d: 2D numpy array of (lat, lon) centers
    """
    proj_back = pyproj.Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True).transform
    prepared_poly = prep(polygon_m)
    minx, miny, maxx, maxy = polygon_m.bounds

    cell_dict = defaultdict(dict)  # {y_idx: {x_idx: (cell, (lat, lon))}}

    x = minx
    while x < maxx:
        y = miny
        while y < maxy:
            center_x = x + cell_size / 2
            center_y = y + cell_size / 2
            center_point = Point(center_x, center_y)

            if prepared_poly.contains(center_point):
                cell = box(x, y, x + cell_size, y + cell_size)
                lon, lat = proj_back(center_x, center_y)
                x_idx = round(center_x / cell_size)
                y_idx = round(center_y / cell_size)
                cell_dict[y_idx][x_idx] = (cell, (lat, lon))
            y += cell_size
        x += cell_size

    # Sort and create 2D numpy arrays
    sorted_y = sorted(cell_dict.keys(), reverse=True)  # top to bottom
    sorted_x = sorted(set().union(*[row.keys() for row in cell_dict.values()]))  # left to right

    grid_cells_2d = []
    grid_centers_2d = []
    for y in sorted_y:
        row_cells = []
        row_centers = []
        for x in sorted_x:
            if x in cell_dict[y]:
                cell, center = cell_dict[y][x]
                row_cells.append(cell)
                row_centers.append(center)
            else:
                row_cells.append(None)
                row_centers.append(None)
        grid_cells_2d.append(row_cells)
        grid_centers_2d.append(row_centers)

    return np.array(grid_cells_2d, dtype=object), np.array(grid_centers_2d, dtype=object)




def plot_decomposition(polygon_m, grid_cells_2d, path_coords=None):
    """
    Plots the polygon, grid cells, and an optional path overlaid on top.

    Args:
        polygon_m: Shapely polygon (projected)
        grid_cells_2d: 2D array of Shapely cells (or None)
        path_coords: optional list of (lat, lon) coordinates in order of traversal
    """
    fig, ax = plt.subplots(figsize=(10, 10))

    # Plot polygon boundary in blue
    x, y = polygon_m.exterior.xy
    ax.plot(x, y, 'b-', linewidth=2, label='Polygon Boundary')

    # Plot grid cell outlines in black
    for row in grid_cells_2d:
        for cell in row:
            if cell:
                gx, gy = cell.exterior.xy
                ax.plot(gx, gy, 'k-', linewidth=0.3)

    # Plot traversal path if provided
    if path_coords:
        transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        path_xy = [transformer.transform(lon, lat) for lat, lon in path_coords]

        x_vals, y_vals = zip(*path_xy)
        ax.plot(x_vals, y_vals, 'r-', linewidth=1.5, label='Traversal Path')
        ax.plot(x_vals[0], y_vals[0], 'go', markersize=6, label='Start')
        ax.plot(x_vals[-1], y_vals[-1], 'ro', markersize=6, label='End')

    ax.set_aspect('equal')
    ax.set_title("Geofence Grid and Traversal Path")
    ax.legend()
    plt.show()






if __name__ == "__main__":
    start = time.time()
    poly = read_geofence()
    cells, centers = decompose_geofence(poly)
    path = perimeter_then_lawnmower_fixed(centers)
    end = time.time()

    print(f"Execution time: {end - start:.2f} seconds")
    print(f"Total grid cells: {len(cells)}")
    plot_decomposition(poly, cells, path)
