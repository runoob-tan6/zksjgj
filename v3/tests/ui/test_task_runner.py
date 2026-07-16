from threading import Event

import borehole.ui.main_window as main_window_module
from borehole.application.task_runner import TaskRunner
from borehole.ui.main_window import MainWindow


def test_task_runner_delivers_success_and_releases_thread(qtbot) -> None:
    runner = TaskRunner()
    results: list[int] = []

    assert runner.start(lambda: 42, results.append, lambda _error: None)
    qtbot.waitUntil(lambda: not runner.running)

    assert results == [42]
    assert runner.worker is None


def test_task_runner_delivers_failure_and_releases_thread(qtbot) -> None:
    runner = TaskRunner()
    errors: list[str] = []

    def fail() -> None:
        raise RuntimeError("task failed")

    assert runner.start(fail, lambda _result: None, errors.append)
    qtbot.waitUntil(lambda: not runner.running)

    assert errors == ["task failed"]
    assert runner.worker is None


def test_task_runner_rejects_overlapping_task(qtbot) -> None:
    runner = TaskRunner()
    release = Event()
    calls: list[str] = []

    def wait_for_release() -> str:
        release.wait(timeout=2)
        calls.append("first")
        return "done"

    assert runner.start(wait_for_release, lambda _result: None, lambda _error: None)
    assert not runner.start(lambda: calls.append("second"), lambda _result: None, lambda _error: None)
    release.set()
    qtbot.waitUntil(lambda: not runner.running)

    assert calls == ["first"]


def test_main_window_centralizes_busy_state_and_rejects_overlap(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(main_window_module, "load_last_project", lambda: None)
    window = MainWindow()
    qtbot.addWidget(window)
    release = Event()

    assert window._start_task(lambda: release.wait(timeout=2), lambda _result: None, lambda _error: None)
    assert window._busy
    assert not window._start_task(lambda: None, lambda _result: None, lambda _error: None)

    release.set()
    qtbot.waitUntil(lambda: not window._busy)
    assert window._worker is None

    window.close()
