from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    sys.path.insert(0, str(project_root / "src"))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    import borehole.ui.main_window as main_window_module
    from borehole.ui.main_window import MainWindow

    main_window_module.load_last_project = lambda: None
    app = QApplication([])
    window = MainWindow()
    window.move(0, 0)
    window.show()
    app.processEvents()
    output.mkdir(parents=True, exist_ok=True)
    for index in range(window._tabs.count()):
        window._tabs.setCurrentIndex(index)
        app.processEvents()
        if not window.grab().save(str(output / f"tab-{index}.png")):
            return 1
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
