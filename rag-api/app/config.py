import os

DATABASE_URL = os.environ.get("DATABASE_URL", "")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
EMBED_DIM = 384
