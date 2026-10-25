from app.core.normalizer import normalize_text
from app.core.trie import WordTokenTrie

trie = WordTokenTrie()
trie.insert('tell me about yourself', {'answer': 'TEST ANSWER'})
trie.insert('walk me through sidekick llm', {'answer': 'SIDEKICK ANSWER'})

# Test 1: exact trigger
r1 = trie.search_prefix('Tell me about yourself')
print('Test 1 (exact):', 'PASS' if r1 and r1.get('answer') == 'TEST ANSWER' else 'FAIL', r1)

# Test 2: trigger phrase embedded in longer sentence
r2 = trie.search_prefix('Why dont you tell me about yourself')
print('Test 2 (embedded):', 'PASS' if r2 and r2.get('answer') == 'TEST ANSWER' else 'FAIL', r2)

# Test 3: no match
r3 = trie.search_prefix('What is your greatest strength')
print('Test 3 (no match):', 'PASS' if r3 is None else 'FAIL', r3)

# Test 4: tokens after normalization
tokens = normalize_text('tell me about yourself')
print('Tokens for trigger:', tokens)
tokens2 = normalize_text('Why dont you tell me about yourself?')
print('Tokens for question:', tokens2)
