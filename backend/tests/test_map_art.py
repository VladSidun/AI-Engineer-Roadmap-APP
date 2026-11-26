from itertools import combinations, pairwise
from xml.etree import ElementTree

from app.config import ROOT
from app.domain.content import Content, Point


def side(start: Point, end: Point, point: Point) -> int:
    return (end[0] - start[0]) * (point[1] - start[1]) - (end[1] - start[1]) * (point[0] - start[0])


def inside(point: Point, coastline: list[Point]) -> bool:
    x, y = point
    crossings = sum(
        (a[1] > y) != (b[1] > y) and x < a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1])
        for a, b in pairwise([*coastline, coastline[0]])
    )
    return bool(crossings % 2)


def test_campaign_coasts_are_separate_and_connected_by_bridges() -> None:
    regions = Content().layout.regions
    for left, right in combinations(regions, 2):
        assert not inside(left.polygon[0], right.polygon), (left.id, right.id)
        assert not inside(right.polygon[0], left.polygon), (left.id, right.id)
        for a, b in pairwise([*left.polygon, left.polygon[0]]):
            for c, d in pairwise([*right.polygon, right.polygon[0]]):
                assert not (side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0), (left.id, right.id)

    terrain = ElementTree.parse(ROOT / "frontend/public/assets/atlas-terrain.svg")
    bridges = terrain.findall(".//*[@id='campaign-bridges']/*")
    assert [(bridge.attrib["data-from"], bridge.attrib["data-to"]) for bridge in bridges] == [
        (left.id, right.id) for left, right in pairwise(regions)
    ]
