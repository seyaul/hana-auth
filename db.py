# db.py  – single helper to always open the database safely
import aiosqlite, pathlib, asyncio

DB_PATH = pathlib.Path(__file__).with_name("users.db")

async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    # one-time, but cheap enough to run every open
    await db.execute("""CREATE TABLE IF NOT EXISTS users(
            id TEXT,
            name TEXT UNIQUE,
            hash TEXT
        )""")
    await db.commit()
    return db
