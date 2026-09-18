"""Stub GitHub OAuth — implementar en fase 2."""

from auth.providers.base import OAuthProvider, OAuthUserInfo


class GitHubOAuthProvider(OAuthProvider):
    name = 'github'

    def get_authorize_url(self, state: str) -> str:
        raise NotImplementedError('GitHub OAuth aún no está habilitado')

    def exchange_code(self, code: str) -> OAuthUserInfo:
        raise NotImplementedError('GitHub OAuth aún no está habilitado')
