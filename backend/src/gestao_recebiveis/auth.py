import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Request
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from gestao_recebiveis.clock import utcnow
from gestao_recebiveis.config import get_settings
from gestao_recebiveis.database import get_session
from gestao_recebiveis.errors import DomainError
from gestao_recebiveis.models import LoginSession, User

password_hasher = PasswordHash.recommended()
Db = Annotated[Session, Depends(get_session, scope="function")]


def token_digest(token: str) -> str:
    return hmac.new(
        get_settings().session_secret.encode(), token.encode(), hashlib.sha256
    ).hexdigest()


def check_origin(request: Request) -> None:
    if request.headers.get("origin") != get_settings().frontend_origin:
        raise DomainError("invalid_origin", "Origem da operação não permitida.", 403)


def current_user(request: Request, session: Db) -> User:
    token = request.cookies.get("cf_session", "")
    login = session.get(LoginSession, token_digest(token)) if token else None
    if login is None or login.expires_at <= utcnow():
        raise DomainError("unauthenticated", "Sessão expirada. Entre novamente.", 401)
    user = session.get(User, login.user_id)
    if user is None or (user.is_demo and not get_settings().demo_mode):
        raise DomainError("unauthenticated", "Sessão inválida.", 401)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        check_origin(request)
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), login.csrf_token):
            raise DomainError(
                "csrf", "Confirmação de segurança inválida. Recarregue a página.", 403
            )
    request.state.login = login
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_operator(user: CurrentUser) -> User:
    if user.role != "operator":
        raise DomainError("forbidden", "Exige perfil operador.", 403)
    return user


Operator = Annotated[User, Depends(require_operator)]


def authenticate(session: Session, email: str, password: str) -> User:
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    # The fallback hash avoids returning immediately for an unknown account.
    hashed = user.password_hash if user else DUMMY_HASH
    valid = password_hasher.verify(password, hashed)
    if not user or not valid or (user.is_demo and not get_settings().demo_mode):
        raise DomainError("invalid_credentials", "E-mail ou senha incorretos.", 401)
    return user


def create_login(session: Session, user: User) -> tuple[str, LoginSession]:
    token = secrets.token_urlsafe(32)
    login = LoginSession(
        token_hash=token_digest(token),
        user_id=user.id,
        csrf_token=secrets.token_urlsafe(32),
        expires_at=utcnow() + timedelta(hours=get_settings().session_hours),
    )
    session.add(login)
    return token, login


DUMMY_HASH = password_hasher.hash("unused-random-local-verification")
