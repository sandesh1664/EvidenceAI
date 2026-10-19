"""Uniform enrollment: no existing-email lookup until browser-bound email proof.

Neither registration nor verification creates a session or resets an existing
password. Email links alone cannot activate attacker-initiated registrations.
"""
from datetime import timedelta
import hmac
import re
import smtplib
import ssl
from email.message import EmailMessage
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from app.core.security import hash_token, new_session_token, password_hasher
from app.models import RegistrationIntent, User


def deliver(settings, email, token):
    if not settings.registration_email_enabled:
        return False
    message=EmailMessage()
    message['From']=settings.smtp_sender
    message['To']=email
    message['Subject']='Verify your EvidenceAI registration request'
    message.set_content('If you requested an EvidenceAI account, open this link in the SAME browser that submitted the request. '
        'Otherwise ignore this email. This does not reset any existing password.\n\n'
        +settings.registration_public_origin+'/verify-email#token='+token)
    # Implicit TLS with certificate/hostname verification. Never a plaintext fallback.
    context=ssl.create_default_context()
    if settings.smtp_ca_file: context.load_verify_locations(cafile=str(settings.smtp_ca_file))
    with smtplib.SMTP_SSL(settings.smtp_host,settings.smtp_port,timeout=10,context=context) as smtp:
        if settings.smtp_username:
            smtp.login(settings.smtp_username,settings.smtp_password.get_secret_value() if settings.smtp_password else '')
        smtp.send_message(message)
    return True


def request_registration(db,data,settings):
    token,browser=new_session_token(),new_session_token()
    # Always perform Argon2id and the same insert, even for existing/inactive emails.
    encoded=password_hasher.hash(data.password.get_secret_value())
    now=db.scalar(select(func.clock_timestamp()))
    expired=select(RegistrationIntent.id).where(RegistrationIntent.expires_at<now).order_by(RegistrationIntent.expires_at).limit(100)
    db.execute(delete(RegistrationIntent).where(RegistrationIntent.id.in_(expired)))
    db.add(RegistrationIntent(email=data.email,display_name=data.display_name,password_hash=encoded,
        token_hash=hash_token(token),browser_hash=hash_token(browser),expires_at=now+timedelta(seconds=settings.registration_ttl_seconds)))
    db.commit()
    try:
        deliver(settings,data.email,token)
    except Exception:
        # Identical public response; no recipient/token/SMTP diagnostic in logs.
        pass
    return browser


def verify_registration(db,token,browser):
    if not browser or not re.fullmatch(r'[A-Za-z0-9_-]{43}',browser) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):
        raise HTTPException(400,'Verification unavailable; use the requesting browser and request a new link')
    intent=db.scalar(select(RegistrationIntent).where(RegistrationIntent.token_hash==hash_token(token)).with_for_update())
    now=db.scalar(select(func.clock_timestamp()))
    if not intent or intent.expires_at<=now or not hmac.compare_digest(intent.browser_hash,hash_token(browser)):
        db.rollback()
        raise HTTPException(400,'Verification unavailable; use the requesting browser and request a new link')
    # Unique normalized email index serializes competing verified requests. Existing
    # credentials, names, disabled status and sessions are never updated.
    db.execute(insert(User).values(email=intent.email,display_name=intent.display_name,password_hash=intent.password_hash).on_conflict_do_nothing())
    db.delete(intent)
    db.commit()
