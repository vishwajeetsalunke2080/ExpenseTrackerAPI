from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class AccountTypeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class AccountTypeCreate(AccountTypeBase):
    pass


class AccountTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)


class AccountTypeResponse(AccountTypeBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_default: bool
