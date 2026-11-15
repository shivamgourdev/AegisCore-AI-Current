"""AEGISCORE_PHASE2_MCP_CIRCUIT_BREAKER

Circuit breaker for MCP server failures.

Tracks consecutive failures and opens the circuit after a threshold,
preventing excessive subprocess restarts and retry multiplication.
Supports half-open state for trial execution.
"""

from __future__ import annotations

import logging
import time
from enum import Enum


logger = logging.getLogger("aegiscore.mcp.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "closed"       # Normal operation, requests pass through
    OPEN = "open"           # Failing, requests are rejected immediately
    HALF_OPEN = "half_open" # Trial execution to test recovery


class CircuitBreaker:
    """Circuit breaker that tracks consecutive failures.

    After `failure_threshold` consecutive failures, the circuit opens
    and all requests are rejected immediately for `recovery_timeout`
    seconds. After that, the circuit enters half-open state and allows
    a single trial execution. If the trial succeeds, the circuit closes;
    if it fails, the circuit reopens.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0
        self._lock = __import__("threading").Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._update_state_locked()
            return self._state

    def _update_state_locked(self) -> None:
        """Update circuit state based on time and failure count."""
        if self._state == CircuitState.OPEN:
            if (
                self._last_failure_time is not None
                and time.monotonic() - self._last_failure_time >= self.recovery_timeout
            ):
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info("Circuit breaker entering half-open state.")

    def can_execute(self) -> bool:
        """Check if execution is allowed through the circuit breaker."""
        with self._lock:
            self._update_state_locked()

            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.OPEN:
                return False
            if self._state == CircuitState.HALF_OPEN:
                return self._half_open_calls < self.half_open_max_calls
            return False

    def record_success(self) -> None:
        """Record a successful execution."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._consecutive_failures = 0
                self._half_open_calls = 0
                logger.info("Circuit breaker closed after successful trial.")
            elif self._state == CircuitState.CLOSED:
                self._consecutive_failures = 0

    def record_failure(self) -> None:
        """Record a failed execution."""
        with self._lock:
            self._consecutive_failures += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                logger.warning("Circuit breaker reopened after failed trial.")
            elif self._state == CircuitState.CLOSED:
                if self._consecutive_failures >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        "Circuit breaker opened after %d consecutive failures.",
                        self.failure_threshold,
                    )

    def get_stats(self) -> dict:
        """Return circuit breaker statistics."""
        with self._lock:
            self._update_state_locked()
            return {
                "state": self._state.value,
                "consecutive_failures": self._consecutive_failures,
                "failure_threshold": self.failure_threshold,
                "half_open_calls": self._half_open_calls,
                "last_failure_time": self._last_failure_time,
            }


# Module-level singleton
_circuit_breaker: CircuitBreaker | None = None


def get_circuit_breaker() -> CircuitBreaker:
    """Return the singleton circuit breaker."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
    return _circuit_breaker
