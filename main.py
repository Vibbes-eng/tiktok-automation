# main.py - Version avec VRAI scraping TikTok (CORRIGÉ POUR RAILWAY)
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
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

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
    title="TikTok Automation API - Vrai Scraping",
    description="API avec scraping TikTok réel via Selenium",
    version="2.0.0"
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
RAILWAY_ENVIRONMENT = os.getenv("RAILWAY_ENVIRONMENT")

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

# Classe pour le scraping TikTok réel (ADAPTÉE POUR RAILWAY)
class TikTokRealScraper:
    def __init__(self, config: dict, websocket_manager: WebSocketManager, session_id: str):
        self.config = config
        self.websocket_manager = websocket_manager
        self.session_id = session_id
        self.driver = None
        self.video_data = None
        self.comments = []
        
    async def send_progress(self, step: str, progress: int, message: str, data: Optional[Dict] = None):
        """Envoyer le progrès via WebSocket"""
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
        """Configuration du driver Selenium pour Railway/Production"""
        try:
            chrome_options = Options()
            
            # Options essentielles pour Railway/Docker
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-background-networking")
            chrome_options.add_argument("--disable-sync")
            chrome_options.add_argument("--disable-translate")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # User agent pour éviter la détection
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            
            # Configuration spécifique pour Railway
            if RAILWAY_ENVIRONMENT:
                logger.info("🚂 Configuration Railway détectée")
                # Utiliser le chromium installé par nixpacks
                chrome_options.binary_location = "/usr/bin/chromium"
                
                # Service avec le chromedriver de nixpacks
                service = Service("/usr/bin/chromedriver")
                
                # Options supplémentaires pour Railway
                chrome_options.add_argument("--disable-features=VizDisplayCompositor")
                chrome_options.add_argument("--disable-web-security")
                chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
            else:
                # Configuration locale avec webdriver-manager
                logger.info("💻 Configuration locale")
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Supprimer les indicateurs WebDriver
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("✅ Driver Selenium configuré avec succès")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur configuration driver: {e}")
            logger.error(f"Chrome binary location: {chrome_options.binary_location if hasattr(chrome_options, 'binary_location') else 'default'}")
            return False
    
    async def extract_video_details(self):
        """Extraire les détails de la vidéo (adapté du script original)"""
        try:
            await self.send_progress("video_extraction", 30, "Extraction des informations vidéo...")
            
            # Attendre un peu pour le chargement complet
            await asyncio.sleep(2)
            
            # Extraire le titre
            video_title = "Titre non trouvé"
            title_selectors = [
                "//h1[@data-e2e='video-title']",
                "//h1[contains(@class, 'video-meta-title')]",
                "//h1",
                "//span[@data-e2e='new-desc-span']",
                "//div[@data-e2e='video-desc']//span"
            ]
            
            for selector in title_selectors:
                try:
                    element = self.driver.find_element(By.XPATH, selector)
                    if element.text.strip():
                        video_title = element.text.strip()
                        logger.info(f"✅ Titre trouvé: {video_title[:100]}...")
                        break
                except NoSuchElementException:
                    continue
            
            # Extraire les hashtags
            hashtags = []
            hashtag_selectors = [
                "//a[@data-e2e='browse-video-hashtag']",
                "//a[contains(@href, '/tag/')]",
                "//strong[contains(text(), '#')]",
                "//strong[contains(@class, 'StrongText') and contains(text(), '#')]"
            ]
            
            for selector in hashtag_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        hashtags = [elem.text.strip() for elem in elements if elem.text.strip().startswith('#')]
                        logger.info(f"✅ Hashtags trouvés: {hashtags}")
                        break
                except NoSuchElementException:
                    continue
            
            # Extraire les stats (si possible)
            stats = {"views": "N/A", "likes": "N/A", "comments": "N/A"}
            
            self.video_data = {
                "title": video_title,
                "hashtags": hashtags,
                "views": stats["views"],
                "likes": stats["likes"],
                "comments_count": stats["comments"],
                "author": "N/A"
            }
            
            await self.send_progress("video_extracted", 40, "Informations vidéo extraites", self.video_data)
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur extraction vidéo: {e}")
            await self.send_progress("error", 40, f"Erreur extraction vidéo: {str(e)}")
            return False
    
    async def scroll_to_load_comments(self):
        """Charger tous les commentaires par défilement (adapté du script original)"""
        try:
            await self.send_progress("comments_loading", 50, "Chargement des commentaires...")
            
            # Attendre que les commentaires soient présents
            try:
                WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@data-e2e='comment-item']"))
                )
            except TimeoutException:
                logger.warning("⚠️ Aucun commentaire trouvé rapidement, tentative de clic sur commentaires...")
                
                # Essayer de cliquer sur le bouton commentaires
                try:
                    comments_button = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[@data-e2e='comment-icon']"))
                    )
                    self.driver.execute_script("arguments[0].click();", comments_button)
                    await self.send_progress("comments_opened", 55, "Section commentaires ouverte")
                    await asyncio.sleep(2)
                except TimeoutException:
                    logger.info("ℹ️ Section commentaires déjà ouverte ou bouton non trouvé")
            
            # Trouver le conteneur de commentaires
            try:
                comment_container = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'DivCommentListContainer')]"))
                )
                logger.info("✅ Conteneur de commentaires trouvé")
            except TimeoutException:
                logger.error("❌ Conteneur de commentaires non trouvé")
                return False
            
            # Défiler pour charger tous les commentaires
            last_height = self.driver.execute_script("return arguments[0].scrollHeight", comment_container)
            scroll_count = 0
            max_scrolls = 20  # Limite pour éviter les boucles infinies
            
            while scroll_count < max_scrolls:
                # Scroll down
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", comment_container)
                await asyncio.sleep(2)  # Attendre le chargement
                
                new_height = self.driver.execute_script("return arguments[0].scrollHeight", comment_container)
                scroll_count += 1
                
                # Mise à jour du progrès
                progress = 55 + min(15, (scroll_count / max_scrolls) * 15)
                await self.send_progress("comments_loading", int(progress), f"Chargement des commentaires... ({scroll_count}/{max_scrolls})")
                
                if new_height == last_height:
                    logger.info(f"✅ Fin du scroll atteinte après {scroll_count} tentatives")
                    break
                    
                last_height = new_height
            
            logger.info("✅ Chargement des commentaires terminé")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur chargement commentaires: {e}")
            await self.send_progress("error", 60, f"Erreur chargement commentaires: {str(e)}")
            return False
    
    async def scrape_all_comments(self):
        """Scraper tous les commentaires (adapté du script original)"""
        try:
            await self.send_progress("comments_scraping", 70, "Extraction des commentaires...")
            
            # Trouver tous les blocs de commentaires
            comment_blocks = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'DivCommentContentWrapper')]")
            
            if not comment_blocks:
                # Essayer d'autres sélecteurs
                alternative_selectors = [
                    "//div[@data-e2e='comment-item']",
                    "//div[contains(@class, 'CommentItemContainer')]",
                    "//div[contains(@class, 'comment-item')]"
                ]
                
                for selector in alternative_selectors:
                    comment_blocks = self.driver.find_elements(By.XPATH, selector)
                    if comment_blocks:
                        logger.info(f"✅ Commentaires trouvés avec sélecteur alternatif: {selector}")
                        break
            
            logger.info(f"📊 {len(comment_blocks)} blocs de commentaires trouvés")
            
            comments_data = []
            excluded_username = self.config.get("account_name", "").lower().strip()
            
            for i, comment_block in enumerate(comment_blocks, 1):
                try:
                    # Extraire le nom d'utilisateur
                    username = ""
                    username_selectors = [
                        ".//div[@data-e2e='comment-username-1']//a",
                        ".//a[contains(@class, 'username')]",
                        ".//span[contains(@class, 'username')]"
                    ]
                    
                    for selector in username_selectors:
                        try:
                            username_element = comment_block.find_element(By.XPATH, selector)
                            href = username_element.get_attribute("href")
                            if href and "/@" in href:
                                username = "@" + href.split("/@")[-1].split("?")[0]
                            else:
                                username = username_element.text.strip()
                            if username:
                                break
                        except NoSuchElementException:
                            continue
                    
                    # Essayer d'obtenir le nom d'affichage
                    if not username:
                        try:
                            display_name_element = comment_block.find_element(By.XPATH, ".//p[contains(@class, 'TUXText') and contains(@class, 'weight-medium')]")
                            username = display_name_element.text.strip()
                        except NoSuchElementException:
                            username = f"@user_{i}"
                    
                    # Extraire le texte du commentaire
                    comment_text = ""
                    comment_selectors = [
                        ".//span[@data-e2e='comment-level-1']/p",
                        ".//span[@data-e2e='comment-level-1']",
                        ".//div[contains(@class, 'comment-text')]",
                        ".//p[contains(@class, 'comment-text')]"
                    ]
                    
                    for selector in comment_selectors:
                        try:
                            comment_element = comment_block.find_element(By.XPATH, selector)
                            comment_text = comment_element.text.strip()
                            if comment_text:
                                break
                        except NoSuchElementException:
                            continue
                    
                    if not comment_text:
                        logger.warning(f"⚠️ Texte de commentaire vide pour l'élément {i}")
                        continue
                    
                    # Exclure les commentaires du propriétaire si configuré
                    if self.config.get("exclude_owner", True) and username.lower().strip() == excluded_username:
                        logger.info(f"🚫 Commentaire exclu: {username}")
                        continue
                    
                    comments_data.append({
                        'id': i,
                        'username': username,
                        'text': comment_text,
                        'timestamp': "N/A"
                    })
                    
                    logger.info(f"✅ Commentaire {i}: {username} - {comment_text[:50]}...")
                    
                    # Mise à jour du progrès
                    if i % 5 == 0:
                        progress = 70 + min(20, (i / len(comment_blocks)) * 20)
                        await self.send_progress("comments_scraping", int(progress), f"Commentaires extraits: {len(comments_data)}")
                
                except Exception as e:
                    logger.error(f"❌ Erreur extraction commentaire {i}: {e}")
                    continue
            
            self.comments = comments_data
            logger.info(f"🎉 Scraping terminé: {len(comments_data)} commentaires valides collectés")
            return comments_data
            
        except Exception as e:
            logger.error(f"❌ Erreur scraping commentaires: {e}")
            await self.send_progress("error", 80, f"Erreur scraping: {str(e)}")
            return []
    
    async def start_scraping_process(self):
        """Processus principal de scraping réel"""
        try:
            # Étape 1: Configuration du driver
            await self.send_progress("init", 5, "Configuration du navigateur...")
            if not self.setup_driver():
                raise Exception("Échec configuration du navigateur")
            
            # Étape 2: Navigation
            await self.send_progress("navigation", 15, "Navigation vers TikTok...")
            self.driver.get(self.config["tiktok_url"])
            await asyncio.sleep(3)  # Attendre le chargement
            
            # Étape 3: Extraction vidéo
            if not await self.extract_video_details():
                raise Exception("Échec extraction informations vidéo")
            
            # Étape 4: Chargement commentaires
            if not await self.scroll_to_load_comments():
                raise Exception("Échec chargement commentaires")
            
            # Étape 5: Scraping commentaires
            comments = await self.scrape_all_comments()
            
            if not comments:
                raise Exception("Aucun commentaire trouvé")
            
            # Étape 6: Finalisation
            await self.send_progress("completed", 100, f"Scraping terminé - {len(comments)} commentaires", {
                "video_info": self.video_data,
                "comments": comments
            })
            
        except Exception as e:
            logger.error(f"❌ Erreur processus scraping: {e}")
            await self.send_progress("error", 0, f"Erreur: {str(e)}")
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("🔒 Driver fermé")

# Service OpenAI réel
class OpenAIRealService:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    async def generate_batch_responses(self, comments: List[dict], config: dict) -> List[dict]:
        """Générer des réponses pour tous les commentaires en une fois (adapté du script original)"""
        if not comments:
            return []
        
        try:
            # Créer le prompt batch adapté du script original
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
            
            # Ajouter chaque commentaire au prompt
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

            # Appel à l'API OpenAI
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model="gpt-4",
                    messages=messages,
                    max_tokens=4000,
                    temperature=0.7,
                )
            )
            
            # Parser la réponse JSON
            response_text = response.choices[0].message.content.strip()
            logger.info(f"OpenAI response received: {len(response_text)} characters")
            
            # Nettoyer le JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            parsed_response = json.loads(response_text)
            api_responses = parsed_response.get("responses", [])
            
            # Convertir en format attendu
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
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erreur parsing JSON OpenAI: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Erreur OpenAI API: {e}")
            return []

# Routes principales
@app.get("/")
async def root():
    return {
        "message": "TikTok Automation API - Vrai Scraping",
        "status": "running",
        "version": "2.0.0",
        "environment": ENVIRONMENT,
        "scraping": "RÉEL (non simulé)",
        "railway": bool(RAILWAY_ENVIRONMENT)
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "openai_configured": bool(OPENAI_API_KEY),
        "environment": ENVIRONMENT,
        "scraping_mode": "REAL",
        "railway": bool(RAILWAY_ENVIRONMENT),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health/detailed")
async def health_detailed():
    """Health check détaillé pour monitoring"""
    try:
        import psutil
        import platform
        
        # Test Chrome si possible
        chrome_status = "unknown"
        try:
            from selenium import webdriver
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            if RAILWAY_ENVIRONMENT:
                options.binary_location = "/usr/bin/chromium"
                service = Service("/usr/bin/chromedriver")
            else:
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                
            driver = webdriver.Chrome(service=service, options=options)
            driver.quit()
            chrome_status = "operational"
        except Exception as e:
            logger.error(f"Chrome test failed: {e}")
            chrome_status = f"error: {str(e)}"
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "TikTok Automation API",
            "version": "2.0.0",
            "environment": "railway" if RAILWAY_ENVIRONMENT else "local",
            "system": {
                "platform": platform.system(),
                "python_version": platform.python_version(),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent
            },
            "services": {
                "api": "operational",
                "chrome": chrome_status,
                "openai": "configured" if OPENAI_API_KEY else "not configured",
                "websocket": "operational"
            },
            "endpoints": [
                "/health",
                "/health/detailed", 
                "/ws/{session_id}",
                "/api/scraping/start/{session_id}",
                "/api/responses/generate/{session_id}",
                "/api/responses/validate",
                "/api/export/excel/{session_id}"
            ]
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
async def start_real_scraping(session_id: str, config: dict, background_tasks: BackgroundTasks):
    """Démarrer le VRAI scraping TikTok avec Selenium"""
    try:
        # Validation
        if not config.get("tiktok_url"):
            raise HTTPException(status_code=400, detail="URL TikTok requise")
        
        openai_key = config.get("openai_key") or OPENAI_API_KEY
        if not openai_key:
            raise HTTPException(status_code=400, detail="Clé OpenAI requise")
        
        logger.info(f"🚀 Démarrage du VRAI scraping pour session: {session_id}")
        logger.info(f"🎯 URL: {config['tiktok_url']}")
        logger.info(f"🚂 Railway: {bool(RAILWAY_ENVIRONMENT)}")
        
        # Créer le scraper et lancer en arrière-plan
        scraper = TikTokRealScraper(config, manager, session_id)
        background_tasks.add_task(scraper.start_scraping_process)
        
        return {
            "message": "VRAI scraping TikTok démarré",
            "session_id": session_id,
            "status": "started",
            "scraping_mode": "REAL",
            "environment": "railway" if RAILWAY_ENVIRONMENT else "local"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur démarrage scraping: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/responses/generate/{session_id}")
async def generate_real_responses(session_id: str, data: dict):
    """Générer les VRAIES réponses IA avec OpenAI"""
    try:
        comments = data.get("comments", [])
        config = data.get("config", {})
        
        openai_key = config.get("openai_key") or OPENAI_API_KEY
        if not openai_key:
            raise HTTPException(status_code=400, detail="Clé OpenAI requise")
        
        logger.info(f"🤖 Génération RÉELLE de réponses pour {len(comments)} commentaires")
        
        # Service OpenAI réel
        openai_service = OpenAIRealService(openai_key)
        responses = await openai_service.generate_batch_responses(comments, config)
        
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
    try:
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