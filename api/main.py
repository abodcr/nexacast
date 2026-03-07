import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from auth import build_session_user, get_current_user, require_admin
from db import ChannelStore
from ffmpeg import FFmpegManager
from users import UserStore, verify_password

APP_NAME = "streambox-api"
HLS_DIR = os.getenv("HLS_DIR", "/var/lib/streambox/hls")
PUBLIC_HLS_BASE = os.getenv("PUBLIC_HLS_BASE", "http://{server}:8081").rstrip("/")
DB_PATH = os.getenv("DB_PATH", "/data/channels.json")
USERS_DB_PATH = os.getenv("USERS_DB_PATH", "/data/users.json")
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-this-secret")
SESSION_HTTPS_ONLY = os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

store = ChannelStore(DB_PATH)
ff = FFmpegManager(hls_dir=HLS_DIR, public_hls_base=PUBLIC_HLS_BASE)
users = UserStore(USERS_DB_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    users.ensure_default_admin(ADMIN_USERNAME, ADMIN_PASSWORD)
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="streambox_session",
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
    max_age=60 * 60 * 12,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class ChannelIn(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    source_url: str = Field(min_length=1, max_length=2048)
    enabled: bool = True
    profile: str = Field(
        default="copy",
        pattern="^(copy|audio_aac_fix|transcode_720p|transcode_480p)$",
    )


class ChannelOut(BaseModel):
    id: str
    name: str
    source_url: str
    enabled: bool
    profile: str
    running: bool
    status: str
    hls_url: str
    last_error: Optional[str] = None
    log_url: str
    started_at: Optional[int] = None
    last_seen_at: Optional[int] = None
    restart_count: int = 0
    playlist_exists: bool = False
    playlist_mtime: Optional[int] = None
    segment_count: int = 0


def channel_to_out(ch: Dict[str, Any]) -> ChannelOut:
    cid = ch["id"]
    m = ff.metrics(cid)
    return ChannelOut(
        id=cid,
        name=ch["name"],
        source_url=ch["source_url"],
        enabled=bool(ch.get("enabled", True)),
        profile=ch.get("profile", "copy"),
        running=bool(m["running"]),
        status=str(m["status"]),
        hls_url=str(m["hls_url"]),
        last_error=m["last_error"],
        log_url=f"/channels/{cid}/log",
        started_at=m["started_at"],
        last_seen_at=m["last_seen_at"],
        restart_count=int(m["restart_count"]),
        playlist_exists=bool(m["playlist_exists"]),
        playlist_mtime=m["playlist_mtime"],
        segment_count=int(m["segment_count"]),
    )


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "app": APP_NAME,
        "hls_dir": HLS_DIR,
        "channels_count": len(store.list()),
    }


@app.post("/login")
def login(payload: LoginIn, request: Request) -> Dict[str, Any]:
    user = users.get_user(payload.username)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not bool(user.get("is_active", True)):
        raise HTTPException(status_code=403, detail="User disabled")

    request.session["user"] = build_session_user(user)
    users.set_last_login(user["username"])
    return {"ok": True, "user": request.session["user"]}


@app.post("/logout")
def logout(request: Request) -> Dict[str, Any]:
    request.session.clear()
    return {"ok": True}


@app.get("/me")
def me(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {"ok": True, "user": user}


@app.get("/stats")
def stats(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    channels = store.list()
    total = len(channels)
    running = 0
    stopped = 0
    error = 0
    disabled = 0

    for ch in channels:
        if not bool(ch.get("enabled", True)):
            disabled += 1
        status = ff.status(ch["id"])
        if status == "running":
            running += 1
        elif status == "error":
            error += 1
        else:
            stopped += 1

    return {
        "ok": True,
        "total": total,
        "running": running,
        "stopped": stopped,
        "error": error,
        "disabled": disabled,
    }


@app.get("/channels", response_model=List[ChannelOut])
def list_channels(user: Dict[str, Any] = Depends(get_current_user)) -> List[ChannelOut]:
    return [channel_to_out(ch) for ch in store.list()]


@app.get("/channels/{channel_id}", response_model=ChannelOut)
def get_channel(channel_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> ChannelOut:
    ch = store.get(channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel_to_out(ch)


@app.post("/channels", response_model=ChannelOut)
def upsert_channel(payload: ChannelIn, user: Dict[str, Any] = Depends(require_admin)) -> ChannelOut:
    store.upsert(payload.model_dump())
    return channel_to_out(payload.model_dump())


@app.delete("/channels/{channel_id}")
def delete_channel(channel_id: str, user: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    ff.stop(channel_id)
    store.delete(channel_id)
    return {"ok": True}


@app.post("/channels/{channel_id}/start")
def start_channel(channel_id: str, user: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    ch = store.get(channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")

    if not bool(ch.get("enabled", True)):
        raise HTTPException(status_code=400, detail="Channel disabled")

    ff.start(
        channel_id=channel_id,
        source_url=ch["source_url"],
        profile=ch.get("profile", "copy"),
    )
    return {
        "ok": True,
        "running": ff.is_running(channel_id),
        "status": ff.status(channel_id),
        "hls_url": ff.hls_url(channel_id),
        "last_error": ff.last_error(channel_id),
    }


@app.post("/channels/{channel_id}/stop")
def stop_channel(channel_id: str, user: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    ff.stop(channel_id)
    return {"ok": True, "running": ff.is_running(channel_id), "status": ff.status(channel_id)}


@app.get("/channels/{channel_id}/log")
def channel_log(channel_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {
        "channel_id": channel_id,
        "log_path": ff.log_path(channel_id),
        "last_error": ff.last_error(channel_id),
        "running": ff.is_running(channel_id),
        "status": ff.status(channel_id),
        "tail": ff.read_log_tail(channel_id, lines=80),
    }


@app.get("/channels/{channel_id}/metrics")
def channel_metrics(channel_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    ch = store.get(channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"ok": True, "channel_id": channel_id, **ff.metrics(channel_id)}
