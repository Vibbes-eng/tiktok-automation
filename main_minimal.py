# main_debug.py - Version simplifiée pour identifier le problème
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="TikTok Automation Debug", version="debug-1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variables d'environnement
PORT = int(os.getenv("PORT", 8000))
RAILWAY_ENVIRONMENT = os.getenv("RAILWAY_ENVIRONMENT")

@app.get("/")
async def root():
    return {
        "message": "TikTok Automation - Mode Debug",
        "status": "running",
        "environment": "railway" if RAILWAY_ENVIRONMENT else "local",
        "port": PORT
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "debug"}

@app.get("/chrome-test")
async def test_chrome():
    chrome_status = {}
    
    # Test 1: Variables d'environnement
    chrome_status["env_vars"] = {
        "CHROME_BIN": os.getenv("CHROME_BIN"),
        "CHROMEDRIVER_PATH": os.getenv("CHROMEDRIVER_PATH"),
        "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT")
    }
    
    # Test 2: Fichiers Chrome
    chrome_paths = [
        "/usr/bin/google-chrome-stable",
        "/usr/local/bin/chromedriver"
    ]
    
    chrome_status["files"] = {}
    for path in chrome_paths:
        chrome_status["files"][path] = {
            "exists": os.path.exists(path),
            "executable": os.access(path, os.X_OK) if os.path.exists(path) else False
        }
    
    # Test 3: Import Selenium
    try:
        from selenium import webdriver
        chrome_status["selenium"] = "available"
    except ImportError as e:
        chrome_status["selenium"] = f"error: {e}"
    
    return {
        "status": "debug",
        "chrome_status": chrome_status
    }

if __name__ == "__main__":
    import uvicorn
    logger.info(f"🚀 Démarrage du serveur de debug sur port {PORT}")
    uvicorn.run("main_debug:app", host="0.0.0.0", port=PORT)