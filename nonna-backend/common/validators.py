"""Validaciones de servidor reutilizables."""
import re

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,180}\.[A-Za-z]{2,24}$")
PHONE_RE = re.compile(r"^\+?[0-9]{8,15}$")
RUN_RE = re.compile(r"^(\d{7,8})-([\dkK])$")


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if not EMAIL_RE.match(value):
        raise ValueError("correo inválido")
    return value


def validate_run(value: str) -> str:
    """Valida un RUN chileno con dígito verificador (formato 12345678-9, sin puntos)."""
    value = value.strip().replace(".", "")
    m = RUN_RE.match(value)
    if not m:
        raise ValueError("RUN inválido: use el formato 12345678-9")
    body, dv = m.group(1), m.group(2).upper()
    total, factor = 0, 2
    for digit in reversed(body):
        total += int(digit) * factor
        factor = 2 if factor == 7 else factor + 1
    expected = 11 - (total % 11)
    expected_dv = {11: "0", 10: "K"}.get(expected, str(expected))
    if dv != expected_dv:
        raise ValueError("RUN inválido: dígito verificador incorrecto")
    return f"{body}-{dv}"


def validate_phone(value: str) -> str:
    value = value.replace(" ", "")
    if not PHONE_RE.match(value):
        raise ValueError("teléfono inválido")
    return value


def mask_run(run: str | None) -> str | None:
    return None if not run else "****" + run[-5:]


def mask_phone(phone: str | None) -> str | None:
    return None if not phone else phone[:4] + "*****" + phone[-2:]
