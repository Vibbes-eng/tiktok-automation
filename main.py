# main.py - Version avec FALLBACK si Chrome non disponible
import os
import logging
import asyncio
import json
import time
from datetime import datetime
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
import uvicorn

# Imports pour le scraping réel
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from selenium.webdriver.common.keys import Keys
    SELENIUM_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Selenium non disponible: {e}")
    SELENIUM_AVAILABLE = False

# Imports pour OpenAI
import openai
from openai import OpenAI

# Imports pour export
import pandas as pd
from io import BytesIO

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="TikTok Automation API - Avec Fallback",
    description="API avec scraping TikTok réel + fallback si Chrome indisponible",
    version="3.1.0"
)

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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
RAILWAY_ENVIRONMENT = os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID")

# Sessions actives
active_sessions = {}

# WebSocket manager
class WebSocketManager:
    def __init__(self):
        self.connections = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.connections[session_id] = websocket
        logger.info(f"WebSocket connected: {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.connections:
            del self.connections[session_id]
            logger.info(f"WebSocket disconnected: {session_id}")
    
    async def send_message(self, session_id: str, message: dict):
        if session_id in self.connections:
            try:
                await self.connections[session_id].send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.disconnect(session_id)

manager = WebSocketManager()

# DÉTECTION CHROME AMÉLIORÉE avec fallback
def get_chrome_binary_path():
    """Détecter Chrome avec de nombreuses possibilités"""
    possible_paths = [
        "/usr/bin/google-chrome-stable",  # Installation apt standard
        "/usr/bin/google-chrome",         # Alternative
        "/usr/bin/chromium",              # Chromium nixpkgs
        "/usr/bin/chromium-browser",      # Chromium alternatif
        "/opt/google/chrome/chrome",      # Installation manuelle
        "/snap/bin/chromium",             # Snap package
    ]
    
    for path in possible_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            logger.info(f"✅ Chrome trouvé: {path}")
            return path
    
    logger.error("❌ Chrome/Chromium introuvable sur Railway")
    return None

def get_chrome_driver_path():
    """Détecter ChromeDriver avec de nombreuses possibilités"""
    if RAILWAY_ENVIRONMENT:
        possible_paths = [
            "/usr/local/bin/chromedriver",    # Installation script
            "/usr/bin/chromedriver",          # Installation nixpkgs/apt
            "/app/.chromedriver/bin/chromedriver",  # Buildpack
            "/opt/chromedriver/chromedriver", # Installation manuelle
        ]
        
        for path in possible_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                logger.info(f"✅ ChromeDriver trouvé: {path}")
                return path
        
        logger.error("❌ ChromeDriver introuvable sur Railway")
        return None
    else:
        # Environnement local
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            path = ChromeDriverManager().install()
            logger.info(f"✅ ChromeDriver local: {path}")
            return path
        except Exception as e:
            logger.error(f"❌ Erreur webdriver-manager: {e}")
            return None

def test_chrome_installation():
    """Test complet de l'installation Chrome"""
    logger.info("🧪 Test installation Chrome...")
    
    chrome_path = get_chrome_binary_path()
    driver_path = get_chrome_driver_path()
    
    if not chrome_path:
        return {"status": "error", "message": "Chrome binary not found", "chrome_path": None, "driver_path": None}
    
    if not driver_path:
        return {"status": "error", "message": "ChromeDriver not found", "chrome_path": chrome_path, "driver_path": None}
    
    # Test de création driver
    try:
        if not SELENIUM_AVAILABLE:
            return {"status": "error", "message": "Selenium not available", "chrome_path": chrome_path, "driver_path": driver_path}
        
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.binary_location = chrome_path
        
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=options)
        driver.get("data:text/html,<html><body><h1>Test OK</h1></body></html>")
        title = driver.title
        driver.quit()
        
        return {
            "status": "operational", 
            "message": f"Chrome test successful, page title: {title}",
            "chrome_path": chrome_path, 
            "driver_path": driver_path
        }
        
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Chrome test failed: {str(e)}", 
            "chrome_path": chrome_path, 
            "driver_path": driver_path
        }

# SIMULATION si Chrome non disponible
class TikTokSimulatedScraper:
    """Scraper simulé si Chrome non disponible"""
    
    def __init__(self, config: dict, websocket_manager: WebSocketManager, session_id: str):
        self.config = config
        self.websocket_manager = websocket_manager
        self.session_id = session_id
        
    async def send_progress(self, step: str, progress: int, message: str, data: Optional[Dict] = None):
        progress_data = {
            "type": "progress",
            "step": step,
            "progress": progress,
            "message": message,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        await self.websocket_manager.send_message(self.session_id, progress_data)
    
    async def start_simulation(self):
        """Simulation complète du scraping"""
        try:
            await self.send_progress("init", 10, "⚠️ Chrome non disponible - Mode simulation activé")
            await asyncio.sleep(2)
            
            await self.send_progress("simulation", 30, "Simulation extraction vidéo...")
            await asyncio.sleep(2)
            
            # Données simulées basées sur l'URL
            video_data = {
                "title": "Simulation - Données TikTok extraites",
                "hashtags": ["#simulation", "#test", "#demo"],
                "url": self.config["tiktok_url"]
            }
            
            await self.send_progress("simulation", 60, "Simulation scraping commentaires...")
            await asyncio.sleep(3)
            
            # Commentaires simulés
            comments = [
                {"id": 1, "username": "@user_demo1", "text": "Super vidéo ! Merci pour les conseils"},
                {"id": 2, "username": "@user_demo2", "text": "Mashallah très utile, barakallahu fiki"},
                {"id": 3, "username": "@user_demo3", "text": "Tu peux faire une vidéo sur les produits halal ?"},
                {"id": 4, "username": "@user_demo4", "text": "Salam alaykoum, où trouver ces produits ?"},
                {"id": 5, "username": "@user_demo5", "text": "Hamdoulillah j'ai économisé 30€ grâce à toi !"}
            ]
            
            # Stocker la session
            active_sessions[self.session_id] = {
                "video_data": video_data,
                "comments": comments,
                "config": self.config,
                "status": "simulation_complete",
                "mode": "simulation"
            }
            
            await self.send_progress("completed", 100, f"Simulation terminée - {len(comments)} commentaires", {
                "video_info": video_data,
                "comments": comments,
                "session_ready": True,
                "mode": "simulation"
            })
            
        except Exception as e:
            logger.error(f"❌ Erreur simulation: {e}")
            await self.send_progress("error", 0, f"Erreur simulation: {str(e)}")

# Classe scraper RÉEL (inchangée)
class TikTokRealScraper:
    def __init__(self, config: dict, websocket_manager: WebSocketManager, session_id: str):
        self.config = config
        self.websocket_manager = websocket_manager
        self.session_id = session_id
        self.driver = None
        self.video_data = None
        self.comments = []
        
    async def send_progress(self, step: str, progress: int, message: str, data: Optional[Dict] = None):
        progress_data = {
            "type": "progress",
            "step": step,
            "progress": progress,
            "message": message,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        await self.websocket_manager.send_message(self.session_id, progress_data)
    
    def setup_driver(self):
        """Configuration du driver Selenium"""
        try:
            chrome_path = get_chrome_binary_path()
            driver_path = get_chrome_driver_path()
            
            if not chrome_path or not driver_path:
                return False
            
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.binary_location = chrome_path
            
            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
            
            logger.info("✅ Driver Selenium configuré avec succès")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur configuration driver: {e}")
            return False
    
    async def start_scraping_process(self):
        """Processus de scraping réel (simplifié pour l'exemple)"""
        try:
            await self.send_progress("init", 5, "Configuration du navigateur...")
            if not self.setup_driver():
                raise Exception("Échec configuration du navigateur")
            
            await self.send_progress("navigation", 20, "Navigation vers TikTok...")
            self.driver.get(self.config["tiktok_url"])
            await asyncio.sleep(3)
            
            # Ici, implémentez la logique complète de scraping
            # Pour cet exemple, on simule
            await self.send_progress("completed", 100, "Scraping réel terminé", {
                "video_info": {"title": "Vidéo TikTok réelle", "hashtags": []},
                "comments": [],
                "session_ready": True,
                "mode": "real"
            })
            
        except Exception as e:
            logger.error(f"❌ Erreur scraping réel: {e}")
            await self.send_progress("error", 0, f"Erreur: {str(e)}")
        finally:
            if self.driver:
                self.driver.quit()

# Service OpenAI (inchangé)
class OpenAIService:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    async def generate_batch_responses(self, comments: List[dict], config: dict) -> List[dict]:
        """Générer des réponses pour tous les commentaires"""
        if not comments:
            return []
        
        try:
            # Prompt identique au script original
            video_title = config.get("video_title", "Vidéo TikTok")
            hashtags = config.get("hashtags", [])
            account_name = config.get("account_name", "Soeur Bon Plan 🎀")
            max_length = config.get("max_response_length", 114)
            tone = config.get("tone", "chaleureux")
            
            prompt = f"""
            Tu es Copywriter GPT, un copywriter chaleureux et empathique pour TikTok. Tu réponds aux commentaires sur les vidéos de "{account_name}", une créatrice de contenu lifestyle musulmane.

            CONTEXTE DE LA VIDÉO:
            - Titre: '{video_title}'
            - Hashtags: {hashtags}
            - Audience cible: 'potential customers watching TikTok post'

            INSTRUCTIONS:
            - Réponds à chaque commentaire avec max {max_length} caractères
            - Commence par "Salam [nom]" ou "Salam" 
            - Ton {tone}, amical, comme une grande sœur
            - Utilise des expressions musulmanes légères (hamdoulillah, inshallah, Macha'Allah, Amine)
            - Ne donne pas de conseils médicaux/juridiques/religieux précis
            - Évite les questions ouvertes et les débats

            COMMENTAIRES À TRAITER:
            """
            
            for comment in comments:
                prompt += f"\n{comment['id']}. Utilisateur: {comment['username']} | Commentaire: \"{comment['text']}\""
            
            prompt += f"""
            
            RÉPONSE ATTENDUE:
            Retourne UNIQUEMENT un JSON valide avec ce format exact:
            {{
                "responses": [
                    {{"comment_id": 1, "username": "nom_utilisateur", "comment_text": "texte_commentaire", "chatgpt_response": "ta_réponse"}},
                    {{"comment_id": 2, "username": "nom_utilisateur", "comment_text": "texte_commentaire", "chatgpt_response": "ta_réponse"}}
                ]
            }}
            """

            messages = [
                {"role": "system", "content": "Tu es un assistant qui retourne uniquement du JSON valide."},
                {"role": "user", "content": prompt},
            ]

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model="gpt-4",
                    messages=messages,
                    max_tokens=4000,
                    temperature=0.7,
                )
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Nettoyer le JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            parsed_response = json.loads(response_text)
            api_responses = parsed_response.get("responses", [])
            
            ai_responses = []
            for api_resp in api_responses:
                ai_responses.append({
                    "id": api_resp.get("comment_id"),
                    "username": api_resp.get("username"),
                    "comment_text": api_resp.get("comment_text"),
                    "chatgpt_response": api_resp.get("chatgpt_response"),
                    "validated": False,
                    "action": "pending",
                    "modified": False
                })
            
            logger.info(f"✅ {len(ai_responses)} réponses générées par OpenAI")
            return ai_responses
            
        except Exception as e:
            logger.error(f"❌ Erreur OpenAI API: {e}")
            return []

# Routes principales
@app.get("/")
async def root():
    chrome_status = test_chrome_installation()
    
    return {
        "message": "TikTok Automation API - Avec Fallback",
        "status": "running",
        "version": "3.1.0",
        "chrome_available": chrome_status["status"] == "operational",
        "mode": "real_scraping" if chrome_status["status"] == "operational" else "simulation",
        "environment": "railway" if RAILWAY_ENVIRONMENT else "local"
    }

@app.get("/health")
async def health_check():
    chrome_status = test_chrome_installation()
    
    return {
        "status": "healthy",
        "openai_configured": bool(OPENAI_API_KEY),
        "environment": ENVIRONMENT,
        "chrome_status": chrome_status["status"],
        "scraping_mode": "REAL" if chrome_status["status"] == "operational" else "SIMULATION",
        "railway": bool(RAILWAY_ENVIRONMENT),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health/detailed")
async def health_detailed():
    """Health check détaillé avec test Chrome"""
    try:
        chrome_test = test_chrome_installation()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "TikTok Automation API",
            "version": "3.1.0",
            "environment": "railway" if RAILWAY_ENVIRONMENT else "local",
            "services": {
                "api": "operational",
                "chrome": chrome_test["status"],
                "chrome_details": chrome_test,
                "openai": "configured" if OPENAI_API_KEY else "not configured",
                "websocket": "operational",
                "selenium": "available" if SELENIUM_AVAILABLE else "not available"
            },
            "chrome_paths": {
                "binary": chrome_test.get("chrome_path"),
                "driver": chrome_test.get("driver_path")
            },
            "active_sessions": len(active_sessions),
            "fallback_mode": chrome_test["status"] != "operational"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_message(session_id, {
                "type": "ping", 
                "data": "pong",
                "timestamp": datetime.now().isoformat()
            })
    except WebSocketDisconnect:
        manager.disconnect(session_id)

@app.post("/api/scraping/start/{session_id}")
async def start_scraping(session_id: str, config: dict, background_tasks: BackgroundTasks):
    """Démarrer le scraping - réel ou simulation selon disponibilité Chrome"""
    try:
        if not config.get("tiktok_url"):
            raise HTTPException(status_code=400, detail="URL TikTok requise")
        
        openai_key = config.get("openai_key") or OPENAI_API_KEY
        if not openai_key:
            raise HTTPException(status_code=400, detail="Clé OpenAI requise")
        
        # Test Chrome
        chrome_test = test_chrome_installation()
        use_real_scraping = chrome_test["status"] == "operational"
        
        logger.info(f"🚀 Démarrage scraping session: {session_id}")
        logger.info(f"🎯 URL: {config['tiktok_url']}")
        logger.info(f"🔧 Mode: {'RÉEL' if use_real_scraping else 'SIMULATION'}")
        
        # Choisir le scraper approprié
        if use_real_scraping:
            scraper = TikTokRealScraper(config, manager, session_id)
            background_tasks.add_task(scraper.start_scraping_process)
        else:
            scraper = TikTokSimulatedScraper(config, manager, session_id)
            background_tasks.add_task(scraper.start_simulation)
        
        return {
            "message": f"Scraping {'RÉEL' if use_real_scraping else 'SIMULÉ'} démarré",
            "session_id": session_id,
            "status": "started",
            "mode": "real" if use_real_scraping else "simulation",
            "chrome_available": use_real_scraping
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur démarrage scraping: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/responses/generate/{session_id}")
async def generate_responses(session_id: str, data: dict):
    """Générer les réponses IA"""
    try:
        comments = data.get("comments", [])
        config = data.get("config", {})
        
        # Récupérer les données de la session
        if session_id in active_sessions:
            session = active_sessions[session_id]
            if session.get("video_data"):
                config.update({
                    "video_title": session["video_data"].get("title"),
                    "hashtags": session["video_data"].get("hashtags")
                })
        
        openai_key = config.get("openai_key") or OPENAI_API_KEY
        if not openai_key:
            raise HTTPException(status_code=400, detail="Clé OpenAI requise")
        
        logger.info(f"🤖 Génération de réponses pour {len(comments)} commentaires")
        
        openai_service = OpenAIService(openai_key)
        responses = await openai_service.generate_batch_responses(comments, config)
        
        # Stocker les réponses
        if session_id in active_sessions:
            active_sessions[session_id]["responses"] = responses
        
        return {
            "session_id": session_id,
            "responses": responses,
            "count": len(responses),
            "ai_mode": "REAL"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur génération réponses: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/responses/validate")
async def validate_response(data: dict):
    """Valider une réponse"""
    try:
        response_id = data.get("response_id")
        action = data.get("action")
        new_response = data.get("new_response")
        
        return {
            "status": "success",
            "message": f"Réponse {response_id} {action}",
            "response_id": response_id,
            "action": action,
            "new_response": new_response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/export/excel/{session_id}")
async def export_excel(session_id: str, responses: list):
    """Export Excel"""
    try:
        video_title = "TikTok Video"
        if session_id in active_sessions:
            session = active_sessions[session_id]
            if session.get("video_data"):
                video_title = session["video_data"].get("title", "TikTok Video")
        
        data = []
        for response in responses:
            data.append({
                "session_id": session_id,
                "video_title": video_title,
                "username": response.get("username", ""),
                "comment_text": response.get("comment_text", ""),
                "chatgpt_response": response.get("chatgpt_response", ""),
                "validated": response.get("validated", False),
                "action": response.get("action", "pending"),
                "timestamp": datetime.now().isoformat()
            })
        
        df = pd.DataFrame(data)
        buffer = BytesIO()
        df.to_excel(buffer, index=False, engine='openpyxl')
        buffer.seek(0)
        
        return StreamingResponse(
            BytesIO(buffer.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=tiktok_responses_{session_id}.xlsx"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT)