"""Quick OCR end-to-end test."""
import sys
sys.path.insert(0, 'backend/app')
from PIL import Image, ImageDraw
import io
from aegiscore.ocr_service import extract_text_from_image_bytes

# Create a test image with text
img = Image.new('RGB', (400, 200), color='white')
draw = ImageDraw.Draw(img)
draw.text((20, 20), 'HIRING: Python Developer', fill='black')
draw.text((20, 60), 'Company: TechCorp', fill='black')
draw.text((20, 100), 'Location: New York', fill='black')
draw.text((20, 140), 'Salary $100k', fill='black')

buf = io.BytesIO()
img.save(buf, format='PNG')
img_bytes = buf.getvalue()

result = extract_text_from_image_bytes(img_bytes)
print('OCR Result:', result)
print('TEXT:', repr(result.get('text', '')))
print('CONFIDENCE:', result.get('confidence'))
assert result['text'], 'Expected non-empty text'
assert 'Python' in result['text'] or 'TECHCORP' in result['text'].upper(), 'Expected project name in text'
print('SUCCESS: OCR extraction works correctly!')