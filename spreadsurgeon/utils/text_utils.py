"""Utilitários de texto e formatação."""

import re
import unicodedata
from typing import Optional

from spreadsurgeon.config import RE_SCIENTIFIC, RE_ONLY_DIGITS, GTIN_LENGTHS


def normalize_text(text: str) -> str:
    """Remove acentos e normaliza espaços."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_str = nfkd.encode("ASCII", "ignore").decode("ASCII")
    return re.sub(r"\s+", " ", ascii_str).strip()


def safe_str(value) -> str:
    """Converte qualquer valor para string preservando zeros à esquerda."""
    if value is None:
        return ""
    s = str(value).strip()
    # Remove notação científica em campos numéricos textuais
    if RE_SCIENTIFIC.match(s):
        try:
            return str(int(float(s)))
        except (ValueError, OverflowError):
            return s
    return s


def is_scientific_notation(value) -> bool:
    s = str(value).strip()
    return bool(RE_SCIENTIFIC.match(s))


def validate_ean(ean: str) -> tuple[bool, str]:
    """Valida EAN/GTIN. Retorna (valido, mensagem)."""
    ean = safe_str(ean).replace("-", "").replace(" ", "")
    if not ean:
        return False, "EAN vazio"
    if not RE_ONLY_DIGITS.match(ean):
        return False, f"EAN contém caracteres não numéricos: '{ean}'"
    if len(ean) not in GTIN_LENGTHS:
        return False, f"EAN com {len(ean)} dígitos (esperado: 8, 12, 13 ou 14)"
    if not _check_gtin_digit(ean):
        return False, f"Dígito verificador inválido para EAN '{ean}'"
    return True, "EAN válido"


def _check_gtin_digit(ean: str) -> bool:
    digits = [int(d) for d in ean]
    check = digits[-1]
    rest   = digits[:-1]
    total = 0
    for i, d in enumerate(reversed(rest)):
        total += d * (3 if i % 2 == 0 else 1)
    calc = (10 - (total % 10)) % 10
    return calc == check


def validate_ncm(ncm: str) -> tuple[bool, str]:
    ncm = safe_str(ncm).replace(".", "").replace("-", "").replace(" ", "")
    if not ncm:
        return False, "NCM vazio"
    if not RE_ONLY_DIGITS.match(ncm):
        return False, f"NCM contém caracteres não numéricos: '{ncm}'"
    if len(ncm) != 8:
        return False, f"NCM com {len(ncm)} dígitos (esperado: 8)"
    return True, "NCM válido"


def price_to_float(value: str) -> Optional[float]:
    """Converte string de preço BR (vírgula decimal) ou US (ponto decimal) para float."""
    s = str(value).strip()
    # Remove símbolo R$
    s = re.sub(r"[R$\s]", "", s)
    # Formato BR: 1.234,56
    if re.match(r"^\d{1,3}(\.\d{3})*(,\d{2})?$", s):
        s = s.replace(".", "").replace(",", ".")
    # Formato US: 1,234.56
    elif re.match(r"^\d{1,3}(,\d{3})*(\.\d{2})?$", s):
        s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def truncate(text: str, max_len: int, suffix: str = "...") -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)].rstrip() + suffix


def title_case_br(text: str) -> str:
    """Title case respeitando palavras de ligação em português."""
    prepositions = {"de", "da", "do", "das", "dos", "em", "no", "na",
                    "nos", "nas", "a", "e", "o", "com", "para", "por",
                    "ao", "aos", "as", "um", "uma", "ou"}
    words = text.split()
    result = []
    for i, w in enumerate(words):
        if i == 0 or w.lower() not in prepositions:
            result.append(w.capitalize())
        else:
            result.append(w.lower())
    return " ".join(result)


def extract_internal_code(text: str) -> tuple[str, Optional[str]]:
    """
    Move código interno entre parênteses para o final do título.
    Retorna (titulo_limpo, codigo_extraido).
    """
    pattern = re.compile(r"\(([A-Za-z0-9\-_/]+)\)")
    match = pattern.search(text)
    if match:
        code = match.group(1)
        clean = pattern.sub("", text).strip()
        clean = re.sub(r"\s+", " ", clean)
        return clean, code
    return text, None
