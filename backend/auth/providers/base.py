"""Interfaz común para proveedores OAuth (fase 2)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OAuthUserInfo:
    email: str
    name: str
    provider: str
    provider_id: str


class OAuthProvider(ABC):
    name: str

    @abstractmethod
    def get_authorize_url(self, state: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def exchange_code(self, code: str) -> OAuthUserInfo:
        raise NotImplementedError
