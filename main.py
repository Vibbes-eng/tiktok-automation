# main_phase1.py - FastAPI + Chrome + Tests basiques
import os
import logging
from fastapi import FastAPI, HTTPException

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="TikTok Automation - Phase 1", 
    description="FastAPI + Chrome + Tests",
    version="phase1-1.0"
)

# Variables d'environnement
RAILWAY_ENVIRONMENT = os.getenv("RAILWAY_ENVIRONMENT")

@app.get("/")
async def root():
    return {
        "status": "OK", 
        "message": "Phase 1: FastAPI + Chrome tests",
        "environment": "railway" if RAILWAY_ENVIRONMENT else "local",
        "port": os.getenv("PORT", "8000"),
        "phase": "1 - Chrome Integration"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "phase": "1", "chrome": "testing"}

@app.get("/chrome-status")
async def chrome_status():
    """Vérification installation Chrome"""
    chrome_info = {}
    
    # Test 1: Variables d'environnement
    chrome_info["env_vars"] = {
        "CHROME_BIN": os.getenv("CHROME_BIN"),
        "CHROMEDRIVER_PATH": os.getenv("CHROMEDRIVER_PATH"),
        "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT")
    }
    
    # Test 2: Fichiers Chrome
    chrome_paths = {
        "chrome_binary": "/usr/bin/google-chrome-stable",
        "chromedriver": "/usr/local/bin/chromedriver"
    }
    
    chrome_info["files"] = {}
    for name, path in chrome_paths.items():
        chrome_info["files"][name] = {
            "path": path,
            "exists": os.path.exists(path),
            "executable": os.access(path, os.X_OK) if os.path.exists(path) else False
        }
    
    # Test 3: Import Selenium
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        chrome_info["selenium"] = {
            "status": "available", 
            "webdriver": "imported",
            "options": "imported"
        }
    except ImportError as e:
        chrome_info["selenium"] = {
            "status": "error", 
            "message": str(e)
        }
    
    # Résumé
    chrome_ready = (
        chrome_info["files"]["chrome_binary"]["executable"] and
        chrome_info["files"]["chromedriver"]["executable"] and
        chrome_info["selenium"]["status"] == "available"
    )
    
    return {
        "status": "chrome_status",
        "chrome_ready": chrome_ready,
        "chrome_info": chrome_info
    }

@app.get("/chrome-test")
async def chrome_test():
    """Test complet Chrome + Selenium"""
    try:
        logger.info("🧪 Démarrage test Chrome...")
        
        # Import Selenium
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        
        # Configuration Chrome pour Railway
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # Chemins
        chrome_binary = "/usr/bin/google-chrome-stable"
        driver_path = "/usr/local/bin/chromedriver"
        
        # Vérifications
        if not os.path.exists(chrome_binary):
            raise Exception(f"Chrome binary not found: {chrome_binary}")
        
        if not os.path.exists(driver_path):
            raise Exception(f"ChromeDriver not found: {driver_path}")
        
        options.binary_location = chrome_binary
        service = Service(driver_path)
        
        logger.info("🔧 Configuration Chrome terminée")
        
        # Test création driver
        driver = webdriver.Chrome(service=service, options=options)
        logger.info("✅ Driver Chrome créé")
        
        # Test navigation basique
        test_url = "data:text/html,<html><head><title>Chrome Test</title></head><body><h1>Chrome fonctionne sur Railway!</h1><p>Test réussi</p></body></html>"
        driver.get(test_url)
        logger.info("🌐 Navigation test réussie")
        
        # Récupérer informations
        title = driver.title
        h1_text = driver.find_element("tag name", "h1").text
        p_text = driver.find_element("tag name", "p").text
        
        # Test JavaScript
        js_result = driver.execute_script("return 'JavaScript fonctionne!';")
        logger.info("⚡ Test JavaScript réussi")
        
        # Test page plus complexe
        driver.get("data:text/html,<html><body><script>document.body.innerHTML='<h2>JS Test: ' + (2+3) + '</h2>';</script></body></html>")
        js_content = driver.find_element("tag name", "h2").text
        
        # Fermer driver
        driver.quit()
        logger.info("🔒 Driver fermé")
        
        return {
            "status": "success",
            "message": "Chrome + Selenium test RÉUSSI sur Railway!",
            "results": {
                "title": title,
                "h1_text": h1_text,
                "p_text": p_text,
                "javascript": js_result,
                "js_content": js_content,
                "chrome_binary": chrome_binary,
                "driver_path": driver_path
            },
            "ready_for_tiktok": True
        }
        
    except Exception as e:
        logger.error(f"❌ Chrome test failed: {e}")
        return {
            "status": "error",
            "message": f"Chrome test échoué: {str(e)}",
            "error_type": type(e).__name__,
            "ready_for_tiktok": False
        }

@app.get("/tiktok-test")
async def tiktok_test():
    """Test navigation vers TikTok (préparation Phase 2)"""
    try:
        logger.info("🎵 Test navigation TikTok...")
        
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        
        # Configuration Chrome pour TikTok
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        chrome_binary = "/usr/bin/google-chrome-stable"
        driver_path = "/usr/local/bin/chromedriver"
        
        options.binary_location = chrome_binary
        service = Service(driver_path)
        
        driver = webdriver.Chrome(service=service, options=options)
        
        # Test navigation TikTok
        driver.get("https://www.tiktok.com")
        
        title = driver.title
        url = driver.current_url
        
        # Test si on peut voir des éléments TikTok
        try:
            # Attendre un peu pour le chargement
            import time
            time.sleep(3)
            
            # Chercher des éléments TikTok typiques
            page_source_preview = driver.page_source[:500]
            has_tiktok_elements = "tiktok" in page_source_preview.lower()
            
        except Exception as e:
            page_source_preview = f"Error getting page source: {e}"
            has_tiktok_elements = False
        
        driver.quit()
        
        return {
            "status": "success",
            "message": "Navigation TikTok réussie",
            "results": {
                "title": title,
                "url": url,
                "has_tiktok_elements": has_tiktok_elements,
                "page_preview": page_source_preview
            },
            "ready_for_phase2": True
        }
        
    except Exception as e:
        logger.error(f"❌ TikTok test failed: {e}")
        return {
            "status": "error",
            "message": f"TikTok test échoué: {str(e)}",
            "error_type": type(e).__name__,
            "ready_for_phase2": False
        }

@app.get("/debug")
async def debug():
    """Debug général système"""
    import subprocess
    
    debug_info = {
        "environment": {
            "PORT": os.getenv("PORT"),
            "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT"),
            "CHROME_BIN": os.getenv("CHROME_BIN"),
            "CHROMEDRIVER_PATH": os.getenv("CHROMEDRIVER_PATH")
        },
        "chrome_files": {},
        "processes": {}
    }
    
    # Test fichiers Chrome
    chrome_files = [
        "/usr/bin/google-chrome-stable",
        "/usr/local/bin/chromedriver"
    ]
    
    for file_path in chrome_files:
        debug_info["chrome_files"][file_path] = {
            "exists": os.path.exists(file_path),
            "executable": os.access(file_path, os.X_OK) if os.path.exists(file_path) else False
        }
    
    # Test processus Chrome
    try:
        ps_result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=5)
        chrome_processes = [line for line in ps_result.stdout.split('\n') if 'chrome' in line.lower()]
        debug_info["processes"]["chrome_count"] = len(chrome_processes)
        debug_info["processes"]["chrome_processes"] = chrome_processes[:3]  # Limiter
    except Exception as e:
        debug_info["processes"]["error"] = str(e)
    
    return debug_info

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🚀 Starting Phase 1 - FastAPI + Chrome on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)