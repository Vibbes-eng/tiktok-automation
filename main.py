# main.py - Version Railway avec ChromeDriver automatique
import os
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import uvicorn

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="TikTok Automation API",
    description="API pour automatisation des reponses TikTok",
    version="1.0.0"
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

# WebSocket manager simple
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

# Routes principales
@app.get("/")
async def root():
    return {
        "message": "TikTok Automation API",
        "status": "running",
        "version": "1.0.0",
        "environment": ENVIRONMENT
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "openai_configured": bool(OPENAI_API_KEY),
        "environment": ENVIRONMENT,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health/detailed")
async def detailed_health():
    checks = {
        "api": True,
        "openai_key": bool(OPENAI_API_KEY),
        "environment": ENVIRONMENT,
        "webdriver": await check_webdriver()
    }
    
    return {
        "status": "healthy" if all(checks.values()) else "degraded",
        "checks": checks,
        "timestamp": datetime.now().isoformat()
    }

async def check_webdriver():
    """Vérifier si WebDriver peut être configuré"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Test rapide de création du driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.quit()
        
        return True
    except Exception as e:
        logger.error(f"WebDriver check failed: {e}")
        return False

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
async def start_scraping(session_id: str, config: dict):
    try:
        # Validation de base
        if not config.get("tiktok_url"):
            raise HTTPException(status_code=400, detail="URL TikTok requise")
        
        if not config.get("openai_key") and not OPENAI_API_KEY:
            raise HTTPException(status_code=400, detail="Clé OpenAI requise")
        
        logger.info(f"Starting scraping for session: {session_id}")
        
        # Simulation progressive pour démonstration
        async def simulate_scraping():
            stages = [
                (10, "Initialisation du navigateur..."),
                (25, "Connexion à TikTok..."),
                (40, "Navigation vers la vidéo..."),
                (55, "Extraction des métadonnées..."),
                (70, "Chargement des commentaires..."),
                (85, "Analyse des commentaires..."),
                (100, "Scraping terminé!")
            ]
            
            for progress, message in stages:
                await manager.send_message(session_id, {
                    "type": "progress",
                    "step": "scraping",
                    "progress": progress,
                    "message": message,
                    "timestamp": datetime.now().isoformat()
                })
                await asyncio.sleep(1)
            
            # Simulation de résultats
            await manager.send_message(session_id, {
                "type": "progress",
                "step": "completed",
                "progress": 100,
                "message": "Scraping terminé avec succès",
                "data": {
                    "video_info": {
                        "title": "Vidéo TikTok de démonstration",
                        "hashtags": ["#demo", "#test", "#automation"],
                        "views": "1.2K",
                        "likes": "89",
                        "comments_count": "15"
                    },
                    "comments": [
                        {"id": 1, "username": "@demo_user1", "text": "Super vidéo, merci pour les conseils !"},
                        {"id": 2, "username": "@demo_user2", "text": "Très utile, j'ai économisé grâce à toi"},
                        {"id": 3, "username": "@demo_user3", "text": "Tu peux faire une vidéo sur les promos ?"},
                        {"id": 4, "username": "@demo_user4", "text": "Mashallah, continue comme ça !"},
                        {"id": 5, "username": "@demo_user5", "text": "Barakallahu fiki ma sœur"}
                    ]
                },
                "timestamp": datetime.now().isoformat()
            })
        
        # Lancer en arrière-plan
        asyncio.create_task(simulate_scraping())
        
        return {
            "message": "Scraping démarré avec succès",
            "session_id": session_id,
            "status": "started"
        }
        
    except Exception as e:
        logger.error(f"Scraping error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/responses/generate/{session_id}")
async def generate_responses(session_id: str, data: dict):
    try:
        comments = data.get("comments", [])
        config = data.get("config", {})
        
        logger.info(f"Generating responses for session: {session_id}, comments: {len(comments)}")
        
        # Simulation de génération IA
        responses = []
        response_templates = [
            "Salam {name} ! Hamdoulillah ça fait plaisir ! ✨",
            "Salam ma sœur ! Mashallah merci pour ton retour 💕",
            "Salam {name} ! Oui bien sûr, je note ton idée inchaAllah 🌟",
            "Salam ! Barakallahu fiki, ça me touche beaucoup 💖",
            "Salam {name} ! De rien, on s'entraide entre sœurs ! 🤗"
        ]
        
        for i, comment in enumerate(comments):
            template = response_templates[i % len(response_templates)]
            name = comment.get("username", "").replace("@", "").split("_")[0]
            
            responses.append({
                "id": comment["id"],
                "username": comment["username"],
                "comment_text": comment["text"],
                "chatgpt_response": template.format(name=name),
                "validated": False,
                "action": "pending",
                "modified": False
            })
        
        return {
            "session_id": session_id,
            "responses": responses,
            "count": len(responses)
        }
        
    except Exception as e:
        logger.error(f"Response generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/responses/validate")
async def validate_response(data: dict):
    try:
        response_id = data.get("response_id")
        action = data.get("action")
        new_response = data.get("new_response")
        
        logger.info(f"Validating response {response_id} with action {action}")
        
        return {
            "status": "success",
            "message": f"Réponse {response_id} {action}",
            "response_id": response_id,
            "action": action,
            "new_response": new_response
        }
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/responses/validate/batch")
async def validate_batch(data: dict):
    try:
        action = data.get("action")
        response_ids = data.get("response_ids", [])
        
        logger.info(f"Batch validation: {action} for {len(response_ids)} responses")
        
        return {
            "status": "success",
            "message": f"Validation {action} appliquée à {len(response_ids)} réponses",
            "action": action,
            "count": len(response_ids)
        }
        
    except Exception as e:
        logger.error(f"Batch validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/export/excel/{session_id}")
async def export_excel(session_id: str, responses: list):
    try:
        import pandas as pd
        from io import BytesIO
        from fastapi.responses import StreamingResponse
        
        # Préparer les données
        data = []
        for response in responses:
            data.append({
                "session_id": session_id,
                "username": response.get("username", ""),
                "comment_text": response.get("comment_text", ""),
                "chatgpt_response": response.get("chatgpt_response", ""),
                "validated": response.get("validated", False),
                "action": response.get("action", "pending"),
                "timestamp": datetime.now().isoformat()
            })
        
        # Créer Excel en mémoire
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
        logger.error(f"Excel export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/export/json/{session_id}")
async def export_json(session_id: str, responses: list):
    try:
        export_data = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "responses": responses,
            "count": len(responses)
        }
        
        from fastapi.responses import Response
        
        return Response(
            content=json.dumps(export_data, indent=2, ensure_ascii=False),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=tiktok_responses_{session_id}.json"}
        )
        
    except Exception as e:
        logger.error(f"JSON export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Point d'entrée pour Railway
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )