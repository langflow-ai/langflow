import asyncio

from loguru import logger

# Using asyncio.Event to implement HIL event lock mechanism

_events: dict[str, asyncio.Event] = {}
_data: dict[str, dict] = {}


async def wait_for_hil(run_id: str, timeout: float = 60 * 60):
    event = asyncio.Event()
    _events[run_id] = event
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
        return _data[run_id]
    except (asyncio.CancelledError, asyncio.TimeoutError) as e:
        if isinstance(e, asyncio.CancelledError) and run_id in _events:
            _events[run_id].set()
        logger.warning(f"HIL event {run_id} {'cancelled' if isinstance(e, asyncio.CancelledError) else 'timed out'}")
        raise
    finally:
        if run_id in _events:
            del _events[run_id]
        if run_id in _data:
            del _data[run_id]


async def trigger_hil(run_id: str, data: dict):
    if run_id not in _events:
        error_msg = f"HIL Event for run {run_id} not found or already timed out"
        logger.warning(error_msg)
        raise ValueError(error_msg)
    _data[run_id] = data
    _events[run_id].set()
