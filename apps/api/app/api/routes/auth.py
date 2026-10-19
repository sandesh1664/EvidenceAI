from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import update, func
from sqlalchemy.orm import Session
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import AuthSession, User
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def authenticated_session(request: Request, db: Session = Depends(get_db),
                          settings: Settings = Depends(get_settings)):
    return auth_service.current_session(db, request.cookies.get(settings.session_cookie_name))


def get_current_user(identity=Depends(authenticated_session), db: Session = Depends(get_db)) -> User:
    session, user = identity
    auth_service.touch_session(db, session)
    return user


def auth_attempt(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    # Forwarded/X-Forwarded-For headers are deliberately ignored here.
    auth_service.rate_limit(db, settings, request.client.host if request.client else "unknown", request.url.path)


@router.post("/register", response_model=UserResponse, status_code=201, dependencies=[Depends(auth_attempt)])
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    return auth_service.register(db, data)


@router.post("/login", response_model=UserResponse, dependencies=[Depends(auth_attempt)])
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db),
          settings: Settings = Depends(get_settings)):
    user, token = auth_service.login(db, data, settings)
    response.set_cookie(settings.session_cookie_name, token, httponly=True,
                        secure=settings.secure_cookies, samesite="lax", path="/")
    return user


@router.post("/logout", status_code=204)
def logout(response: Response, identity=Depends(authenticated_session), db: Session = Depends(get_db),
           settings: Settings = Depends(get_settings)):
    session, _ = identity
    db.execute(update(AuthSession).where(AuthSession.id == session.id).values(revoked_at=func.clock_timestamp()))
    db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.secure_cookies,
                           httponly=True, samesite="lax")


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user
