"""Run from any directory with the project's Python environment."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.services.seed import seed_demo

if __name__ == '__main__':
    with create_app().app_context():
        print(f'Created {seed_demo()} demo transactions.')
