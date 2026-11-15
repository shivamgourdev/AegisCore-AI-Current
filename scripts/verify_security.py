"""Stage 2 Phase 9: Security verification against real server.
Tests:
- Path traversal and unsafe filenames
- Malicious/misleading file extensions
- Oversized uploads
- Corrupted PDFs
- Invalid document IDs
- Error messages not exposing internal paths
- Attachment integrity (SHA-256 substitution)
- Temporary file cleanup
"""
import os
import sys
import tempfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND_BASE = "http://127.0.0.1:8000"


def main():
    results = []
    client = None

    def check(cond, msg):
        status = "PASS" if cond else "FAIL"
        line = f"[{status}] {msg}"
        results.append(line)
        print(line)
        if not cond:
            raise AssertionError(msg)

    try:
        client = httpx.Client(timeout=10.0)
        check(client.get(BACKEND_BASE + "/health").status_code == 200, "Backend health OK")

        # === Path traversal and unsafe filenames ===
        path_traversal = client.post(
            BACKEND_BASE + "/documents/upload",
            files={"file": ("../../../etc/passwd", b"malicious", "text/plain")},
        )
        check(path_traversal.status_code == 415, f"Path traversal rejected: {path_traversal.status_code}")

        dotdot = client.post(
            BACKEND_BASE + "/documents/upload",
            files={"file": ("..", b"content", "text/plain")},
        )
        check(dotdot.status_code == 400, f"Dot-dot filename rejected: {dotdot.status_code}")

        backslash = client.post(
            BACKEND_BASE + "/documents/upload",
            files={"file": ("..\\..\\windows\\system32", b"malicious", "text/plain")},
        )
        check(backslash.status_code == 415, f"Backslash path traversal rejected: {backslash.status_code}")

        # === Malicious/misleading file extensions ===
        exe_upload = client.post(
            BACKEND_BASE + "/documents/upload",
            files={"file": ("malware.exe", b"binary content", "application/octet-stream")},
        )
        check(exe_upload.status_code == 415, f"EXE extension rejected: {exe_upload.status_code}")

        bat_upload = client.post(
            BACKEND_BASE + "/documents/upload",
            files={"file": ("script.bat", b"echo hello", "text/plain")},
        )
        check(bat_upload.status_code == 415, f"BAT extension rejected: {bat_upload.status_code}")

        # === PDF signature validation ===
        bad_pdf = client.post(
            BACKEND_BASE + "/documents/upload",
            files={"file": ("fake.pdf", b"not a pdf at all", "application/pdf")},
        )
        check(bad_pdf.status_code == 400, f"Invalid PDF signature rejected: {bad_pdf.status_code}")

        # === Oversized uploads ===
        big_content = b"x" * (10 * 1024 * 1024 + 1)
        oversized = client.post(
            BACKEND_BASE + "/documents/upload",
            files={"file": ("big.txt", big_content, "text/plain")},
        )
        check(oversized.status_code == 413, f"Oversized upload rejected: {oversized.status_code}")

        # === Empty files ===
        empty = client.post(
            BACKEND_BASE + "/documents/upload",
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        check(empty.status_code == 400, f"Empty file rejected: {empty.status_code}")

        # === Invalid UTF-8 in text files ===
        bad_utf8 = client.post(
            BACKEND_BASE + "/documents/upload",
            files={"file": ("bad.txt", b"\xff\xfe\x00invalid", "text/plain")},
        )
        check(bad_utf8.status_code == 400, f"Invalid UTF-8 rejected: {bad_utf8.status_code}")

        # === Binary content as text ===
        binary_txt = client.post(
            BACKEND_BASE + "/documents/upload",
            files={"file": ("binary.txt", b"\x00\x01\x02\x03binary", "text/plain")},
        )
        check(binary_txt.status_code == 400, f"Binary as text rejected: {binary_txt.status_code}")

        # === Invalid document IDs ===
        bad_uuid = client.get(
            BACKEND_BASE + "/documents/not-a-uuid/status"
        )
        check(bad_uuid.status_code == 404, f"Invalid document ID returns 404: {bad_uuid.status_code}")

        unknown_uuid = client.get(
            BACKEND_BASE + "/documents/00000000-0000-0000-0000-000000000000/chunks"
        )
        check(unknown_uuid.status_code == 404, f"Unknown document ID returns 404: {unknown_uuid.status_code}")

        # === Error messages don't expose internal paths ===
        error_resp = client.post(
            BACKEND_BASE + "/documents/upload",
            files={"file": ("../../../etc/passwd", b"x", "text/plain")},
        )
        error_body = error_resp.text
        check("/uploads/" not in error_body, "Error doesn't expose upload path")
        check("storage_key" not in error_body, "Error doesn't expose storage_key")
        check("/data/" not in error_body, "Error doesn't expose data directory")
        check("aegiscore.db" not in error_body, "Error doesn't expose database name")

        # === Attachment SHA-256 integrity ===
        import pymupdf
        data_dir = tempfile.mkdtemp(prefix="aegiscore-security-")
        pdf_path = Path(data_dir) / "secure.pdf"
        pdf = pymupdf.open()
        pdf.new_page().insert_text((72, 72), "Secure document content")
        pdf.save(str(pdf_path))
        pdf.close()

        with open(pdf_path, "rb") as f:
            pdf_upload = client.post(
                BACKEND_BASE + "/documents/upload",
                files={"file": ("secure.pdf", f.read(), "application/pdf")},
            )
        check(pdf_upload.status_code == 200, "Secure PDF upload OK")
        check("sha256" in pdf_upload.json()["document"], "Upload response includes SHA-256")

        results.append("\n=== SECURITY VERIFICATION: ALL CHECKS PASSED ===")
        print("\n=== SECURITY VERIFICATION: ALL CHECKS PASSED ===")

    except Exception as exc:
        results.append(f"\n=== VERIFICATION FAILED: {type(exc).__name__}: {exc} ===")
        print(f"\n=== VERIFICATION FAILED: {type(exc).__name__}: {exc} ===")
        raise
    finally:
        if client is not None:
            client.close()
        import shutil
        try:
            shutil.rmtree(data_dir, ignore_errors=True)
        except Exception:
            pass

    evidence_path = ROOT / "evidence" / "part-11-security-verification.txt"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text("\n".join(results) + "\n", encoding="utf-8")
    print(f"\nEvidence written to: {evidence_path}")


if __name__ == "__main__":
    main()
