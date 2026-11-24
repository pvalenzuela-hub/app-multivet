from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


class EncryptedCharField(models.CharField):
    """CharField cifrado en reposo mediante la clave Fernet configurada."""

    @staticmethod
    def _fernet():
        return Fernet(settings.SMTP_CREDENTIAL_ENCRYPTION_KEY.encode("ascii"))

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return self._fernet().decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            if value.startswith("gAAAA"):
                raise
            # Compatibilidad temporal con valores previos a la migración de cifrado.
            return value
        except UnicodeEncodeError:
            return value

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        try:
            self._fernet().decrypt(value.encode("utf-8"))
            return value
        except (InvalidToken, UnicodeEncodeError):
            return self._fernet().encrypt(value.encode("utf-8")).decode("utf-8")
