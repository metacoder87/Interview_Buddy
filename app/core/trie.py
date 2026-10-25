"""
WordTokenTrie provides a deterministic lookup for interview questions.


It matches transcript fragments against a pre-compiled Q&A bank.
If an exact match or prefix match is found, it returns the scripted answer.
Otherwise, it falls back to RAG.
"""
from typing import Any, Dict, Optional, List
from .normalizer import normalize_text

class WordTokenTrie:
    def __init__(self):
        """
        Initializes an empty trie.
        Each node is a dict: {token: [next_node_dict, payload_dict_or_None]}
        """
        self.root: Dict[str, List[Any]] = {}

    def insert(self, trigger_phrase: str, payload: Dict[str, Any]) -> None:
        """
        Inserts a trigger phrase and its associated payload into the trie.
        
        Args:
            trigger_phrase: The phrase to match (e.g., "tell me about yourself").
            payload: The content to return (e.g., the scripted answer).
        """
        tokens = normalize_text(trigger_phrase)
        current_node = self.root
        for token in tokens:
            if token not in current_node:
                current_node[token] = [{}, None]
            current_node = current_node[token][0]
        current_node[None] = [None, payload] # Using None as a key for payload

    def search_prefix(self, transcript_text: str) -> Optional[Dict[str, Any]]:
        """
        Searches for a match in the trie based on a transcript fragment.

        Tries matching at every token position in the input so that trigger
        phrases embedded inside longer sentences (e.g. "Why don't you tell me
        about yourself?") are still found even when the transcript has a preamble.

        Args:
            transcript_text: The text fragment to search (e.g., from the interviewer).

        Returns:
            The payload of the last matched trigger, or None if no match found.
        """
        tokens = normalize_text(transcript_text)
        last_payload = None

        # Slide a starting window over every token position
        for start in range(len(tokens)):
            current_node = self.root
            for token in tokens[start:]:
                if token in current_node:
                    current_node = current_node[token][0]
                    if None in current_node:
                        last_payload = current_node[None][1]
                else:
                    break

        return last_payload