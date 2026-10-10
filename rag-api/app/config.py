import os

DATABASE_URL = os.environ.get("DATABASE_URL", "")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
EMBED_DIM = 384
RERANK_MODEL = os.environ.get("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
GEN_MODEL = os.environ.get("GEN_MODEL", "claude-sonnet-5-5")
GEN_EFFORT = os.environ.get("GEN_EFFORT", "low")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "claude-haiku-4-5")
