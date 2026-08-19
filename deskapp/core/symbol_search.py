"""Thread-safe wrapper around webapp.search.

Uses the canonical PySide6 ``QThread + Worker QObject`` pattern. The
worker lives on the worker thread. The worker emits ``finished`` /
``failed`` from the worker thread; with ``Qt.QueuedConnection`` those
signals are delivered to slots on the GUI thread (the main thread).

Critical detail: ``QThread`` is a plain ``QObject`` — it is NOT managed
by ``QThreadPool`` like ``QRunnable`` is. We must hold a Python reference
to the thread and worker until they finish, otherwise the GC will reap
them with the worker thread still running ("QThread: Destroyed while
thread is still running"). The module-level ``_keep_alive`` list holds
such references; the cleanup lambda removes pairs once the thread has
fully exited.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot


# Hold strong refs to QThread/Worker pairs so Python GC doesn't reap them
# while the worker thread is still running.
_keep_alive: list[tuple[QThread, "_SearchWorker"]] = []


class _SearchWorker(QObject):
    """Performs the search on the worker thread."""

    finished = Signal(list)   # list[dict]
    failed = Signal(str)

    def __init__(self, query: str, limit: int) -> None:
        super().__init__()
        self.query = query
        self.limit = limit

    @Slot()
    def run(self) -> None:
        try:
            from webapp.search import search as webapp_search
            hits = webapp_search(self.query, limit=self.limit)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.finished.emit(hits)


def search_async(query: str, limit: int,
                 on_results, on_error=None) -> None:
    """Fire-and-forget search. ``on_results(list[dict])`` is invoked on the GUI thread.

    Each call spawns a fresh QThread; the thread is cleaned up automatically
    once the worker emits ``finished`` or ``failed``.
    """
    thread = QThread()
    worker = _SearchWorker(query, limit)
    worker.moveToThread(thread)

    # Run worker when the thread starts
    thread.started.connect(worker.run)

    # QueuedConnection ensures slots run on the GUI thread (the receiver's
    # thread), not on the worker thread.
    worker.finished.connect(on_results, Qt.QueuedConnection)
    worker.finished.connect(thread.quit, Qt.QueuedConnection)
    if on_error is not None:
        worker.failed.connect(on_error, Qt.QueuedConnection)
        worker.failed.connect(thread.quit, Qt.QueuedConnection)

    # Drop the keep-alive reference once the thread has fully exited.
    key = (thread, worker)

    def _drop_ref() -> None:
        try:
            _keep_alive.remove(key)
        except ValueError:
            pass

    # Once the thread has fully exited, clean up the QObjects.
    # `thread.finished` fires after the event loop ends, so we never call
    # wait() ourselves (which would deadlock if invoked on the worker thread).
    thread.finished.connect(_drop_ref)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)

    # Hold reference until cleanup runs
    _keep_alive.append(key)

    thread.start()
