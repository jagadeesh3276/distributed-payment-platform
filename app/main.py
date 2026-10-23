from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from fastapi import Depends, FastAPI, Header, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Account, Transfer, LedgerEntry, IdempotencyRecord, OutboxEvent
from app.schemas import AccountCreate, AccountOut, AmountRequest, TransferRequest
from app.security import enforce_rate_limit, request_hash
import os

app = FastAPI(title="Distributed Payment Platform", version="1.0.0")
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

@app.get("/health")
def health():
    return {"status":"ok","service":"transaction-service","instance":os.getenv("INSTANCE_NAME","local")}

@app.get("/health/ready")
def readiness(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status":"ready","database":"connected"}

@app.post("/accounts", response_model=AccountOut, status_code=201, dependencies=[Depends(enforce_rate_limit)])
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    account = Account(account_number=payload.account_number, owner_id=payload.owner_id, currency=payload.currency, balance=Decimal("0.00"))
    db.add(account)
    try:
        db.commit(); db.refresh(account); return account
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Account already exists or violates a database constraint") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database operation failed") from exc

@app.get("/accounts/{account_number}", response_model=AccountOut, dependencies=[Depends(enforce_rate_limit)])
def get_account(account_number: str, db: Session = Depends(get_db)):
    account = db.scalar(select(Account).where(Account.account_number == account_number))
    if not account: raise HTTPException(status_code=404, detail="Account not found")
    return account

def cached_response(db: Session, key: str | None, digest: str):
    if not key: return None
    rec = db.scalar(select(IdempotencyRecord).where(IdempotencyRecord.key == key))
    if not rec: return None
    if rec.request_hash != digest:
        raise HTTPException(status_code=409, detail="Idempotency key reused with different payload")
    return rec.response_body

def save_key(db: Session, key: str | None, digest: str, body: dict):
    if key: db.add(IdempotencyRecord(key=key, request_hash=digest, response_status=200, response_body=body))

@app.post("/accounts/{account_number}/deposits", dependencies=[Depends(enforce_rate_limit)])
def deposit(account_number: str, payload: AmountRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), db: Session = Depends(get_db)):
    digest = request_hash({"op":"deposit","account":account_number,"amount":payload.amount})
    cached = cached_response(db,idempotency_key,digest)
    if cached is not None: return cached
    account = db.scalar(select(Account).where(Account.account_number == account_number).with_for_update())
    if not account: raise HTTPException(status_code=404, detail="Account not found")
    account.balance += payload.amount
    body = {"account_number":account.account_number,"balance":str(account.balance),"currency":account.currency}
    save_key(db,idempotency_key,digest,body)
    try: db.commit(); return body
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Idempotency conflict") from exc

@app.post("/accounts/{account_number}/withdrawals", dependencies=[Depends(enforce_rate_limit)])
def withdraw(account_number: str, payload: AmountRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), db: Session = Depends(get_db)):
    digest = request_hash({"op":"withdraw","account":account_number,"amount":payload.amount})
    cached = cached_response(db,idempotency_key,digest)
    if cached is not None: return cached
    account = db.scalar(select(Account).where(Account.account_number == account_number).with_for_update())
    if not account: raise HTTPException(status_code=404, detail="Account not found")
    if account.balance < payload.amount: raise HTTPException(status_code=422, detail="Insufficient funds")
    account.balance -= payload.amount
    body = {"account_number":account.account_number,"balance":str(account.balance),"currency":account.currency}
    save_key(db,idempotency_key,digest,body)
    try: db.commit(); return body
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Idempotency conflict") from exc

@app.post("/transfers", status_code=201, dependencies=[Depends(enforce_rate_limit)])
def transfer(payload: TransferRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), db: Session = Depends(get_db)):
    if payload.source_account == payload.destination_account:
        raise HTTPException(status_code=422, detail="Source and destination must differ")
    digest = request_hash({"op":"transfer",**payload.model_dump()})
    cached = cached_response(db,idempotency_key,digest)
    if cached is not None: return cached
    accounts = db.scalars(select(Account).where(Account.account_number.in_([payload.source_account,payload.destination_account])).order_by(Account.account_number).with_for_update()).all()
    by_number = {a.account_number:a for a in accounts}
    source,dest = by_number.get(payload.source_account),by_number.get(payload.destination_account)
    if not source or not dest: raise HTTPException(status_code=404, detail="Source or destination account not found")
    if source.status != "active" or dest.status != "active": raise HTTPException(status_code=409, detail="Accounts must be active")
    if source.currency != dest.currency: raise HTTPException(status_code=422, detail="Currency mismatch")
    if source.balance < payload.amount: raise HTTPException(status_code=422, detail="Insufficient funds")
    ref = str(uuid4())
    source.balance -= payload.amount; dest.balance += payload.amount
    db.add(Transfer(reference=ref,source_account=source.account_number,destination_account=dest.account_number,amount=payload.amount,currency=source.currency,status="completed"))
    db.add_all([
        LedgerEntry(transfer_reference=ref,account_number=source.account_number,direction="debit",amount=payload.amount,currency=source.currency),
        LedgerEntry(transfer_reference=ref,account_number=dest.account_number,direction="credit",amount=payload.amount,currency=source.currency)
    ])
    event = {"reference":ref,"source_account":source.account_number,"destination_account":dest.account_number,"amount":str(payload.amount),"currency":source.currency,"status":"completed"}
    db.add(OutboxEvent(event_type="transfer.completed",aggregate_id=ref,payload=event))
    body = {**event,"created_at":datetime.now(timezone.utc).isoformat()}
    save_key(db,idempotency_key,digest,body)
    try: db.commit(); return body
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Idempotency conflict; retry with same key and payload") from exc
    except SQLAlchemyError as exc:
        db.rollback(); raise HTTPException(status_code=503, detail="Transfer could not be committed") from exc

@app.get("/accounts/{account_number}/ledger", dependencies=[Depends(enforce_rate_limit)])
def ledger(account_number: str, db: Session = Depends(get_db)):
    if not db.scalar(select(Account.id).where(Account.account_number == account_number)):
        raise HTTPException(status_code=404, detail="Account not found")
    entries = db.scalars(select(LedgerEntry).where(LedgerEntry.account_number == account_number).order_by(LedgerEntry.id.desc()).limit(100)).all()
    return [{"transfer_reference":e.transfer_reference,"direction":e.direction,"amount":str(e.amount),"currency":e.currency,"created_at":e.created_at.isoformat() if e.created_at else None} for e in entries]
