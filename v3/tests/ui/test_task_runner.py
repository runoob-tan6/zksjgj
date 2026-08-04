from threading import Event

import borehole.application.task_runner as task_runner_module
import borehole.ui.main_window as main_window_module
from borehole.application.task_runner import TaskRunner
from borehole.ui.main_window import MainWindow


def test_task_runner_delivers_success_and_releases_thread(qtbot) -> None:
    for expected in range(10):
        runner = TaskRunner()
        results: list[int] = []

        assert runner.start(lambda: expected, results.append, lambda _error: None)
        worker = runner.worker
        assert worker is not None
        assert worker.wait(2000)

        assert runner.running
        qtbot.waitUntil(lambda: not runner.running)

        assert results == [expected]
        assert runner.worker is None


def test_task_runner_delivers_failure_and_releases_thread(qtbot) -> None:
    for attempt in range(10):
        runner = TaskRunner()
        errors: list[str] = []

        def fail() -> None:
            raise RuntimeError(f"task failed {attempt}")

        assert runner.start(fail, lambda _result: None, errors.append)
        worker = runner.worker
        assert worker is not None
        assert worker.wait(2000)

        assert runner.running
        qtbot.waitUntil(lambda: not runner.running)

        assert errors == [f"task failed {attempt}"]
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


def test_task_runner_logs_background_traceback(qtbot, monkeypatch) -> None:
    runner = TaskRunner()
    logged: list[str] = []
    monkeypatch.setattr(task_runner_module.logger, "exception", lambda message: logged.append(message))

    def fail() -> None:
        raise RuntimeError("task failed")

    assert runner.start(fail, lambda _result: None, lambda _error: None)
    qtbot.waitUntil(lambda: not runner.running)

    assert logged == ["Background task failed"]


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
