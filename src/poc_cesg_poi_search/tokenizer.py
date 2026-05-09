"""Tokenizer for CESG POI search: Lindera + fallback char n-gram."""
import unicodedata
import re
from typing import Any

# Try to import lindera; fall back gracefully
_lindera_available = False
try:
    import lindera_python as lindera  # type: ignore
    _lindera_available = True
except ImportError:
    pass


def normalize_text(text: str) -> str:
    """Unicode NFKC normalization + lowercase."""
    if not text:
        return ""
    return unicodedata.normalize("NFKC", text).lower().strip()


def tokenize_lindera(text: str) -> list[str]:
    """Morphological tokenization via Lindera; falls back to whitespace split."""
    if not text:
        return []
    norm = normalize_text(text)
    if _lindera_available:
        try:
            tokens = lindera.tokenize(norm)
            return [t.text for t in tokens if t.text.strip()]
        except Exception:
            pass
    # Fallback: whitespace + symbol split
    return [t for t in re.split(r"[\s,.\-/()「」【】。、！？　]+", norm) if t]


def char_ngrams(text: str, n: int) -> list[str]:
    """Generate character n-grams from text (no spaces)."""
    cleaned = normalize_text(text)
    cleaned = re.sub(r"\s+", "", cleaned)
    if len(cleaned) < n:
        return [cleaned] if cleaned else []
    return [cleaned[i : i + n] for i in range(len(cleaned) - n + 1)]


def _dedup(tokens: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def build_exact_tokens(row: dict[str, Any]) -> str:
    """Normalized name + alternate names for exact match."""
    parts: list[str] = []
    for field in ("name_normalized", "name_primary", "names_all"):
        val = row.get(field) or ""
        if val:
            parts.append(normalize_text(str(val)))
    return " ".join(_dedup(parts))


def build_category_tokens(row: dict[str, Any]) -> str:
    """Category terms (primary + path) for category-level matching."""
    parts: list[str] = []
    for field in ("category_primary", "category_path"):
        val = row.get(field) or ""
        if val:
            for seg in re.split(r"[>/,|]", str(val)):
                seg = normalize_text(seg)
                if seg:
                    parts.append(seg)
    return " ".join(_dedup(parts))


def build_morph_tokens(row: dict[str, Any]) -> str:
    """Morphological tokens from name fields via Lindera."""
    parts: list[str] = []
    for field in ("name_primary", "name_normalized", "names_all"):
        val = row.get(field) or ""
        if val:
            parts.extend(tokenize_lindera(str(val)))
    return " ".join(_dedup(parts))


def build_name_bigram_tokens(row: dict[str, Any]) -> str:
    """Character bi-grams from name fields."""
    parts: list[str] = []
    for field in ("name_primary", "name_normalized", "names_all"):
        val = row.get(field) or ""
        if val:
            parts.extend(char_ngrams(str(val), 2))
    return " ".join(_dedup(parts))


def build_name_trigram_tokens(row: dict[str, Any]) -> str:
    """Character tri-grams from name fields."""
    parts: list[str] = []
    for field in ("name_primary", "name_normalized", "names_all"):
        val = row.get(field) or ""
        if val:
            parts.extend(char_ngrams(str(val), 3))
    return " ".join(_dedup(parts))


def expand_query(query: str) -> dict[str, str]:
    """Expand a user query into per-field query strings."""
    norm = normalize_text(query)
    morph = " ".join(tokenize_lindera(query))
    bigrams = " ".join(char_ngrams(query, 2))
    trigrams = " ".join(char_ngrams(query, 3))
    return {
        "exact_query": norm,
        "category_query": norm,
        "morph_query": morph if morph else norm,
        "bigram_query": bigrams if bigrams else norm,
        "trigram_query": trigrams if trigrams else norm,
    }
