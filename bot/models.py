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
