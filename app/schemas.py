from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator
class AccountCreate(BaseModel):
    account_number: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    owner_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, value: str) -> str:
        value = value.upper()
        if not value.isascii() or not value.isalpha():
            raise ValueError("Currency must contain three ASCII letters")
        return value
class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    account_number: str
    owner_id: str
    currency: str
    balance: Decimal
    status: str
    created_at: datetime
class AmountRequest(BaseModel):
    amount: Decimal = Field(gt=Decimal("0"), max_digits=18, decimal_places=2)
    @field_validator("amount")
    @classmethod
    def amount_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value.as_tuple().exponent < -2:
            raise ValueError("Amount must be finite with at most two decimal places")
        return value
class TransferRequest(AmountRequest):
    source_account: str = Field(min_length=1, max_length=32)
    destination_account: str = Field(min_length=1, max_length=32)
