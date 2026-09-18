"""Stub Google OAuth — implementar en fase 2."""

from auth.providers.base import OAuthProvider, OAuthUserInfo


class GoogleOAuthProvider(OAuthProvider):
    name = 'google'

    def get_authorize_url(self, state: str) -> str:
        raise NotImplementedError('Google OAuth aún no está habilitado')

    def exchange_code(self, code: str) -> OAuthUserInfo:
        raise NotImplementedError('Google OAuth aún no está habilitado')
