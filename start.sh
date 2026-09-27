#!/bin/bash
# Render / Railway / Fly startup script — ensures schema exists (and seeds an
# empty DB), then starts gunicorn. (Vercel uses api/index.py instead.)
set -e
export FLASK_ENV=production

echo "==> Running DB setup..."
python -c "
from app import app, bootstrap_database
bootstrap_database(app, seed=True)
print('==> DB ready.')
"

echo "==> Starting gunicorn..."
gunicorn "app:app" --workers 2 --bind 0.0.0.0:$PORT --timeout 120
