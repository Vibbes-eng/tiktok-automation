import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="TikTok Automation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

PORT = int(os.getenv("PORT", 8000))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

@app.get("/")
def root():
    return {"message": "TikTok Automation API", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy", "openai_configured": bool(OPENAI_API_KEY)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT)