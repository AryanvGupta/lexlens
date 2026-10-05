from fastapi import FastAPI

app = FastAPI(title="lexlens rag-api")


@app.get("/health")
def health():
    return {"status": "ok"}
