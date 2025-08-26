
import os, io, asyncio
from typing import Optional
try:
    import pytesseract
    from PIL import Image
except Exception:
    pytesseract = None
    Image = None

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

async def ai_chat(prompt: str, lang: str="ar") -> str:
    # Minimal adapter that prefers DeepSeek then OpenAI; falls back to a stub if none.
    if DEEPSEEK_API_KEY:
        # pseudo-call
        return f"[DeepSeek:{lang}] {prompt[:400]}"
    if OPENAI_API_KEY:
        return f"[OpenAI:{lang}] {prompt[:400]}"
    # fallback
    return f"[Local:{lang}] {prompt[:400]} (نموذج محلي تجريبي)"

async def ai_image_ocr_then_translate(image_bytes: bytes, lang: str="ar") -> str:
    text = ""
    if pytesseract and Image:
        try:
            img = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(img)
        except Exception:
            text = ""
    if DEEPSEEK_API_KEY:
        return f"[DeepSeek OCR→{lang}] {text[:500]}"
    if OPENAI_API_KEY:
        return f"[OpenAI OCR→{lang}] {text[:500]}"
    return f"[Local OCR→{lang}] {text[:500]}"
