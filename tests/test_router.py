import pytest
import json
from unittest.mock import patch, MagicMock
from app.core.router import HybridRouter

@pytest.fixture
def mock_config():
    return {
        "retrieval_mode": "trie",
        "provider": "ollama",
        "ollama_model": "llama3",
        "ollama_host": "http://localhost:11434"
    }

@pytest.fixture
def router(mock_config):
    # We need to mock QA_BANK_PATH because it's a global in router.py
    # But it's defined at the module level.
    with patch("app.core.router.QA_BANK_PATH") as mock_path:
        # We'll use the real qa_bank.yml path
        import pathlib
        mock_path.is_file.return_value = True
        mock_path.read_text.return_value = """
entries:
- id: Q_TEST
  question: Test Question
  triggers:
    - test trigger
  answer: Test Answer
"""
        # Wait, the router.py uses json.loads() then yaml.safe_load()
        # The current yaml I mocked is not valid JSON.
        # Actually, I should probably just use a valid JSON string for mock_path.read_text.
        
        # Let's try again with valid JSON string
        mock_path.read_text.return_value = json.dumps({
            "entries": [
                {
                    "id": "Q_TEST",
                    "question": "Test Question",
                    "triggers": ["test trigger"],
                    "answer": "Test Answer",
                    "gotcha_warning": None
                }
            ]
        })
        
        r = HybridRouter(mock_config)
        return r

@pytest.mark.trie
@pytest.mark.router
@pytest.mark.asyncio
async def test_router_trie_hit(router):
    result = await router.resolve_query("test trigger")
    assert result["source"] == "trie"
    assert result["script"] == "Test Answer"

@pytest.mark.trie
@pytest.mark.router
@pytest.mark.asyncio
async def test_router_trie_miss(router):
    result = await router.resolve_query("something completely different")
    assert result["source"] == "rag"
    assert result["script"] is None

@pytest.mark.trie
@pytest.mark.router
@pytest.mark.asyncio
async def test_router_rag_mode(mock_config):
    mock_config["retrieval_mode"] = "rag"
    with patch("app.core.router.QA_BANK_PATH") as mock_path:
        mock_path.is_file.return_value = True
        mock_path.read_text.return_value = json.dumps({
            "entries": [
                {
                    "id": "Q_TEST",
                    "question": "Test Question",
                    "triggers": ["test trigger"],
                    "answer": "Test Answer",
                    "gotcha_warning": None
                }
            ]
        })
        r = HybridRouter(mock_config)
        result = await r.resolve_query("test trigger")
        assert result["source"] == "rag"
        assert result["script"] is None
