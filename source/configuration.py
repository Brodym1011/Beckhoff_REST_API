import os

BACKEND_MODE = os.getenv("BACKEND_MODE", "mock").strip().lower()
