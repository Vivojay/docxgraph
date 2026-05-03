from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    org_name: str
    email: EmailStr
    password: str
    specialty: str | None = None
    years_experience: int | None = None
    region: str | None = None
