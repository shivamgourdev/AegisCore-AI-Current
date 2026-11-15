"""AEGISCORE_PHASE2_TESTS_CIRCUIT_BREAKER

Unit tests for the MCP circuit breaker.
"""

import pytest

from aegiscore.mcp_circuit_breaker import CircuitBreaker, CircuitState, get_circuit_breaker


class TestCircuitBreaker:
    def test_closed_state_allows_execution(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        assert cb.can_execute() is True

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        import time
        time.sleep(0.15)

        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        import time
        time.sleep(0.15)

        assert cb.can_execute() is True  # Half-open allows one call
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb._consecutive_failures == 0

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        import time
        time.sleep(0.15)

        assert cb.can_execute() is True
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_consecutive_failures_reset_on_success(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        cb.record_failure()
        cb.record_failure()
        assert cb._consecutive_failures == 2
        cb.record_success()
        assert cb._consecutive_failures == 0

    def test_get_stats(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        stats = cb.get_stats()
        assert stats["state"] == CircuitState.CLOSED.value
        assert stats["consecutive_failures"] == 0
        assert stats["failure_threshold"] == 3

    def test_singleton(self):
        cb1 = get_circuit_breaker()
        cb2 = get_circuit_breaker()
        assert cb1 is cb2

    def test_half_open_max_calls(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1, half_open_max_calls=1)
        cb.record_failure()
        cb.record_failure()
        import time
        time.sleep(0.15)

        # First call in half-open is allowed
        assert cb.can_execute() is True
        # Second call should be blocked (half_open_max_calls=1)
        cb._half_open_calls = 1  # Simulate first call used
        assert cb.can_execute() is False


class TestCircuitBreakerIntegration:
    def test_circuit_breaker_in_execution_flow(self):
        """Test that circuit breaker integrates with execution decisions."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)

        # Simulate failures
        for _ in range(3):
            cb.record_failure()

        # Circuit should be open, blocking execution
        assert cb.can_execute() is False

        # Record success should not be possible while open
        # (but we can still call record_success - it just won't change state to closed)
        cb.record_success()  # While OPEN, record_success doesn't change state
        assert cb.state == CircuitState.OPEN
