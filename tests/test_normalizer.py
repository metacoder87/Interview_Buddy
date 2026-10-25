import pytest
from app.core.normalizer import normalize_text

def test_normalize_text_basic():
    assert normalize_text("Hello World!") == ["hello", "world"]
    assert normalize_text("HELLO WORLD") == ["hello", "world"]

def test_normalize_text_punctuation():
    assert normalize_text("Hello, World; and... how are you?") == ["hello", "world", "how", "you"]

def test_normalize_text_stop_words():
    assert normalize_text("The quick brown fox is on the mat") == ["quick", "brown", "fox", "mat"]

def test_normalize_text_empty():
    assert normalize_text("") == []
    assert normalize_text(None) == []

def test_normalize_text_numbers():
    assert normalize_text("The price is 100 dollars.") == ["price", "100", "dollars"]
