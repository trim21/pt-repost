import threading
from types import TracebackType
from typing import Literal

import psycopg
import six
import xxhash
from psycopg.errors import QueryCanceled
from typing_extensions import LiteralString


class AcquireError(Exception):
    """An attempt to reacquire a non-shared lock failed."""


class FailedToLockError(Exception):
    """when using Lock as context manager, and it failed _acquire the lock"""


class ReleaseError(Exception):
    """An attempt to _release a lock failed due to the current scope not holding it."""


class UnsupportedInterfaceError(Exception):
    """Database interface specified or detected is unsupported."""


class _NoopLock:
    def acquire(self, blocking: bool = True) -> None:
        pass

    def release(self) -> None:
        pass


class Lock:
    __conn: psycopg.Connection
    key: str | int | tuple[int, int]
    __lock_id: tuple[int] | tuple[int, int]
    __value_holder: LiteralString
    __scope: str
    __shared: bool

    __blocking_lock_func: LiteralString
    __nonblocking_lock_func: LiteralString
    __unlock_func: LiteralString

    def __init__(
        self,
        conn_info: str,
        key: str | int | tuple[int, int],
        scope: Literal["session"] = "session",
        shared: bool = False,
        timeout_ms: int | None = None,
    ):
        """Create a new Lock instance.

        Parameters:
            conn_info: Database connection info.
            key: Unique lock key, str key will share namespace with single int key.
            scope: Lock scope, session means connection
            shared: Use a shared lock, it works like read-only lock in rwlock.
                    it will be blocked is someone holding a non-shared lock.
        """
        self.__conn = psycopg.Connection.connect(conn_info, autocommit=True)
        if timeout_ms:
            if isinstance(timeout_ms, int):
                self.__conn.execute(f"set statement_timeout = {timeout_ms:d}")
            else:
                raise ValueError(f"timeout_ms must be int or None, get {timeout_ms!r}")

        self.key = key
        # convert uint64 value range to int64 value range
        if isinstance(key, str | bytes):
            self.__lock_id = (
                xxhash.xxh3_64_intdigest(six.ensure_binary(key)) - 9223372036854775808,
            )
            self.__value_holder: LiteralString = "%s"
        elif isinstance(key, int):
            self.__lock_id = (key,)
            self.__value_holder = "%s"
        else:
            self.__lock_id = key
            self.__value_holder = "%s, %s"

        if len(self.__lock_id) == 1:
            assert -9223372036854775808 <= self.__lock_id[0] <= +9223372036854775807
        else:
            assert -2147483648 <= self.__lock_id[0] <= 2147483647
            assert -2147483648 <= self.__lock_id[1] <= 2147483647

        self.__scope = scope
        self.__shared = shared

        suffix: LiteralString = ""

        if shared:
            suffix = "_shared"

        # thread will need to acquire in-process lock first before they can acquire lock on pg
        if shared:
            self.__lock: threading.Lock | _NoopLock = _NoopLock()
        else:
            self.__lock = threading.Lock()

        self.__blocking_lock_func: LiteralString = f"pg_advisory_lock{suffix}"
        self.__nonblocking_lock_func: LiteralString = f"pg_try_advisory_lock{suffix}"
        self.__unlock_func: LiteralString = f"pg_advisory_unlock{suffix}"

    def __enter__(self) -> None:
        """Enter the context manager."""
        self.__lock.acquire(blocking=True)
        try:
            self.__acquire()
        except Exception:
            self.__lock.release()
            raise

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Exit the context manager."""
        self.__release()
        self.__lock.release()

        # do not suppress any error
        return exc is None

    def __acquire(self) -> bool:
        with self.__conn.cursor() as cursor:
            try:
                cursor.execute(
                    f"SELECT pg_catalog.{self.__blocking_lock_func}({self.__value_holder})",
                    self.__lock_id,
                )
            except QueryCanceled as e:
                raise FailedToLockError(f"timeout when _acquire lock for {self.key!r}") from e

            row = cursor.fetchone()
            if row is None:
                raise UnreachableError()
            result, *_ = row

        # lock function returns True/False in unblocking mode, and always None in blocking mode
        return result is not False

    def __release(self) -> bool:
        """Release the lock.

        Parameters:
            self (Lock): Lock.

        Returns:
            bool: True, if the lock was released, otherwise False.
        """
        with self.__conn.cursor() as cursor:
            cursor.execute(
                f"SELECT pg_catalog.{self.__unlock_func}({self.__value_holder})",
                self.__lock_id,
            )
            row = cursor.fetchone()
            if row is None:
                raise UnreachableError()
            result, *_ = row

        return result


class UnreachableError(Exception):
    pass
