from pydantic import BaseModel
import datetime
from typing import Optional

class LoginRequest(BaseModel):
    user_id: str
    password: str

class User(BaseModel):
    id: int
    username: str

class LoginData(BaseModel):
    token: str
    user: User

class TokenResponse(BaseModel):
    data: LoginData
    status: str
    message: str

class SimpleTokenResponse(BaseModel):
    token: str

class TokenData(BaseModel):
    user_id: str
    exp: datetime.datetime
