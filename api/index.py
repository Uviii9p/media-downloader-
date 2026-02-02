import sys
import os

# Add the project root to sys.path to allow imports from backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.main import app

# Vercel needs the variable 'app'
