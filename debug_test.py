import sys
sys.path.insert(0, 'backend/app')
from aegiscore.document_service import save_document, get_resume_attachment, _database_connection

metadata, duplicate = save_document(
    "shivam_resume.pdf",
    b"%PDF-1.4\nTest resume content",
)
print(f"document_id: {metadata['document_id']}")
print(f"duplicate: {duplicate}")

doc_id = metadata["document_id"]
print(f"Looking up document_id: {doc_id}")

connection = _database_connection()
row = connection.execute(
    "SELECT * FROM documents WHERE document_id = ?",
    (doc_id,),
).fetchone()
print(f"Row found: {row is not None}")
if row:
    print(f"Row data: document_id={row['document_id']}, filename={row['filename']}, extension={row['extension']}")
connection.close()

try:
    meta, path = get_resume_attachment(doc_id)
    print(f"get_resume_attachment succeeded: {meta['document_id']}")
except Exception as e:
    print(f"get_resume_attachment failed: {e}")
