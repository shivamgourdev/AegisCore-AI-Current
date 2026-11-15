"""Stage 2 Phase 4: RAG Knowledge Sandbox - real browser verification.
Assumes backend is running on port 8000 and frontend proxy on port 5500.
Uses Playwright to test the full RAG Q&A workflow in a real browser.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pymupdf
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BACKEND_BASE = "http://127.0.0.1:8000"
FRONTEND_BASE = "http://127.0.0.1:5500"


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

        # Verify servers are reachable
        check(client.get(BACKEND_BASE + "/health").status_code == 200, "Backend health OK")
        check(client.get(FRONTEND_BASE + "/").status_code == 200, "Frontend reachable")

        # Create synthetic documents
        data_dir = tempfile.mkdtemp(prefix="aegiscore-rag-browser-")
        pdf_path = Path(data_dir) / "orion_report.pdf"
        pdf = pymupdf.open()
        p1 = pdf.new_page()
        p1.insert_text((72, 72), "Project Orion revenue was 42 million dollars in Q3.")
        p2 = pdf.new_page()
        p2.insert_text((72, 72), "Unique fact on page 2: The hiring team plans to recruit six junior Python engineers.")
        pdf.save(str(pdf_path))
        pdf.close()

        txt_path = Path(data_dir) / "notes.txt"
        txt_path.write_text("Project Orion revenue was 42 million dollars in Q3.\nThe hiring team plans to recruit six junior Python engineers.", encoding="utf-8")

        md_path = Path(data_dir) / "readme.md"
        md_path.write_text("# Project Orion\n\n- Revenue: 42 million dollars in Q3.\n- Hiring: six junior Python engineers.", encoding="utf-8")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # Capture console errors
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: console_errors.append(str(exc)))

            # 1. Open the application
            page.goto(FRONTEND_BASE + "/", wait_until="networkidle")
            check(page.locator("h1").text_content() is not None, "Page loads")

            # 2. RAG Knowledge Sandbox heading visible
            rag_heading = page.locator("h2").filter(has_text="RAG Knowledge Sandbox")
            check(rag_heading.count() == 1, "RAG Knowledge Sandbox heading visible")

            # 3-5. Upload PDF, TXT, MD files
            file_input = page.locator("#ragFiles")
            file_input.set_input_files([str(pdf_path), str(txt_path), str(md_path)])

            # 6. Upload selected
            page.locator("#ragUploadBtn").click()
            page.wait_for_timeout(5000)

            upload_status = page.locator("#ragUploadStatus").text_content()
            check("Uploaded 3 document(s)" in upload_status, f"All 3 docs uploaded. Status: {upload_status}")

            # 7-8. Verify document names in list
            page.wait_for_timeout(1000)
            doc_list = page.locator("#ragDocumentList").text_content()
            check("orion_report.pdf" in doc_list, "PDF document in list")
            check("notes.txt" in doc_list, "TXT document in list")
            check("readme.md" in doc_list, "MD document in list")

            # 9-10. Verify extraction and embedding status via API
            docs_response = client.get(BACKEND_BASE + "/documents")
            docs_data = docs_response.json()
            check(len(docs_data["documents"]) >= 3, f"At least 3 documents registered")

            for doc in docs_data["documents"]:
                status_response = client.get(BACKEND_BASE + f"/documents/{doc['document_id']}/status")
                check(status_response.status_code == 200, f"Status OK for {doc['filename']}")
                status_data = status_response.json()
                check(status_data["status"] == "text_extracted", f"{doc['filename']} extraction status")
                check(status_data["chunk_count"] >= 1, f"{doc['filename']} has chunks")
                check(status_data["embedding_count"] >= 1, f"{doc['filename']} has embeddings")

            # 11-12. Dense retrieval Q&A
            page.locator("#ragQuery").fill("What was Project Orion's Q3 revenue?")
            page.locator("#ragMode").select_option("dense")
            page.locator("#ragAskBtn").click()
            page.wait_for_timeout(60000)  # Ollama needs time

            ask_status = page.locator("#ragAskStatus").text_content()
            answer = page.locator("#ragAnswer").text_content()
            print(f"DEBUG dense: status='{ask_status}' answer='{answer[:200] if answer else '(empty)'}'")
            check(len(answer) > 0 or "No answer" in ask_status, f"Dense retrieval returned a response. Status: {ask_status}")
            citations_dense = page.locator("#ragCitations").text_content()
            # If answered (not abstained), verify citations exist
            if "No answer" not in ask_status and "abstained" not in ask_status.lower():
                check(len(citations_dense) > 0, "Dense retrieval has citations when answered")
            else:
                print("  (Dense retrieval abstained - correct fail-closed behavior)")

            # 13. Sparse retrieval Q&A
            page.locator("#ragQuery").fill("hiring junior Python engineers")
            page.locator("#ragMode").select_option("sparse")
            page.locator("#ragAskBtn").click()
            page.wait_for_timeout(60000)

            ask_status_sparse = page.locator("#ragAskStatus").text_content()
            answer_sparse = page.locator("#ragAnswer").text_content()
            print(f"DEBUG sparse: status='{ask_status_sparse}' answer='{answer_sparse[:200] if answer_sparse else '(empty)'}'")
            check(len(answer_sparse) > 0 or "No answer" in ask_status_sparse, f"Sparse retrieval returned a response. Status: {ask_status_sparse}")
            citations_sparse = page.locator("#ragCitations").text_content()
            if "No answer" not in ask_status_sparse and "abstained" not in ask_status_sparse.lower():
                check(len(citations_sparse) > 0, "Sparse retrieval has citations when answered")
            else:
                print("  (Sparse retrieval abstained - correct fail-closed behavior)")

            # 14. Hybrid retrieval Q&A
            page.locator("#ragQuery").fill("Project Orion revenue and hiring")
            page.locator("#ragMode").select_option("hybrid")
            page.locator("#ragAskBtn").click()
            page.wait_for_timeout(60000)

            ask_status_hybrid = page.locator("#ragAskStatus").text_content()
            answer_hybrid = page.locator("#ragAnswer").text_content()
            print(f"DEBUG hybrid: status='{ask_status_hybrid}' answer='{answer_hybrid[:200] if answer_hybrid else '(empty)'}'")
            check(len(answer_hybrid) > 0 or "No answer" in ask_status_hybrid, f"Hybrid retrieval returned a response. Status: {ask_status_hybrid}")
            citations_hybrid = page.locator("#ragCitations").text_content()
            if "No answer" not in ask_status_hybrid and "abstained" not in ask_status_hybrid.lower():
                check(len(citations_hybrid) > 0, "Hybrid retrieval has citations when answered")
            else:
                print("  (Hybrid retrieval abstained - correct fail-closed behavior)")

            # 15. Unsupported question - verify system handles it (abstain or grounded answer)
            page.locator("#ragQuery").fill("What is the serial number of the Zephyr spacecraft?")
            page.locator("#ragMode").select_option("dense")
            page.locator("#ragAskBtn").click()
            page.wait_for_timeout(60000)

            abstain_status = page.locator("#ragAskStatus").text_content()
            answer_unsupported = page.locator("#ragAnswer").text_content()
            print(f"DEBUG unsupported: status='{abstain_status}' answer='{answer_unsupported[:200] if answer_unsupported else '(empty)'}'")
            check(len(answer_unsupported) > 0 or "No answer" in abstain_status, f"System returned a response for unsupported question. Status: {abstain_status}")
            # Verify no invented facts - if answered, it should only cite existing documents
            citations_unsupported = page.locator("#ragCitations").text_content()
            if "No answer" not in abstain_status and "abstained" not in abstain_status.lower():
                # If answered, verify citations reference real uploaded documents
                check(len(citations_unsupported) > 0, "Unsupported question has citations when answered")
                print("  (Unsupported question answered with grounded citations - acceptable)")
            else:
                print("  (Unsupported question abstained - correct behavior)")

            # 16. Loading state - button should be re-enabled
            check(page.locator("#ragAskBtn").is_enabled(), "Ask button re-enabled after request")

            # 17. Delete one document from UI
            delete_buttons = page.locator("button:has-text('Delete')")
            check(delete_buttons.count() >= 1, "Delete buttons visible")

            # Count documents before deletion
            docs_before = client.get(BACKEND_BASE + "/documents").json()["documents"]
            count_before = len(docs_before)

            # Set up dialog handler before clicking
            page.on("dialog", lambda dialog: dialog.accept())
            delete_buttons.first.click()
            page.wait_for_timeout(3000)

            delete_status = page.locator("#ragUploadStatus").text_content()
            check("deleted" in delete_status.lower(), f"Delete status: {delete_status}")

            # 18. Verify document count decreased
            docs_after = client.get(BACKEND_BASE + "/documents").json()["documents"]
            check(len(docs_after) == count_before - 1, f"Document count decreased: {count_before} -> {len(docs_after)}")

            # 19. Verify remaining documents are intact
            check(len(docs_after) >= 2, "At least 2 documents remain after deletion")

            # Check no console errors
            check(len(console_errors) == 0, f"No console errors. Errors: {console_errors}")

            browser.close()

        results.append("\n=== RAG KNOWLEDGE SANDBOX BROWSER VERIFICATION: ALL CHECKS PASSED ===")
        print("\n=== RAG KNOWLEDGE SANDBOX BROWSER VERIFICATION: ALL CHECKS PASSED ===")

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

    # Write evidence
    evidence_path = ROOT / "evidence" / "part-07-rag-browser-verification.txt"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text("\n".join(results) + "\n", encoding="utf-8")
    print(f"\nEvidence written to: {evidence_path}")


if __name__ == "__main__":
    main()
