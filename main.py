import os
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {
        "status": "OK", 
        "message": "Railway PORT fix",
        "port": os.getenv("PORT", "not_set"),
        "listening": "dynamic_port"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}