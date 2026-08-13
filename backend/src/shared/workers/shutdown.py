import asyncio
import os
import signal

_shutdown_event = asyncio.Event()
_cleanup_tasks: list[asyncio.Task] = []


def _handler(sig: int, _frame):
    _shutdown_event.set()


def install_signal_handlers():
    # When workers run embedded inside the uvicorn process (main.py lifespan,
    # which sets EMBEDDED_WORKERS=1), uvicorn owns SIGINT/SIGTERM. Calling
    # loop.add_signal_handler here REPLACES uvicorn's handler, so a SIGTERM
    # would only set our event and the API server would never initiate
    # shutdown — the process hangs after the workers exit. Standalone worker
    # scripts (no EMBEDDED_WORKERS) own the loop and should install handlers.
    if os.environ.get("EMBEDDED_WORKERS"):
        return
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: _signal_handler(s))  # type: ignore[misc]
        except NotImplementedError:
            signal.signal(sig, _handler)


def _signal_handler(sig: int):
    _shutdown_event.set()


async def wait_for_shutdown():
    await _shutdown_event.wait()


def register_cleanup(task: asyncio.Task):
    _cleanup_tasks.append(task)


async def cleanup():
    for task in _cleanup_tasks:
        task.cancel()
    if _cleanup_tasks:
        await asyncio.gather(*_cleanup_tasks, return_exceptions=True)
