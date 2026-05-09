"""Tests for quadkey module."""
from poc_cesg_poi_search.quadkey import lonlat_to_tile, tile_to_quadkey, lonlat_to_quadkey


def test_lonlat_to_tile_tokyo():
    x, y = lonlat_to_tile(139.767, 35.681, 12)
    assert isinstance(x, int)
    assert isinstance(y, int)
    assert x > 0
    assert y > 0


def test_tile_to_quadkey_length():
    qk = tile_to_quadkey(3632, 1612, 12)
    assert len(qk) == 12
    assert all(c in "0123" for c in qk)


def test_lonlat_to_quadkey_default_zoom():
    qk = lonlat_to_quadkey(139.767, 35.681)
    assert len(qk) == 12


def test_quadkey_consistency():
    lon, lat = 139.767, 35.681
    x, y = lonlat_to_tile(lon, lat, 12)
    qk1 = tile_to_quadkey(x, y, 12)
    qk2 = lonlat_to_quadkey(lon, lat, 12)
    assert qk1 == qk2


def test_antimeridian_boundary():
    x, y = lonlat_to_tile(-180.0, 0.0, 1)
    assert x == 0


def test_equator():
    x1, y1 = lonlat_to_tile(0, 0.001, 1)
    x2, y2 = lonlat_to_tile(0, -0.001, 1)
    assert y1 <= y2
