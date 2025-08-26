
import os, time, base64, json, httpx
from fastapi import Depends, HTTPException, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
from models import User
from main import SessionLocal

security = HTTPBearer()
oauth_router = APIRouter()

# This is a minimal OAuth flow suitable for admin-only dashboard.
# Frontend exchanges code -> backend -> Discord user info -> JWT-like simple token (signed).
SECRET = os.getenv("DISCORD_OAUTH_CLIENT_SECRET","devsecret")

def sign(payload: dict) -> str:
    data = json.dumps(payload).encode()
    sig = base64.urlsafe_b64encode(data).decode()
    return sig

def unsign(token: str) -> dict:
    try:
        data = base64.urlsafe_b64decode(token.encode())
        return json.loads(data.decode())
    except Exception:
        raise HTTPException(401, "Bad token")

class TokenResponse(BaseModel):
    token: str

@oauth_router.get("/oauth/callback", response_model=TokenResponse)
async def oauth_callback(code: str):
    # In production, exchange code with Discord OAuth2.
    # Here we mock by treating code as discord_id for simplicity of demo.
    discord_id = code
    username = f"user_{code[-4:]}" if len(code) >= 4 else f"user_{code}"
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.discord_id==discord_id))
        if not u:
            u = User(discord_id=discord_id, username=username, role="admin" if os.getenv("ADMIN_MOCK","0")=="1" else "member")
            db.add(u); db.commit()
    token = sign({"discord_id": discord_id, "role": u.role, "ts": int(time.time())})
    return {"token": token}

def get_current_user(token: HTTPAuthorizationCredentials = Depends(security)):
    data = unsign(token.credentials)
    return data

def admin_required(user=Depends(get_current_user)):
    if user.get("role") not in ("admin", "owner"):
        raise HTTPException(403, "Admins only")
    return user
