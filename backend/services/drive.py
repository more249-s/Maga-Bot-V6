
import os, io, json, hashlib
# Minimal Google Drive uploader stub (structure + link simulation).
# Replace with real googleapiclient integration if desired.

ROOT_ID = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID","")

def ensure_drive_path_and_upload(work_name: str, chapter_folder: str, filename: str, data: bytes) -> str:
    # Pretend uploading and return a stable fake link.
    h = hashlib.sha256((work_name + chapter_folder + filename).encode()).hexdigest()[:12]
    return f"https://drive.google.com/fake/{h}/{filename}"
