"""Route all py_mini_racer V8 calls through a dedicated worker thread.

Why: V8 isolates are bound to the OS thread that created them. Calling into
the same isolate from a different thread blocks forever on absl's
``AbslInternalPerThreadSemWait``. langgraph's ``ToolNode`` runs tool calls in
a ``ThreadPoolExecutor``, so any AkShare endpoint that uses
``py_mini_racer.MiniRacer`` (Sina K-line, cninfo, etc.) deadlocks the moment
a worker thread tries to execute JS.

Strategy: a single background thread owns the V8 isolate. All callers
submit ``(callable, args, kwargs)`` jobs to a queue and wait for the result.
Jobs execute strictly serially in the worker, so the isolate never sees a
cross-thread call. V8 is created exactly once, in this worker.
"""
from __future__ import annotations

import queue
import threading
from typing import Any, Callable

try:
    import py_mini_racer  # noqa: F401
except Exception:  # pragma: no cover
    py_mini_racer = None  # type: ignore[assignment]


_WORKER: "_Worker | None" = None
_PATCHED = False


class _Worker:
    """Owns the V8 isolate and executes JS jobs one at a time."""

    def __init__(self) -> None:
        self._q: "queue.Queue[Any]" = queue.Queue()
        self._thread = threading.Thread(
            target=self._loop, name="py_mini_racer-worker", daemon=True
        )
        self._thread.start()
        # Block until the worker confirms the real MiniRacer is up. This
        # guarantees the isolate was created on the worker thread we own.
        ready_evt = threading.Event()
        self._q.put(("__init__", ready_evt))
        ready_evt.wait(timeout=60)

    def _loop(self) -> None:
        # Create the real MiniRacer on this thread; V8 binds the isolate to
        # this OS thread for the rest of the process lifetime.
        mr = py_mini_racer.__dict__["_OrigMiniRacer"]()  # type: ignore[index]
        # Warm-up so V8's per-thread pool is initialised.
        mr.execute("1+1")

        while True:
            item = self._q.get()
            if item is None:
                self._q.task_done()
                return
            kind, payload = item
            try:
                if kind == "__init__":
                    payload.set()
                elif kind == "call":
                    fn, args, kwargs, holder = payload
                    holder["__result__"] = fn(mr, *args, **kwargs)
            except Exception as e:
                if kind == "call":
                    payload[3]["__error__"] = e  # type: ignore[index]
            finally:
                self._q.task_done()

    def submit(self, fn: Callable[..., Any], args: tuple, kwargs: dict) -> Any:
        holder: dict[str, Any] = {}
        self._q.put(("call", (fn, args, kwargs, holder)))
        self._q.join()
        if "__error__" in holder:
            raise holder["__error__"]
        return holder["__result__"]


def install() -> None:
    """Idempotent. Start the worker thread and patch py_mini_racer.MiniRacer."""
    global _WORKER, _PATCHED
    if _PATCHED or py_mini_racer is None:
        return

    # Save the real MiniRacer under a private name so the worker can call it
    # directly without going back through the proxy.
    py_mini_racer._OrigMiniRacer = py_mini_racer.MiniRacer  # type: ignore[attr-defined]
    _WORKER = _Worker()

    class _Proxy:
        def execute(self, expr, *args, **kwargs):
            return _WORKER.submit(_Orig_execute, (expr, *args), kwargs)

        def eval(self, code, *args, **kwargs):
            return _WORKER.submit(_Orig_eval, (code, *args), kwargs)

        def call(self, name, *args, **kwargs):
            return _WORKER.submit(_Orig_call, (name, *args), kwargs)

    def _Orig_execute(mr, expr, *args, **kwargs):
        return mr.execute(expr, *args, **kwargs)

    def _Orig_eval(mr, code, *args, **kwargs):
        return mr.eval(code, *args, **kwargs)

    def _Orig_call(mr, name, *args, **kwargs):
        return mr.call(name, *args, **kwargs)

    py_mini_racer.MiniRacer = _Proxy  # type: ignore[attr-defined]

    # AkShare modules that did ``from py_mini_racer import MiniRacer`` keep the
    # original class in their namespace. Patch those already-loaded modules too
    # so any later ``MiniRacer()`` from AkShare returns our proxy.
    import sys as _sys
    orig = py_mini_racer._OrigMiniRacer
    for mod_name in list(_sys.modules):
        mod = _sys.modules.get(mod_name)
        if mod is None:
            continue
        if getattr(mod, "MiniRacer", None) is orig:
            mod.MiniRacer = _Proxy  # type: ignore[attr-defined]
    _PATCHED = True
