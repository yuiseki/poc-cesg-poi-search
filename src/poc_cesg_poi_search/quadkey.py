"""Quadkey utilities for spatial shard key generation."""
import math


def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    """Convert lon/lat to tile x/y at zoom level z (Slippy Map / XYZ)."""
    lat_rad = math.radians(lat)
    n = 2**z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    x = max(0, min(n - 1, x))
    y = max(0, min(n - 1, y))
    return x, y


def tile_to_quadkey(x: int, y: int, z: int) -> str:
    """Convert tile x/y/z to quadkey string."""
    quadkey = []
    for i in range(z, 0, -1):
        digit = 0
        mask = 1 << (i - 1)
        if x & mask:
            digit += 1
        if y & mask:
            digit += 2
        quadkey.append(str(digit))
    return "".join(quadkey)


def lonlat_to_quadkey(lon: float, lat: float, z: int = 12) -> str:
    """Convert lon/lat to quadkey at zoom level z."""
    x, y = lonlat_to_tile(lon, lat, z)
    return tile_to_quadkey(x, y, z)
