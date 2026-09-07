"""Unit tests for osw.utils.util.parallelize.

Covers issue #25. The behaviour that callers depend on is result ordering,
kwargs forwarding, and the two failure modes: abort on the first exception, or
collect exceptions in place so the batch completes with results still aligned
to the input.

Also covers issue #154: flush_at_end and progress_bar were dropped when the
implementation moved from dask to asyncio, leaving both parameters inert.
"""

import asyncio
import sys
import threading

import pytest

from osw.utils.util import ThreadRoutedStdout, parallelize

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


def _print_then_return(item):
    print(f"handled {item}")
    return item


def test_flush_at_end_prints_what_the_tasks_printed(capsys):
    parallelize(_print_then_return, [1, 2, 3], flush_at_end=True)

    out = capsys.readouterr().out
    assert "handled 1" in out
    assert "handled 2" in out
    assert "handled 3" in out


def test_flush_at_end_replays_in_input_order(capsys):
    """Output follows the iterable, not the order the tasks happened to finish."""
    import time

    delays = {1: 0.05, 2: 0.0, 3: 0.03}

    def sleep_then_print(item):
        time.sleep(delays[item])
        print(f"handled {item}")

    parallelize(sleep_then_print, [1, 2, 3], flush_at_end=True)

    out = capsys.readouterr().out
    assert out.index("handled 1") < out.index("handled 2") < out.index("handled 3")


def test_flush_at_end_defers_until_the_batch_is_done():
    """Nothing reaches the real stdout while the tasks are still running."""
    written = []
    snapshots = []
    barrier = threading.Barrier(3, timeout=BARRIER_TIMEOUT)

    class _Recorder:
        def write(self, message):
            written.append(message)
            return len(message)

        def flush(self):
            pass

    def print_then_look(item):
        print(f"handled {item}")
        barrier.wait()  # every task has printed by the time this releases
        snapshots.append("".join(written))

    original = sys.stdout
    sys.stdout = _Recorder()
    try:
        parallelize(print_then_look, [1, 2, 3], flush_at_end=True, progress_bar=False)
    finally:
        sys.stdout = original

    # mid-flight the real stream had seen none of it, afterwards it has all of it
    assert not any("handled" in snapshot for snapshot in snapshots)
    assert "".join(written).count("handled") == 3


def test_task_output_is_suppressed_without_flush_at_end(capsys):
    parallelize(_print_then_return, [1, 2, 3])

    assert "handled" not in capsys.readouterr().out


def test_flush_at_end_reports_even_when_the_batch_fails(capsys):
    """A failing item must not swallow the diagnostics of the others."""

    def print_then_fail(item):
        print(f"handled {item}")
        if item == 2:
            raise ValueError("boom")
        return item

    with pytest.raises(ValueError, match="boom"):
        parallelize(print_then_fail, [1, 2, 3], flush_at_end=True)

    assert "handled 1" in capsys.readouterr().out


def test_stdout_is_restored_afterwards():
    original = sys.stdout

    parallelize(_print_then_return, [1, 2], flush_at_end=True)

    assert sys.stdout is original


def test_stdout_is_restored_after_a_failure():
    original = sys.stdout

    with pytest.raises(ValueError):
        parallelize(_fail_on_even, [2])

    assert sys.stdout is original


def test_progress_bar_can_be_switched_off(capsys):
    assert parallelize(_double, [1, 2, 3], progress_bar=False) == [2, 4, 6]

    # tqdm renders to stderr, so switching it off must leave stderr untouched
    assert capsys.readouterr().err == ""


def test_progress_bar_is_shown_by_default(capsys):
    assert parallelize(_double, [1, 2, 3]) == [2, 4, 6]

    assert "3/3" in capsys.readouterr().err


def test_both_parameters_combine():
    """Neither parameter may break the results the caller is actually after."""
    assert parallelize(
        _print_then_return, [1, 2, 3], flush_at_end=True, progress_bar=False
    ) == [1, 2, 3]


def test_routed_stdout_keeps_threads_apart():
    """The property the old redirect_stdout lacked: concurrent writes stay separate."""
    stdout = ThreadRoutedStdout(sys.stdout)
    collected = {}
    barrier = threading.Barrier(2, timeout=BARRIER_TIMEOUT)

    def write_interleaved(name):
        buffer = stdout.register()
        barrier.wait()  # force both threads to be inside their capture at once
        stdout.write(name)
        barrier.wait()
        stdout.write(name)
        stdout.unregister()
        collected[name] = "".join(buffer)

    threads = [
        threading.Thread(target=write_interleaved, args=(name,)) for name in ("a", "b")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert collected == {"a": "aa", "b": "bb"}


def test_routed_stdout_passes_unregistered_threads_through():
    class _Sink:
        def __init__(self):
            self.written = []

        def write(self, message):
            self.written.append(message)
            return len(message)

    sink = _Sink()
    stdout = ThreadRoutedStdout(sink)

    stdout.write("straight through")

    assert sink.written == ["straight through"]
