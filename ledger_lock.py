"""Advisory cross-process locking for the local JSON ledger.

Supported deployment: POSIX systems with fcntl/flock. The lock file must live
on a local filesystem whose flock semantics are reliable; network filesystems
are not an accepted concurrency boundary.
"""
from __future__ import annotations

import fcntl
import functools
import os
from contextlib import contextmanager


@contextmanager
def ledger_file_lock(path: str):
    lock_path = os.path.abspath(path) + ".lock"
    directory = os.path.dirname(lock_path)
    os.makedirs(directory, exist_ok=True)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def locked_ledger(path_getter):
    """Serialize a complete ledger operation across threads and POSIX processes."""
    def decorate(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            with ledger_file_lock(path_getter()):
                return function(*args, **kwargs)
        return wrapped
    return decorate
