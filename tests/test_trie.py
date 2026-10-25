import pytest
from app.core.trie import WordTokenTrie

def test_trie_insert_and_search():
    trie = WordTokenTrie()
    trie.insert("tell me about yourself", {"id": "Q1", "answer": "Hello, I am an AI engineer."})
    
    # Exact match
    assert trie.search_prefix("tell me about yourself")["id"] == "Q1"
    
    # Partial match (prefix)
    # Note: The implementation I wrote returns the "last matched data" which means 
    # if it finds a node that has a payload, it updates last_payload.
    # If "tell me about" was a trigger, it would return that.
    
    # Let's test another one
    trie.insert("walk me through sidekick llm", {"id": "Q3", "answer": "Sidekick is cool."})
    assert trie.search_prefix("walk me through sidekick llm")["id"] == "Q3"

def test_trie_no_match():
    trie = WordTokenTrie()
    trie.insert("tell me about yourself", {"id": "Q1", "answer": "Hello, I am an AI engineer."})
    
    assert trie.search_prefix("what is your name?") is None

def test_trie_partial_prefix_match():
    trie = WordTokenTrie()
    # If "tell me" was a trigger, it should match "tell me about yourself" prefix
    trie.insert("tell me", {"id": "Q_partial", "answer": "Partial match"})
    
    # "tell me about yourself" should still match "tell me" if that's the last payload encountered?
    # Wait, in my implementation:
    # if token in current_node:
    #     current_node = current_node[token][0]
    #     if None in current_node:
    #         last_payload = current_node[None][1]
    
    # If input is "tell me about yourself"
    # tokens are ["tell", "me", "about", "yourself"]
    # 1. "tell" -> current_node = trie["tell"][0]
    # 2. "me" -> current_node = trie["me"][0]. if None in trie["me"][0]: last_payload = ...
    #    In this case, trie["me"][0] has None, so last_payload becomes "Partial match".
    # 3. "about" -> current_node = trie["about"][0]
    # 4. "yourself" -> current_node = trie["yourself"][0]
    
    # If "tell me about yourself" was also in the trie, it would overwrite it at the end.
    
    trie.insert("tell me about yourself", {"id": "Q1", "answer": "Full match"})
    assert trie.search_prefix("tell me about yourself")["id"] == "Q1"
    
    # If we search "tell me about", it should still return "Partial match" because "about" is not a payload node
    # Wait, "tell me" is a payload node. "about" is NOT. 
    # So it will find "tell" (no payload), then "me" (has payload "Partial match"), then "about" (no payload).
    # The last_payload seen was "Partial match".
    
    # Let's check this behavior.
    assert trie.search_prefix("tell me about")["id"] == "Q_partial"

def test_trie_empty_input():
    trie = WordTokenTrie()
    assert trie.search_prefix("") is None
    assert trie.search_prefix(None) is None
