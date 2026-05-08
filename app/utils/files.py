import os
import uuid
from fastapi import UploadFile, HTTPException
from ..config import settings

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


async def save_upload_file(file: UploadFile, subfolder: str = "") -> str:
    """
    Faylni saqlaydi va nisbiy yo'lni qaytaradi.
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Faqat rasm fayllari qabul qilinadi (jpg, png, webp, gif)")

    content = await file.read()

    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail=f"Fayl hajmi {settings.MAX_FILE_SIZE_MB}MB dan oshmasligi kerak")

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"

    save_dir = os.path.join(settings.UPLOAD_DIR, subfolder)
    os.makedirs(save_dir, exist_ok=True)

    file_path = os.path.join(save_dir, filename)
    with open(file_path, "wb") as f:
        f.write(content)

    return f"{subfolder}/{filename}" if subfolder else filename


def delete_file(relative_path: str):
    full_path = os.path.join(settings.UPLOAD_DIR, relative_path)
    if os.path.exists(full_path):
        os.remove(full_path)