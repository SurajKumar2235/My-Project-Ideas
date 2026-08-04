from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class Draft(BaseModel):
    id: Optional[int] = None
    chat_id: int
    user_id: int
    content: str
    created_at: Optional[datetime] = None

class Lock(BaseModel):
    issue_number: int
    repo: str
    locked_by_user_id: Optional[int] = None
    locked_by_username: Optional[str] = None
    locked_at: Optional[datetime] = None
    status: str = Field(default="todo")  # todo | doing | done

class User(BaseModel):
    id: Optional[int] = None
    github_id: Optional[int] = None
    username: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    access_token: Optional[str] = None
    role: str = Field(default="user")  # dev | user | admin | owner
    created_at: Optional[datetime] = None
    
class UsersChannel(BaseModel):
    chat_id: int
    user_id: int
    telegram_username: Optional[str] = None
    telegram_channel_id: Optional[str] = None
     

