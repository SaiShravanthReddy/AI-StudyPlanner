from __future__ import annotations

from dataclasses import dataclass
from secrets import compare_digest
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    token: str


class AuthService:
    def __init__(self, settings: Settings):
        self._tokens_by_user = self._parse_tokens(settings.auth_user_tokens)

    def authenticate(self, token: Optional[str]) -> AuthenticatedUser:
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
        for user_id, expected_token in self._tokens_by_user.items():
            if compare_digest(expected_token, token):
                return AuthenticatedUser(user_id=user_id, token=token)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token.")

    def assert_user(self, expected_user_id: str, actual_user: AuthenticatedUser) -> None:
        if expected_user_id != actual_user.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden for requested user.")

    def _parse_tokens(self, raw_tokens: str) -> dict[str, str]:
        parsed: dict[str, str] = {}
        for chunk in raw_tokens.split(","):
            entry = chunk.strip()
            if not entry:
                continue
            user_id, separator, token = entry.partition(":")
            if not separator or not user_id.strip() or not token.strip():
                raise ValueError("AUTH_USER_TOKENS must be a comma-separated list of user_id:token pairs.")
            parsed[user_id.strip()] = token.strip()
        if not parsed:
            raise ValueError("AUTH_USER_TOKENS must define at least one user_id:token pair.")
        return parsed


def get_auth_service(settings: Settings = Depends(get_settings)) -> AuthService:
    return AuthService(settings)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthenticatedUser:
    token = credentials.credentials if credentials else None
    return auth_service.authenticate(token)
