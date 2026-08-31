"""Unit tests for osw.utils.util.parallelize.

Covers issue #25. The behaviour that callers depend on is result ordering,
kwargs forwarding, and the two failure modes: abort on the first exception, or
collect exceptions in place so the batch completes with results still aligned
to the input.
"""

import asyncio
import threading

import pytest

from osw.utils.util import parallelize

# Generous enough that a loaded CI machine still passes, short enough that a
# serialized execution trips it instead of hanging the suite.
BARRIER_TIMEOUT = 30


def _double(item):
    return item * 2


def _add(item, offset=0, factor=1):
    return item * factor + offset


def _fail_on_even(item):
    if item % 2 == 0:
        raise ValueError(f"boom on {item}")
    return item


def test_returns_results_in_input_order():
    """Results map back to the input positionally, not by completion time."""
    delays = [0.05, 0.0, 0.03, 0.0]

    def sleep_then_return(item):
        import time

        time.sleep(delays[item])
        return item

    assert parallelize(sleep_then_return, [0, 1, 2, 3]) == [0, 1, 2, 3]


def test_maps_the_function_over_the_iterable():
    assert parallelize(_double, [1, 2, 3]) == [2, 4, 6]


def test_forwards_kwargs_to_the_function():
    assert parallelize(_add, [1, 2, 3], offset=10, factor=2) == [12, 14, 16]


def test_empty_iterable_returns_empty_list():
    assert parallelize(_double, []) == []


def test_accepts_any_iterable_not_only_a_list():
    assert parallelize(_double, range(3)) == [0, 2, 4]


def test_tasks_run_concurrently():
    """A barrier that only clears if all items are in flight at once."""
    barrier = threading.Barrier(4, timeout=BARRIER_TIMEOUT)

    def wait_for_the_others(item):
        barrier.wait()
        return item

    assert parallelize(wait_for_the_others, [1, 2, 3, 4]) == [1, 2, 3, 4]


def test_first_exception_propagates_by_default():
    with pytest.raises(ValueError, match="boom on 2"):
        parallelize(_fail_on_even, [1, 2, 3])


def test_return_exceptions_keeps_results_aligned():
    """Regression guard: a failing item must not drop its neighbours."""
    results = parallelize(_fail_on_even, [1, 2, 3, 4, 5], return_exceptions=True)

    assert len(results) == 5
    assert results[0] == 1
    assert isinstance(results[1], ValueError)
    assert results[2] == 3
    assert isinstance(results[3], ValueError)
    assert results[4] == 5


def test_return_exceptions_completes_every_task():
    """Every item is attempted even though the first one raises."""
    attempted = []
    lock = threading.Lock()

    def record_then_fail(item):
        with lock:
            attempted.append(item)
        raise RuntimeError(f"boom on {item}")

    results = parallelize(record_then_fail, [1, 2, 3], return_exceptions=True)

    assert sorted(attempted) == [1, 2, 3]
    assert all(isinstance(r, RuntimeError) for r in results)


def test_works_inside_a_running_event_loop():
    """The Jupyter case: parallelize is called while a loop is already running."""

    async def caller():
        return parallelize(_double, [1, 2, 3])

    assert asyncio.run(caller()) == [2, 4, 6]
