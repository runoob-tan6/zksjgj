from pathlib import Path

from borehole.domain.enums import HoleType
from borehole.domain.models import BasicLayer, Borehole
from borehole.infrastructure.file_writer import render_h_file


def make_borehole(layers: list[BasicLayer]) -> Borehole:
    return Borehole(prefix="ZK1", folder=Path("."), hole_type=HoleType.ZK, layers=layers)


def test_render_h_file_omits_layers_without_complete_descriptions() -> None:
    borehole = make_borehole(
        [
            BasicLayer(bottom_depth="5", description="黏土"),
            BasicLayer(bottom_depth="10", description=""),
            BasicLayer(bottom_depth="15", description="砂岩"),
        ]
    )

    assert render_h_file(borehole) == "#5\n黏土\n#15\n砂岩\n★"


def test_render_h_file_returns_only_end_mark_without_complete_descriptions() -> None:
    borehole = make_borehole(
        [
            BasicLayer(bottom_depth="5", description=""),
            BasicLayer(bottom_depth="", description="孤立描述"),
            BasicLayer(bottom_depth="  ", description="  "),
        ]
    )

    assert render_h_file(borehole) == "★"


def test_render_h_file_strips_surrounding_whitespace() -> None:
    borehole = make_borehole([BasicLayer(bottom_depth=" 5.0 ", description="  粉质黏土  ")])

    assert render_h_file(borehole) == "#5.0\n粉质黏土\n★"
