from pydantic import BaseModel, EmailStr

# Request bodies
class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

# Token response
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"