"""
Normalizes input text for trie matching and search.

Removes punctuation, lowercases, and filters out common stop-words
to ensure consistent tokenization of interview transcript fragments.
"""
import re
import string

def normalize_text(text: str) -> list[str]:
    """
    Normalizes input text by lowercasing, removing punctuation, 
    and splitting into tokens.
    
    Args:
        text: The raw transcript or trigger phrase.
        
    Returns:
        A list of cleaned tokens.
    """
    if not text:
        return []
    
    # Lowercase
    text = text.lower()
    
    # Remove punctuation
    text = text.translate(str.maketrans('', '', string.punctuation))
    
    # Split into tokens and filter out empty strings
    tokens = text.split()
    
    # Simple stop-word removal (can be expanded)
    # These common words are often noise in a trie match
    stop_words = {"the", "a", "an", "is", "are", "to", "of", "in", "and", "or", "for", "with", "on", "at", "by", "from"}
    tokens = [token for token in tokens if token not in stop_words]
    
    return tokens
