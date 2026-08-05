from pathlib import Path

from borehole.domain.enums import HoleType
from borehole.domain.models import Borehole
from borehole.ui.undo_controller import UndoController


def test_undo_controller_migrates_and_removes_prefix_key() -> None:
    borehole = Borehole("ZK1", Path("/tmp"), HoleType.ZK)
    controller = UndoController()
    manager = controller.get(borehole)

    controller.migrate("ZK1", "ZK2")
    controller.remove("ZK2")

    assert manager is not None
    assert controller.managers == {}
