import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    expires_in: int
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
