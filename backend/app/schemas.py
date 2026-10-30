# -*- coding: utf-8 -*-
"""Pydantic 请求/响应模型。"""
from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=6, max_length=64)
    nickname: str = Field(default="", max_length=50)


class LoginIn(BaseModel):
    phone: str
    password: str


class TokenOut(BaseModel):
    token: str
    token_type: str = "bearer"
    user_id: int
    nickname: str
    role: str


class SessionCreateIn(BaseModel):
    title: str = "新的对话"
    persona_id: str = "nuan"


class MessageIn(BaseModel):
    content: str = Field(default="", max_length=2000)
    msg_type: str = "text"      # text / image / voice
    image_url: str = ""


class UserUpdateIn(BaseModel):
    nickname: str | None = None
    password: str | None = None
    is_active: bool | None = None


class ProfileUpdateIn(BaseModel):
    nickname: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, min_length=6, max_length=20)
    avatar: str | None = Field(default=None, max_length=255)
    old_password: str | None = None
    new_password: str | None = Field(default=None, min_length=6, max_length=64)


class SessionRenameIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class CalibrateIn(BaseModel):
    message_id: int
    emotion_type: str


class PostIn(BaseModel):
    title: str = Field(default="", max_length=120)
    content: str = Field(default="", max_length=5000)
    tags: list[str] = []
    image_urls: list[str] = []
    blocks: list[dict] = []


class CommentIn(BaseModel):
    content: str = Field(min_length=1, max_length=1000)