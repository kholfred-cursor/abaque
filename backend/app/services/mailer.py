"""Outgoing email. ConsoleMailer is for development only (startup fails in production)."""

from __future__ import annotations

import logging
import sys
from typing import Literal, Protocol

logger = logging.getLogger(__name__)

Template = Literal["verify_email", "reset_password", "account_exists"]

TEMPLATES: dict[Template, tuple[str, str]] = {
    "verify_email": (
        "Confirmez votre adresse e-mail",
        "Bonjour,\n\nPour activer votre compte Abaque, ouvrez ce lien (valable 24 heures) :\n"
        "{link}\n\nSi vous n'êtes pas à l'origine de cette demande, ignorez ce message.",
    ),
    "reset_password": (
        "Réinitialisation de votre mot de passe",
        "Bonjour,\n\nPour choisir un nouveau mot de passe, ouvrez ce lien "
        "(valable 30 minutes) :\n{link}\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.",
    ),
    "account_exists": (
        "Vous avez déjà un compte Abaque",
        "Bonjour,\n\nUne inscription a été demandée avec cette adresse, qui a déjà un compte.\n"
        "Pour vous connecter : {link}\nMot de passe oublié ? Utilisez « Mot de passe oublié » "
        "sur la page de connexion.",
    ),
}


class Mailer(Protocol):
    async def send(self, to: str, template: Template, context: dict[str, str]) -> None: ...


def mask_email(address: str) -> str:
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def render(template: Template, context: dict[str, str]) -> tuple[str, str]:
    subject, body = TEMPLATES[template]
    return subject, body.format(**context)


class ConsoleMailer:
    """Development mailer: the structured log keeps only a masked recipient; the readable
    message (with its link) goes to stderr so a developer can click it locally."""

    async def send(self, to: str, template: Template, context: dict[str, str]) -> None:
        subject, body = render(template, context)
        logger.info("Email %s queued for %s", template, mask_email(to))
        sys.stderr.write(f"\n--- DEV EMAIL ({template}) ---\nSubject: {subject}\n{body}\n---\n")
