# app.py, run fly with fly deploy
from fastapi import FastAPI, HTTPException, status, Depends, UploadFile, File, Path 
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer
from fastapi.responses import FileResponse
from passlib.hash import bcrypt
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from pathlib import Path as PPath
import aiosqlite, uuid, os
from contextlib import asynccontextmanager


SECRET = os.getenv("JWT_SECRET", "CHANGE_ME")   # export JWT_SECRET=reallyrandom
ALGO   = "HS256"
TTL    = timedelta(hours=8)
security = HTTPBearer()
CURRENT_VERSION = "0.1.65"
VALID_TOOLS = {"wholefoods", "safeway", "harristeeter", "giantscale"}


DB = "/data/users.db"
DATA_DIR = PPath("/data")
print(f"Database path: {DB}")
print(f"Data directory exists: {os.path.exists('/data')}")
print(f"Data directory writable: {os.access('/data', os.W_OK)}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("/data", exist_ok=True)

    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id          TEXT,
                name        TEXT UNIQUE,
                hash        TEXT,
                password    TEXT DEFAULT 'test',         
                role        TEXT DEFAULT 'user'
            )
        """)
        
        # -------- FIXED block (no 'async for' on coroutine) --------
        cur  = await db.execute("PRAGMA table_info(users)")
        cols = [row[1] for row in await cur.fetchall()]
        await cur.close()
        # -----------------------------------------------------------
        await db.commit()

    yield

async def verify_token(token: str = Depends(security)):
    try:
        payload = jwt.decode(token.credentials, SECRET, algorithms=[ALGO])
        username = payload.get("sub")
        if not username:
            raise HTTPException(401, "Invalid token")
        
        # Check if user still exists in database
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute("SELECT name FROM users WHERE name=?", (username,))
            row = await cur.fetchone()
            await cur.close()
        
        if not row:
            raise HTTPException(401, "User no longer exists")
            
        return username
    except JWTError:
        raise HTTPException(401, "Invalid token")
    

async def get_role(username: str) -> str | None:
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT role FROM users WHERE name=?", (username,))
        row = await cur.fetchone()
        await cur.close()
    return row[0] if row else None

async def admin_guard(current_user: str = Depends(verify_token)):
    role = await get_role(current_user)
    if role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return current_user


# Add the lifespan to your FastAPI app
app = FastAPI(lifespan=lifespan)  # ← Add this parameter

import sqlite3


async def _create_user(name: str, pw: str, role: str = "user"):
    try:
        # bcrypt has a 72-byte limit on passwords
        if len(pw.encode('utf-8')) > 72:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password too long (max 72 bytes)")

        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "INSERT INTO users (id, name, hash, password, role) VALUES (?,?,?,?,?)",
                (str(uuid.uuid4()), name, bcrypt.hash(pw), pw, role)
            )
            await db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "User already exists")



async def delete_user(name):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM users WHERE name=?", (name,))
        await db.commit()

async def _verify(name: str, pw: str) -> bool:
    try:
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute("SELECT hash FROM users WHERE name=?", (name,))
            row = await cur.fetchone()
            await cur.close()

        if not row:
            return False

        # bcrypt has a 72-byte limit on passwords
        if len(pw.encode('utf-8')) > 72:
            return False

        return bcrypt.verify(pw, row[0])
    except (ValueError, Exception) as e:
        # Log the error for debugging (optional)
        print(f"Verification error for user {name}: {type(e).__name__}: {e}")
        return False

def jwt_token(sub):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": sub, "iat": now, "exp": now + TTL}, SECRET, ALGO)

@app.post("/login")
async def login(form: OAuth2PasswordRequestForm = Depends()):
    if not await _verify(form.username, form.password):
        raise HTTPException(401, "Bad creds")
    return {"access_token": jwt_token(form.username), "token_type": "bearer"}

@app.get("/")
async def root():
    return {"message": "Hello World", "status": "API is running"}

# admin endpoints (simple)
@app.post("/admin/create/{user}/{pw}")
async def admin_create(user: str, pw: str,
                       _=Depends(admin_guard)):
    await _create_user(user, pw)           # default role='user'
    return {"msg": "user added"}

@app.post("/admin/promote/{user}")
async def admin_promote(user: str,
                        _=Depends(admin_guard)):
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE users SET role='admin' WHERE name=?", (user,))
        await db.commit()
    return {"msg": f"{user} promoted"}

@app.delete("/admin/delete/{user}")
async def admin_delete(user: str,
                       _=Depends(admin_guard)):
    await delete_user(user); return {"msg": "user deleted"}

@app.get("/admin/users")
async def list_users(_=Depends(admin_guard)):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT id, name, role, password FROM users")
        rows = await cur.fetchall()
    return {"users": [
        {"id": r[0], "name": r[1], "role": r[2], "password": r[3]}
        for r in rows
    ]}


## NOTE: Non admin-locked endpoints
@app.get("/verify")
async def verify_user(current_user: str = Depends(verify_token)):
    return {"user": current_user, "status": "valid"}

@app.get("/version")
def get_version():
    return {
        "version": CURRENT_VERSION,
        "download_url": f"https://github.com/seyaul/Scrapling/releases/download/v{CURRENT_VERSION}/HanaTool-{CURRENT_VERSION}.zip",  # Changed to .zip
        "release_date": "2025-11-13",
        "required": False,
        "changelog": "Update: Price History Management v1"
    }

import shutil, uuid
@app.post("/upload/{tool}")
async def upload_csv(
    tool: str = Path(..., description="scraper ID"),
    file: UploadFile = File(...)
):
    if tool not in VALID_TOOLS:
        raise HTTPException(400, "unknown tool")
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "CSV only")

    unique = DATA_DIR / f"{tool}_{uuid.uuid4()}.csv"
    with unique.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    latest_link = DATA_DIR / f"latest_{tool}.csv"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(unique.name)           # latest_<tool>.csv

    return {"ok": True, "stored_as": unique.name}


@app.get("/download/{tool}/latest")
def download_latest(tool: str = Path(...)):
    latest_link = DATA_DIR / f"latest_{tool}.csv"
    if not latest_link.exists():
        raise HTTPException(404, "No file yet for this tool")
    return FileResponse(DATA_DIR / latest_link.readlink())