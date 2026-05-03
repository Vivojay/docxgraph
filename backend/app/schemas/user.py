from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: str
    specialty: str | None
    years_experience: int | None
    region: str | None
    is_verified: bool
    is_available: bool
    org_id: int

    class Config:
        from_attributes = True
