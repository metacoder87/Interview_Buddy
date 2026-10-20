# conftest.py
"""Test configuration to ensure the `app` package is importable during pytest runs.
Adds the repository root to `sys.path` so that `import app.core` works.
"""
import sys
import os

# Append the directory containing this file (project root) to sys.path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
