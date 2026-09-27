"""Vercel serverless entrypoint.

Vercel's @vercel/python runtime imports this module and looks for a WSGI
callable named ``app``. We add the project root to sys.path so the existing
``app.py`` (one directory up) imports cleanly, then expose its ``app``.
"""
import os
import sys

# Make the marketplace package root importable (../ from this file).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# app.py selects the production config automatically when VERCEL is set.
from app import app  # noqa: E402  (import after sys.path setup)

# Vercel looks for `app` (WSGI application).
__all__ = ['app']
