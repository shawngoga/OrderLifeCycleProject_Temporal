import asyncio
import logging

logger = logging.getLogger("hedge")

# Shared primitives
hedge_success = asyncio.Event()
hedge_winner_id: int | None = None
hedge_id_map: dict[asyncio.Task, int] = {}

# Global lock to enforce atomic election
_election_lock = asyncio.Lock()


def reset_hedge_state():

    global hedge_winner_id
    hedge_success.clear()
    hedge_winner_id = None
    hedge_id_map.clear()


async def elect_hedge_winner(hedge_id: int, order_id: str, logger) -> bool:

    global hedge_winner_id

    async with _election_lock:
        if hedge_winner_id is None:
            hedge_winner_id = hedge_id
            hedge_success.set()
            logger.info(f"[Hedge] hedge {hedge_id} elected as winner for order {order_id}")

    # Double‑check before DB commit
    if hedge_winner_id != hedge_id:
        logger.info(f"[Hedge] hedge {hedge_id} canceled before DB commit for order {order_id}")
        return False

    return True


async def run_with_hedges(fn, *args, hedges: int = 7, **kwargs):
    """
    Launch multiple hedges, return first real success, cancel losers immediately.
    Each hedge task registers its hedge_id in hedge_id_map.
    """
    tasks: list[asyncio.Task] = []

    # Bind hedge_id explicitly to avoid late binding bug
    for i in range(hedges):
        async def wrapped_fn(*args, hedge_id=i, **kwargs):
            task = asyncio.current_task()
            hedge_id_map[task] = hedge_id
            return await fn(*args, **kwargs)

        t = asyncio.create_task(wrapped_fn(*args, **kwargs))
        hedge_id_map[t] = i  # ensure lookup works later
        tasks.append(t)

    winner_result = None
    last_error = None

    for fut in asyncio.as_completed(tasks):
        try:
            result = await fut
            hedge_id = hedge_id_map.get(fut, "?")

            # Skip loser sentinel values (None or empty string)
            if result is None or result == "":
                continue

            winner_result = result

            for t in tasks:
                if t is not fut and not t.done():
                    t.cancel()
                    loser_id = hedge_id_map.get(t, "?")
            break
        except Exception as e:
            hedge_id = hedge_id_map.get(fut, "?")
            logger.error(f"[Hedge] hedge {hedge_id} failed: {e}")
            last_error = e

    # Drain canceled tasks
    for t in tasks:
        if t.done():
            try:
                await t
            except Exception:
                pass

    if winner_result is not None:
        return winner_result
    raise last_error
