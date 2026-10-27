"""Language detection heuristic for Uzbek, Russian, and English."""
from __future__ import annotations

import re
from typing import Optional, Set

APOSTROPHES = "'ʻ’‘`"
APOSTROPHE_PATTERN = f"[{APOSTROPHES}]"

UZBEK_CYRILLIC_SPECIAL: Set[str] = set("ўқғҳЎҚҒҲ")

UZBEK_CYRILLIC_WORDS: Set[str] = {
    "салом", "рахмат", "раҳмат", "яхши", "нима", "қалесан", "калесан", "йўқ", "йук",
    "бугун", "эртага", "керак", "ассалому", "алайкум", "ҳа", "хоп", "бўпти", "бопти",
    "ҳозир", "хозир", "қаерда", "кайерда", "қандай", "қандайсиз", "яхшимисиз", "сиз",
    "мен", "сен", "биз", "улар", "бор", "қайда", "қаердасан", "раҳмат", "шунақа",
    "албатта", "майли", "тушундим", "чиройли", "соғ", "омон", "зур", "зўр"
}

UZBEK_LATIN_WORDS: Set[str] = {
    "salom", "rahmat", "yaxshi", "nima", "qalesan", "qayerda", "bugun", "ertaga",
    "kerak", "xop", "hop", "bopti", "zor", "hozir", "keyin", "men", "sen", "siz",
    "assalomu", "alaykum", "ha", "yoq", "qanday", "chunki", "bilan", "uchun", "biz",
    "ular", "bor", "bormisiz", "mayli", "albatta", "tushundim", "shunaqa", "qaerdasan",
    "qayerdasan", "sog", "omon", "ishlar", "tinclik", "tinchlik", "nimala", "bormisan",
}

UZBEK_SUFFIXES = (
    "misan", "misiz", "mizmi", "yapsan", "yapman", "yapti", "yapmiz",
    "asizmi", "ganman", "dingmi"
)


def _normalize_apostrophes(text: str) -> str:
    res = text
    for ch in "ʻ’‘`":
        res = res.replace(ch, "'")
    return res


def _has_uzbek_og_apostrophe(word: str) -> bool:
    """Check if word contains Uzbek o' or g' apostrophe, excluding English o'clock / 's."""
    norm = _normalize_apostrophes(word.lower())
    if norm == "o'clock":
        return False
    # If the word only ends with 's (like dog's, cat's, it's), not Uzbek
    if norm.endswith("'s"):
        prefix = norm[:-2]
        if "'" not in prefix:
            return False
    # Check for [og]' pattern
    return bool(re.search(r"[og]'", norm))


def detect_language(text: Optional[str]) -> Optional[str]:
    """Detect whether text is Uzbek ('uz'), Russian ('ru'), English ('en'), or None."""
    if not text:
        return None

    # Strip and check if any letters exist
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return None

    cyrillic_letters = [ch for ch in letters if '\u0400' <= ch <= '\u04FF']
    latin_letters = [ch for ch in letters if ('a' <= ch.lower() <= 'z')]

    # 1. Cyrillic dominant
    if len(cyrillic_letters) >= len(latin_letters) and cyrillic_letters:
        # Check special Uzbek Cyrillic letters
        for ch in text:
            if ch in UZBEK_CYRILLIC_SPECIAL:
                return "uz"
        # Tokenize Cyrillic words
        words = re.findall(r"[\u0400-\u04FF]+", text.lower())
        for w in words:
            if w in UZBEK_CYRILLIC_WORDS:
                return "uz"
            if any(w.endswith(suf) for suf in ("мисан", "мисиз", "мизми", "япсан", "япти", "дингми")):
                return "uz"
        return "ru"

    # 2. Latin dominant
    words = re.findall(r"[a-zA-Z'ʻ’‘`]+", text)
    for raw_w in words:
        # Check o' or g'
        if _has_uzbek_og_apostrophe(raw_w):
            return "uz"

        # Check stripped word
        clean_w = re.sub(f"[{APOSTROPHES}]", "", raw_w).lower()
        if clean_w in UZBEK_LATIN_WORDS:
            return "uz"

        # Check Uzbek suffixes
        if any(clean_w.endswith(suf) for suf in UZBEK_SUFFIXES):
            return "uz"

    return "en"
