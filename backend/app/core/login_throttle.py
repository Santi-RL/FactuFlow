"""Presupuesto acotado de login para el runtime de un proceso de FactuFlow."""

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from math import ceil
from threading import Lock
from time import monotonic
from typing import Callable

from fastapi import HTTPException, Request

_INITIALIZATION_LOCK = Lock()


@dataclass
class _Window:
    expires: float
    count: int = 0


class LoginThrottle:
    """Reserva antes de bcrypt; los rechazos no prolongan las ventanas."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        window_seconds: int = 60,
        account_limit: int = 5,
        source_limit: int = 30,
        total_limit: int = 60,
        max_entries: int = 4096,
        concurrency: int = 2,
    ):
        self.clock = clock
        self.window_seconds = window_seconds
        self.account_limit = account_limit
        self.source_limit = source_limit
        self.total_limit = total_limit
        self.max_entries = max_entries
        self.concurrency = concurrency
        self._entries: dict[str, _Window] = {}
        self._total = _Window(0)
        self._active = 0
        self._lock = Lock()

    @staticmethod
    def _reject(seconds: float):
        retry = max(1, ceil(seconds))
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos de acceso. Vuelve a intentarlo en {retry} segundos.",
            headers={"Retry-After": str(retry)},
        )

    @contextmanager
    def attempt(self, email: str, source: str):
        account_key = "account:" + sha256(email.strip().lower().encode()).hexdigest()
        source_key = "source:" + sha256(source.encode()).hexdigest()
        with self._lock:
            now = self.clock()
            self._entries = {
                key: value
                for key, value in self._entries.items()
                if value.expires > now
            }
            if self._total.expires <= now:
                self._total = _Window(now + self.window_seconds)
            constraints = [(self._total, self.total_limit)]
            for key, limit in (
                (account_key, self.account_limit),
                (source_key, self.source_limit),
            ):
                if key in self._entries:
                    constraints.append((self._entries[key], limit))
            waits = [
                value.expires - now
                for value, limit in constraints
                if value.count >= limit
            ]
            if waits:
                self._reject(max(waits))
            missing = sum(key not in self._entries for key in (account_key, source_key))
            if len(self._entries) + missing > self.max_entries:
                self._reject(
                    min(value.expires for value in self._entries.values()) - now
                )
            if self._active >= self.concurrency:
                self._reject(1)
            account = self._entries.setdefault(
                account_key, _Window(now + self.window_seconds)
            )
            origin = self._entries.setdefault(
                source_key, _Window(now + self.window_seconds)
            )
            account.count += 1
            origin.count += 1
            self._total.count += 1
            self._active += 1
        # El resultado mutable permite descontar sólo este acceso correcto.
        result = {"success": False}
        try:
            yield result
        finally:
            with self._lock:
                self._active -= 1
                if result["success"]:
                    account.count -= 1


def get_login_throttle(request: Request) -> LoginThrottle:
    """Estado por aplicación; no interpretar cabeceras de proxy del cliente."""
    with _INITIALIZATION_LOCK:
        if not hasattr(request.app.state, "login_throttle"):
            request.app.state.login_throttle = LoginThrottle()
        return request.app.state.login_throttle
