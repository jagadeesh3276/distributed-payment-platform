from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.schemas import AmountRequest, AccountCreate
def test_amount_accepts_decimal():
    assert AmountRequest(amount=Decimal("12.34")).amount == Decimal("12.34")
def test_amount_rejects_zero():
    with pytest.raises(ValidationError): AmountRequest(amount=Decimal("0.00"))
def test_amount_rejects_more_than_two_decimal_places():
    with pytest.raises(ValidationError): AmountRequest(amount=Decimal("1.234"))
def test_currency_uppercase():
    assert AccountCreate(account_number="A1",owner_id="U1",currency="inr").currency == "INR"
