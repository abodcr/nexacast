from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Literal

class ChannelCreate(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    app: str = Field(default="live", min_length=1, max_length=32)
    stream: str = Field(min_length=1, max_length=128)
    source_url: str

class ChannelOut(BaseModel):
    id: str
    app: str
    stream: str
    source_url: str
    hls_url: str
    status: Literal["stopped", "running"]
    last_error: Optional[str] = None