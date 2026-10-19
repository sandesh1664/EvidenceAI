import re
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, func, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import Settings
from app.core.security import hash_token, new_session_token, password_hasher, verify_password
from app.models import User, AuthSession, AuthRateLimit
from app.schemas.auth import RegisterRequest, LoginRequest


def rate_limit(db: Session, settings: Settings, client: str, action: str):
    # An atomic PostgreSQL upsert serializes competing workers for this IP/window.
    seconds = settings.auth_rate_window_seconds
    now = db.scalar(select(func.clock_timestamp()))
    start = datetime.fromtimestamp(int(now.timestamp()) // seconds * seconds, timezone.utc)
    statement = insert(AuthRateLimit).values(key=hash_token(action + ":" + client),
                                           window_start=start, attempts=1)
    count = db.scalar(statement.on_conflict_do_update(
        index_elements=[AuthRateLimit.key, AuthRateLimit.window_start],
        set_={"attempts": AuthRateLimit.attempts + 1}).returning(AuthRateLimit.attempts))
    db.commit()  # Failed authentication must not roll back the attempt counter.
    if count > settings.auth_rate_limit:
        raise HTTPException(429, "Too many authentication attempts", headers={"Retry-After": str(seconds)})


def register(db: Session, data: RegisterRequest) -> User:
    user = User(email=data.email, display_name=data.display_name,
                password_hash=password_hasher.hash(data.password.get_secret_value()))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email is already registered") from None
    return user


def login(db: Session, data: LoginRequest, settings: Settings):
    user = db.scalar(select(User).where(func.lower(func.btrim(User.email)) == data.email))
    valid = verify_password(user.password_hash if user else None, data.password.get_secret_value())
    if not valid or not user or not user.is_active:
        raise HTTPException(401, "Invalid email or password")
    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = password_hasher.hash(data.password.get_secret_value())
    token = new_session_token()
    now = db.scalar(select(func.clock_timestamp()))
    session = AuthSession(user_id=user.id, token_hash=hash_token(token),
                          expires_at=now + timedelta(seconds=settings.session_ttl_seconds))
    db.add(session)
    db.commit()
    return user, token


def current_session(db: Session, token: str | None):
    if not token or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise HTTPException(401, "Authentication required")
    row = db.execute(select(AuthSession, User).join(User, User.id == AuthSession.user_id).where(
        AuthSession.token_hash == hash_token(token), AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > func.clock_timestamp(), User.is_active.is_(True))).first()
    if not row:
        raise HTTPException(401, "Authentication required")
    return row


def touch_session(db: Session, session: AuthSession):
    db.execute(update(AuthSession).where(AuthSession.id == session.id,
               AuthSession.revoked_at.is_(None)).values(last_used_at=func.clock_timestamp()))
    db.commit()
