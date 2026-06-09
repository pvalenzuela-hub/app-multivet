# appclinica/utils/rut.py
import re

RUT_INPUT_RE = re.compile(r"^\s*0*\d{7,8}-[0-9Kk]\s*$")


def _rut_clean(raw: str) -> str:
    r = (raw or "").strip().upper()
    r = re.sub(r"[^0-9K]", "", r)
    return r

def rut_dv(cuerpo: str) -> str:
    # cuerpo: solo dígitos (sin dv)
    reversed_digits = map(int, reversed(cuerpo))
    factors = [2, 3, 4, 5, 6, 7]
    s = 0
    for i, d in enumerate(reversed_digits):
        s += d * factors[i % len(factors)]
    mod = 11 - (s % 11)
    if mod == 11:
        return "0"
    if mod == 10:
        return "K"
    return str(mod)

def rut_validate_and_format(raw: str) -> str:
    """
    Exige formato con guion, valida DV y retorna formato canonico: 99999999-X
    """
    if not RUT_INPUT_RE.match(raw or ""):
        raise ValueError("RUT invalido. Use el formato 9999999-X.")

    r = _rut_clean(raw)
    if len(r) < 2:
        raise ValueError("RUT invalido.")

    cuerpo, dv = r[:-1], r[-1]

    # elimina ceros a la izquierda
    try:
        cuerpo_int = int(cuerpo)
    except ValueError:
        raise ValueError("RUT invalido.")

    if cuerpo_int <= 0:
        raise ValueError("RUT invalido.")

    cuerpo = str(cuerpo_int)  # <- aquí se eliminan ceros a la izquierda

    dv_calc = rut_dv(cuerpo)
    if dv != dv_calc:
        raise ValueError("RUT invalido (digito verificador no coincide).")

    return f"{cuerpo}-{dv}"
