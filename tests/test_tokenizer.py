"""Tests for tokenizer module."""
import pytest
from poc_cesg_poi_search.tokenizer import (
    normalize_text,
    char_ngrams,
    build_name_bigram_tokens,
    build_name_trigram_tokens,
    expand_query,
)


def test_normalize_nfkc():
    assert normalize_text("Ａｂｃ") == "abc"
    assert normalize_text("カフェ") == "カフェ"
    assert normalize_text("  Hello  ") == "hello"


def test_normalize_empty():
    assert normalize_text("") == ""
    assert normalize_text(None) == ""  # type: ignore[arg-type]


def test_bigram_basic():
    result = char_ngrams("カフェ", 2)
    assert "カフ" in result
    assert "フェ" in result


def test_bigram_short():
    assert char_ngrams("ab", 2) == ["ab"]
    assert char_ngrams("a", 2) == ["a"]
    assert char_ngrams("", 2) == []


def test_trigram_basic():
    result = char_ngrams("東京タワー", 3)
    assert "東京タ" in result
    assert "京タワ" in result
    assert "タワー" in result


def test_trigram_short():
    assert char_ngrams("ab", 3) == ["ab"]


def test_build_bigram_tokens():
    row = {"name_primary": "スターバックス", "name_normalized": "スターバックス", "names_all": ""}
    tokens = build_name_bigram_tokens(row)
    assert "スタ" in tokens
    assert "ター" in tokens


def test_build_trigram_tokens():
    row = {"name_primary": "スターバックス", "name_normalized": "スターバックス", "names_all": ""}
    tokens = build_name_trigram_tokens(row)
    assert "スター" in tokens


def test_expand_query_keys():
    result = expand_query("カフェ")
    assert "exact_query" in result
    assert "category_query" in result
    assert "morph_query" in result
    assert "bigram_query" in result
    assert "trigram_query" in result


def test_expand_query_bigrams():
    result = expand_query("カフェ")
    assert "カフ" in result["bigram_query"]


def test_no_unigram_field():
    """Confirm there is no unigram token builder exported."""
    import poc_cesg_poi_search.tokenizer as tok
    assert not hasattr(tok, "build_name_unigram_tokens")
