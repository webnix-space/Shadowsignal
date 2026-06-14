import sys
import os

# Add project root to path so 'app' package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
app = Flask(__name__)

# Import all routes and logic from app package
from app.main import *

