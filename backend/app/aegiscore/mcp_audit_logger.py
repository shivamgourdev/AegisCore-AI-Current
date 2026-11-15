"""AEGISCORE_PHASE2_MCP_AUDIT_LOGGER

Structured audit logging for MCP tool executions.

Uses tamper-evident append-only records with hash-chain integrity verification.
Does NOT claim immutability — documents exactly what tampering it can detect.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


logger = logging.getLogger("aegiscore.mcp.audit")


class AuditLogger:
    """Tamper-evident audit logger for MCP tool executions.

    Records are append-only JSONL entries with a hash chain linking each
    record to the previous one. Tampering (modification, removal, reordering)
    breaks the hash chain and is detectable on verification.

    Does not claim absolute immutability — an attacker with write access to
    the log file could rewrite the entire chain. Restricted file permissions
    are recommended.
    """

    def __init__(self, log_path: str | Path | None = None) -> None:
        if log_path is None:
            log_path = os.environ.get("AEGISCORE_MCP_AUDIT_LOG", "data/mcp_audit.log")
        self.log_path = Path(log_path)
        self._lock = threading.Lock()
        self._last_hash: str | None = None
        self._initialized = False

        # Ensure parent directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Recover chain state from existing log
        self._recover_chain()

    def _recover_chain(self) -> None:
        """Read existing log to recover the last hash in the chain."""
        if not self.log_path.exists():
            self._initialized = True
            return
        try:
            with self.log_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        self._last_hash = record.get("chain_hash")
                    except json.JSONDecodeError:
                        # Corrupt line — stop recovery; chain is broken
                        logger.warning("Corrupt audit log line encountered during recovery")
                        break
        except OSError as exc:
            logger.error("Failed to read audit log during recovery: %s", exc)
        self._initialized = True

    def _compute_chain_hash(self, previous_hash: str | None, record: dict[str, Any]) -> str:
        """Compute the chain hash for a record."""
        payload = {
            "previous_hash": previous_hash,
            "record": {
                k: v for k, v in record.items() if k != "chain_hash"
            },
        }
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    def log(
        self,
        execution_id: str,
        tool_name: str,
        input_data: dict[str, Any],
        output_status: str,
        duration_seconds: float,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an audit record and return it.

        The record includes a chain_hash linking to the previous record,
        making tampering detectable on verification.
        """
        if not self._initialized:
            self._recover_chain()

        # Sanitize input — never log sensitive document content
        safe_input = self._sanitize_input(input_data)

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": execution_id,
            "tool_name": tool_name,
            "input_hash": hashlib.sha256(
                json.dumps(safe_input, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "output_status": output_status,
            "duration_seconds": round(duration_seconds, 6),
            "error": error,
            "metadata": metadata or {},
            "previous_hash": self._last_hash,
        }

        chain_hash = self._compute_chain_hash(self._last_hash, record)
        record["chain_hash"] = chain_hash
        self._last_hash = chain_hash

        line = json.dumps(record, sort_keys=True, separators=(",", ":"))
        with self._lock:
            try:
                with self.log_path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
                    f.flush()
                    os.fsync(f.fileno())
            except OSError as exc:
                logger.error("Failed to write audit log: %s", exc)
                raise

        return record

    @staticmethod
    def _sanitize_input(input_data: dict[str, Any]) -> dict[str, Any]:
        """Remove potentially sensitive fields from logged input."""
        sensitive_keys = {"resume_text", "job_description", "resume_summary", "body", "text"}
        safe = {}
        for k, v in input_data.items():
            if k in sensitive_keys:
                safe[k] = f"<{len(str(v))} chars>" if v is not None else None
            else:
                safe[k] = v
        return safe

    def verify_chain(self) -> dict[str, Any]:
        """Verify the hash chain integrity of the audit log.

        Returns a dict with 'valid', 'record_count', 'broken_at', and 'details'.
        Detects modification, removal, or reordering of records.
        """
        if not self.log_path.exists():
            return {"valid": True, "record_count": 0, "broken_at": None, "details": "No log file"}

        previous_hash: str | None = None
        record_count = 0
        broken_at: int | None = None
        details: list[str] = []

        try:
            with self.log_path.open("r", encoding="utf-8") as f:
                for line_number, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        broken_at = line_number
                        details.append(f"Line {line_number}: corrupt JSON")
                        break

                    record_count += 1

                    # Check previous_hash linkage
                    if record.get("previous_hash") != previous_hash:
                        broken_at = line_number
                        details.append(
                            f"Line {line_number}: previous_hash mismatch "
                            f"(expected {previous_hash}, got {record.get('previous_hash')})"
                        )
                        break

                    # Recompute chain hash
                    payload = {
                        "previous_hash": record.get("previous_hash"),
                        "record": {
                            k: v for k, v in record.items() if k != "chain_hash"
                        },
                    }
                    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
                    expected_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

                    if record.get("chain_hash") != expected_hash:
                        broken_at = line_number
                        details.append(
                            f"Line {line_number}: chain_hash mismatch "
                            f"(expected {expected_hash}, got {record.get('chain_hash')})"
                        )
                        break

                    previous_hash = record.get("chain_hash")

        except OSError as exc:
            return {
                "valid": False,
                "record_count": record_count,
                "broken_at": line_number if "line_number" in dir() else None,
                "details": [f"IO error: {exc}"],
            }

        valid = broken_at is None
        return {
            "valid": valid,
            "record_count": record_count,
            "broken_at": broken_at,
            "details": details if details else ["Chain verified successfully"],
        }

    def get_last_hash(self) -> str | None:
        """Return the current head hash of the chain."""
        return self._last_hash


# Module-level singleton
_audit_logger: AuditLogger | None = None


def get_audit_logger(log_path: str | Path | None = None) -> AuditLogger:
    """Return the singleton audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(log_path)
    return _audit_logger
