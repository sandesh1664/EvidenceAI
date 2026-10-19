from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import update, func
from sqlalchemy.orm import Session
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import AuthSession, User
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse, RegistrationAccepted, VerifyRegistrationRequest
from app.services import auth_service, registration_service

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


def registration_cookie(settings):
    return ('__Host-' if settings.secure_cookies else '')+'evidenceai_registration'


@router.post("/register", response_model=RegistrationAccepted, status_code=202, dependencies=[Depends(auth_attempt)])
def register(data: RegisterRequest, response: Response, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    auth_service.rate_limit(db,settings,"registration-email:"+data.email,"registration-email")
    browser=registration_service.request_registration(db,data,settings)
    response.set_cookie(registration_cookie(settings),browser,httponly=True,secure=settings.secure_cookies,
        samesite='lax',path='/',max_age=settings.registration_ttl_seconds)
    return RegistrationAccepted()


@router.post('/verify-registration',status_code=202,dependencies=[Depends(auth_attempt)])
def verify_registration(data: VerifyRegistrationRequest, request: Request, response: Response,
        db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    registration_service.verify_registration(db,data.token.get_secret_value(),request.cookies.get(registration_cookie(settings)))
    response.delete_cookie(registration_cookie(settings),path='/',httponly=True,secure=settings.secure_cookies,samesite='lax')
    return {'detail':'Registration verified. You can now sign in with your credentials.'}


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
