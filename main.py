# main.py - Version COMPLÈTE avec toutes les fonctionnalités du script original
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
from selenium.webdriver.common.keys import Keys

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
    title="TikTok Automation API - COMPLET",
    description="API avec scraping TikTok réel + connexion + validation + publication",
    version="3.0.0"
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

# Sessions actives (stockage en mémoire)
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

# SOLUTION CHROMEDRIVER POUR RAILWAY (CORRIGÉ)
def get_chrome_driver_path():
    """Détecter le chemin correct de ChromeDriver selon l'environnement"""
    if RAILWAY_ENVIRONMENT:
        # Tester plusieurs chemins possibles sur Railway
        possible_paths = [
            "/usr/bin/chromedriver",      # Chemin nixpacks standard
            "/app/.chromedriver/bin/chromedriver",  # Chemin buildpack
            "/usr/local/bin/chromedriver", # Chemin alternatif
            "/opt/google/chrome/chromedriver", # Chemin Google Chrome
        ]
        
        for path in possible_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                logger.info(f"✅ ChromeDriver trouvé: {path}")
                return path
        
        logger.error("❌ ChromeDriver introuvable sur Railway")
        return None
    else:
        # Environnement local - utiliser webdriver-manager
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            path = ChromeDriverManager().install()
            logger.info(f"✅ ChromeDriver local: {path}")
            return path
        except Exception as e:
            logger.error(f"❌ Erreur webdriver-manager: {e}")
            return None

def get_chrome_binary_path():
    """Détecter le chemin correct de Chrome/Chromium"""
    if RAILWAY_ENVIRONMENT:
        possible_paths = [
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser", 
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/app/.chrome-for-testing/chrome"
        ]
        
        for path in possible_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                logger.info(f"✅ Chrome/Chromium trouvé: {path}")
                return path
        
        logger.error("❌ Chrome/Chromium introuvable sur Railway")
        return None
    else:
        # Laisser Chrome utiliser le chemin par défaut
        return None

# Classe pour le scraping TikTok COMPLET (avec toutes les fonctionnalités)
class TikTokCompleteScraper:
    def __init__(self, config: dict, websocket_manager: WebSocketManager, session_id: str):
        self.config = config
        self.websocket_manager = websocket_manager
        self.session_id = session_id
        self.driver = None
        self.video_data = None
        self.comments = []
        self.logged_in = False
        
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
        """Configuration du driver Selenium CORRIGÉE pour Railway"""
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
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
            
            # User agent pour éviter la détection
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            
            # 🔧 CORRECTION PRINCIPALE : Détection automatique des chemins
            driver_path = get_chrome_driver_path()
            binary_path = get_chrome_binary_path()
            
            if not driver_path:
                raise Exception("ChromeDriver introuvable")
            
            if binary_path:
                chrome_options.binary_location = binary_path
                logger.info(f"🔧 Chrome binary: {binary_path}")
            
            logger.info(f"🔧 ChromeDriver path: {driver_path}")
            
            # Créer le service avec le bon chemin
            service = Service(driver_path)
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Supprimer les indicateurs WebDriver
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("✅ Driver Selenium configuré avec succès")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur configuration driver: {e}")
            # Debug supplémentaire
            logger.error(f"RAILWAY_ENVIRONMENT: {RAILWAY_ENVIRONMENT}")
            logger.error(f"Driver path tenté: {driver_path if 'driver_path' in locals() else 'N/A'}")
            logger.error(f"Binary path tenté: {binary_path if 'binary_path' in locals() else 'N/A'}")
            return False
    
    async def wait_for_manual_login(self):
        """Attendre la connexion manuelle TikTok (FONCTIONNALITÉ AJOUTÉE)"""
        try:
            await self.send_progress("login_required", 20, "🔐 Connexion TikTok requise - Attendez l'autorisation manuelle...")
            
            # Naviguer vers TikTok
            self.driver.get(self.config["tiktok_url"])
            await asyncio.sleep(3)
            
            # Détecter si une connexion est nécessaire
            login_indicators = [
                "//button[contains(text(), 'Log in')]",
                "//button[contains(text(), 'Se connecter')]", 
                "//a[contains(@href, '/login')]",
                "//div[contains(text(), 'Log in to follow')]"
            ]
            
            needs_login = False
            for indicator in login_indicators:
                try:
                    if self.driver.find_elements(By.XPATH, indicator):
                        needs_login = True
                        break
                except:
                    continue
            
            if needs_login:
                await self.send_progress("manual_login", 25, "🔐 Connexion manuelle requise. Le navigateur va s'ouvrir en mode visible...", {
                    "action_required": "manual_login",
                    "message": "Connectez-vous manuellement à TikTok, puis cliquez sur 'Continuer' dans l'interface."
                })
                
                # Stocker l'état pour permettre l'interaction manuelle
                active_sessions[self.session_id] = {
                    "driver": self.driver,
                    "status": "waiting_login",
                    "config": self.config
                }
                
                # Attendre que l'utilisateur confirme la connexion
                return False  # Indique qu'on doit attendre
            else:
                self.logged_in = True
                await self.send_progress("logged_in", 30, "✅ Déjà connecté à TikTok")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erreur vérification connexion: {e}")
            await self.send_progress("error", 25, f"Erreur connexion: {str(e)}")
            return False
    
    async def extract_video_details(self):
        """Extraire les détails de la vidéo (adapté du script original)"""
        try:
            await self.send_progress("video_extraction", 40, "Extraction des informations vidéo...")
            
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
            
            self.video_data = {
                "title": video_title,
                "hashtags": hashtags,
                "url": self.config["tiktok_url"]
            }
            
            await self.send_progress("video_extracted", 50, "Informations vidéo extraites", self.video_data)
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur extraction vidéo: {e}")
            await self.send_progress("error", 40, f"Erreur extraction vidéo: {str(e)}")
            return False
    
    async def scroll_to_load_comments(self):
        """Charger tous les commentaires par défilement"""
        try:
            await self.send_progress("comments_loading", 60, "Chargement des commentaires...")
            
            # Attendre que les commentaires soient présents
            try:
                WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@data-e2e='comment-item']"))
                )
            except TimeoutException:
                logger.warning("⚠️ Tentative d'ouverture de la section commentaires...")
                
                try:
                    comments_button = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[@data-e2e='comment-icon']"))
                    )
                    self.driver.execute_script("arguments[0].click();", comments_button)
                    await self.send_progress("comments_opened", 65, "Section commentaires ouverte")
                    await asyncio.sleep(2)
                except TimeoutException:
                    logger.info("ℹ️ Section commentaires déjà ouverte")
            
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
            max_scrolls = 20
            
            while scroll_count < max_scrolls:
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", comment_container)
                await asyncio.sleep(2)
                
                new_height = self.driver.execute_script("return arguments[0].scrollHeight", comment_container)
                scroll_count += 1
                
                progress = 65 + min(10, (scroll_count / max_scrolls) * 10)
                await self.send_progress("comments_loading", int(progress), f"Chargement des commentaires... ({scroll_count}/{max_scrolls})")
                
                if new_height == last_height:
                    logger.info(f"✅ Fin du scroll atteinte après {scroll_count} tentatives")
                    break
                    
                last_height = new_height
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur chargement commentaires: {e}")
            await self.send_progress("error", 65, f"Erreur chargement commentaires: {str(e)}")
            return False
    
    async def scrape_all_comments(self):
        """Scraper tous les commentaires (ADAPTÉ du script original)"""
        try:
            await self.send_progress("comments_scraping", 75, "Extraction des commentaires...")
            
            # Trouver tous les blocs de commentaires
            comment_blocks = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'DivCommentContentWrapper')]")
            
            if not comment_blocks:
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
                    # Extraire le nom d'utilisateur (logique du script original)
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
                    
                    # Exclure les commentaires du propriétaire
                    if self.config.get("exclude_owner", True) and username.lower().strip() == excluded_username:
                        logger.info(f"🚫 Commentaire exclu: {username}")
                        continue
                    
                    # IMPORTANT: Conserver l'élément pour pouvoir répondre plus tard
                    comments_data.append({
                        'id': i,
                        'username': username,
                        'text': comment_text,
                        'timestamp': "N/A",
                        'element': comment_block  # 🔑 Clé pour la publication
                    })
                    
                    logger.info(f"✅ Commentaire {i}: {username} - {comment_text[:50]}...")
                    
                    if i % 5 == 0:
                        progress = 75 + min(15, (i / len(comment_blocks)) * 15)
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
        """Processus principal de scraping COMPLET"""
        try:
            # Étape 1: Configuration du driver
            await self.send_progress("init", 5, "Configuration du navigateur...")
            if not self.setup_driver():
                raise Exception("Échec configuration du navigateur")
            
            # Étape 2: Vérification connexion TikTok
            await self.send_progress("login_check", 15, "Vérification connexion TikTok...")
            login_success = await self.wait_for_manual_login()
            
            if not login_success:
                # Attendre la confirmation manuelle
                await self.send_progress("waiting_login", 25, "En attente de connexion manuelle...", {
                    "action_required": "manual_login",
                    "session_id": self.session_id
                })
                return  # Arrêter ici, reprendre après confirmation
            
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
            
            # Étape 6: Stocker la session pour validation et publication
            active_sessions[self.session_id] = {
                "driver": self.driver,
                "video_data": self.video_data,
                "comments": comments,
                "config": self.config,
                "status": "ready_for_responses"
            }
            
            # Étape 7: Finalisation
            await self.send_progress("completed", 100, f"Scraping terminé - {len(comments)} commentaires", {
                "video_info": self.video_data,
                "comments": comments,
                "session_ready": True
            })
            
        except Exception as e:
            logger.error(f"❌ Erreur processus scraping: {e}")
            await self.send_progress("error", 0, f"Erreur: {str(e)}")
        # Note: Ne pas fermer le driver ici, on en a besoin pour publier les réponses

# Service OpenAI réel (adapté du script original)
class OpenAICompleteService:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    async def generate_batch_responses(self, comments: List[dict], config: dict) -> List[dict]:
        """Générer des réponses en batch (ADAPTÉ du script original)"""
        if not comments:
            return []
        
        try:
            video_title = config.get("video_title", "Vidéo TikTok")
            hashtags = config.get("hashtags", [])
            account_name = config.get("account_name", "Soeur Bon Plan 🎀")
            max_length = config.get("max_response_length", 114)
            tone = config.get("tone", "chaleureux")
            
            # Prompt adapté du script original
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
            logger.info(f"OpenAI response received: {len(response_text)} characters")
            
            # Nettoyer le JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            parsed_response = json.loads(response_text)
            api_responses = parsed_response.get("responses", [])
            
            # Convertir en format attendu avec référence à l'élément
            ai_responses = []
            for api_resp in api_responses:
                comment_id = api_resp.get("comment_id")
                # Trouver l'élément correspondant
                comment_element = None
                for comment in comments:
                    if comment['id'] == comment_id:
                        comment_element = comment.get('element')
                        break
                
                ai_responses.append({
                    "id": comment_id,
                    "username": api_resp.get("username"),
                    "comment_text": api_resp.get("comment_text"),
                    "chatgpt_response": api_resp.get("chatgpt_response"),
                    "validated": False,
                    "action": "pending",
                    "modified": False,
                    "element": comment_element  # 🔑 Pour la publication
                })
            
            logger.info(f"✅ {len(ai_responses)} réponses générées par OpenAI")
            return ai_responses
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erreur parsing JSON OpenAI: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Erreur OpenAI API: {e}")
            return []

# NOUVELLES FONCTIONS pour la publication des commentaires
async def reply_to_comment_selenium(driver, comment_element, ai_reply):
    """Publier une réponse à un commentaire (ADAPTÉ du script original)"""
    try:
        # Trouver le bouton de réponse
        reply_button_selectors = [
            ".//button[@data-e2e='reply-button']",
            ".//span[@aria-label='Reply' and @role='button']",
            ".//span[@aria-label='Répondre' and @role='button']",
            ".//span[contains(text(), 'Reply')]/ancestor::button",
            ".//span[contains(text(), 'Répondre')]/ancestor::button",
            ".//button[contains(@class, 'reply-btn')]"
        ]
        
        reply_button = None
        for selector in reply_button_selectors:
            try:
                reply_button = comment_element.find_element(By.XPATH, selector)
                if reply_button:
                    logger.info(f"Found reply button using selector: {selector}")
                    break
            except NoSuchElementException:
                continue
        
        if not reply_button:
            logger.error("Reply button not found within the comment.")
            return False

        # Scroll et cliquer sur le bouton de réponse
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", reply_button)
        await asyncio.sleep(0.5)
        driver.execute_script("arguments[0].click();", reply_button)
        logger.info("Reply button clicked.")

        # Attendre le champ de saisie
        reply_input_selectors = [
            "//div[@class='public-DraftEditorPlaceholder-inner' and contains(text(), 'Ajouter une réponse')]/following::div[@contenteditable='true'][1]",
            "//div[@class='public-DraftEditorPlaceholder-inner' and contains(text(), 'Add a reply')]/following::div[@contenteditable='true'][1]",
            "//div[@data-e2e='comment-input']//div[@contenteditable='true']",
            "//div[@contenteditable='true' and @role='textbox']",
            "//div[contains(@class, 'notranslate') and @contenteditable='true']"
        ]
        
        reply_input = None
        for selector in reply_input_selectors:
            try:
                reply_input = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, selector))
                )
                if reply_input:
                    logger.info(f"Found reply input using selector: {selector}")
                    break
            except TimeoutException:
                continue

        if not reply_input:
            logger.error("Reply input field not found.")
            return False

        # Saisir la réponse
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", reply_input)
        await asyncio.sleep(0.5)
        driver.execute_script("arguments[0].click();", reply_input)
        await asyncio.sleep(0.5)
        
        # Utiliser JavaScript pour insérer le texte
        driver.execute_script("arguments[0].textContent = arguments[1];", reply_input, ai_reply)
        
        # Déclencher les événements pour que TikTok détecte le changement
        driver.execute_script("""
            var element = arguments[0];
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
        """, reply_input)
        
        logger.info(f"AI reply entered: {ai_reply}")
        await asyncio.sleep(2)

        # Trouver et cliquer sur le bouton publier
        try:
            publish_buttons = driver.find_elements(By.XPATH, "//div[@data-e2e='comment-post' and @role='button' and @aria-disabled='false']")
            if len(publish_buttons) >= 2:
                publish_button = publish_buttons[1]  # Deuxième bouton (pour les réponses)
            elif len(publish_buttons) == 1:
                publish_button = publish_buttons[0]
            else:
                logger.error("No publish button found.")
                return False

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", publish_button)
            await asyncio.sleep(1)
            driver.execute_script("arguments[0].click();", publish_button)
            logger.info("Publish button clicked. Comment posted.")
            await asyncio.sleep(3)  # Attendre la publication

            return True

        except Exception as e:
            logger.error(f"Error finding or clicking publish button: {e}")
            return False

    except Exception as e:
        logger.error(f"Error replying to comment: {e}")
        return False

# Routes principales
@app.get("/")
async def root():
    return {
        "message": "TikTok Automation API - COMPLET",
        "status": "running",
        "version": "3.0.0",
        "environment": ENVIRONMENT,
        "features": [
            "VRAI scraping TikTok",
            "Connexion manuelle TikTok",
            "Validation interactive",
            "Publication réelle des réponses",
            "Export Excel"
        ],
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
        "chrome_driver": get_chrome_driver_path(),
        "chrome_binary": get_chrome_binary_path(),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health/detailed")
async def health_detailed():
    """Health check détaillé avec test Chrome CORRIGÉ"""
    try:
        # Test Chrome
        chrome_status = "unknown"
        error_details = None
        
        try:
            driver_path = get_chrome_driver_path()
            binary_path = get_chrome_binary_path()
            
            if not driver_path:
                chrome_status = "error: ChromeDriver not found"
            else:
                options = Options()
                options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                
                if binary_path:
                    options.binary_location = binary_path
                
                service = Service(driver_path)
                driver = webdriver.Chrome(service=service, options=options)
                driver.get("data:text/html,<html><body><h1>Test OK</h1></body></html>")
                driver.quit()
                chrome_status = "operational"
                
        except Exception as e:
            chrome_status = f"error: {str(e)}"
            error_details = {
                "driver_path": get_chrome_driver_path(),
                "binary_path": get_chrome_binary_path(),
                "railway_env": bool(RAILWAY_ENVIRONMENT),
                "error": str(e)
            }
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "TikTok Automation API COMPLET",
            "version": "3.0.0",
            "environment": "railway" if RAILWAY_ENVIRONMENT else "local",
            "services": {
                "api": "operational",
                "chrome": chrome_status,
                "openai": "configured" if OPENAI_API_KEY else "not configured",
                "websocket": "operational"
            },
            "chrome_details": error_details,
            "active_sessions": len(active_sessions),
            "endpoints": [
                "/health",
                "/health/detailed", 
                "/ws/{session_id}",
                "/api/scraping/start/{session_id}",
                "/api/scraping/continue/{session_id}",
                "/api/responses/generate/{session_id}",
                "/api/responses/validate",
                "/api/responses/publish/{session_id}",
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
async def start_complete_scraping(session_id: str, config: dict, background_tasks: BackgroundTasks):
    """Démarrer le scraping COMPLET avec toutes les fonctionnalités"""
    try:
        if not config.get("tiktok_url"):
            raise HTTPException(status_code=400, detail="URL TikTok requise")
        
        openai_key = config.get("openai_key") or OPENAI_API_KEY
        if not openai_key:
            raise HTTPException(status_code=400, detail="Clé OpenAI requise")
        
        logger.info(f"🚀 Démarrage du scraping COMPLET pour session: {session_id}")
        logger.info(f"🎯 URL: {config['tiktok_url']}")
        
        # Créer le scraper complet
        scraper = TikTokCompleteScraper(config, manager, session_id)
        background_tasks.add_task(scraper.start_scraping_process)
        
        return {
            "message": "Scraping COMPLET TikTok démarré",
            "session_id": session_id,
            "status": "started",
            "features": ["real_scraping", "manual_login", "comment_posting"],
            "environment": "railway" if RAILWAY_ENVIRONMENT else "local"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur démarrage scraping: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scraping/continue/{session_id}")
async def continue_after_login(session_id: str):
    """Continuer le scraping après connexion manuelle TikTok (NOUVELLE FONCTIONNALITÉ)"""
    try:
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session non trouvée")
        
        session = active_sessions[session_id]
        if session.get("status") != "waiting_login":
            raise HTTPException(status_code=400, detail="Session pas en attente de connexion")
        
        driver = session.get("driver")
        config = session.get("config")
        
        if not driver:
            raise HTTPException(status_code=500, detail="Driver non disponible")
        
        logger.info(f"🔄 Reprise du scraping après connexion manuelle: {session_id}")
        
        # Créer un nouveau scraper avec le driver existant
        scraper = TikTokCompleteScraper(config, manager, session_id)
        scraper.driver = driver
        scraper.logged_in = True
        
        # Reprendre le processus à partir de l'extraction vidéo
        async def continue_scraping():
            try:
                await scraper.send_progress("resuming", 35, "Reprise du scraping après connexion...")
                
                if not await scraper.extract_video_details():
                    raise Exception("Échec extraction informations vidéo")
                
                if not await scraper.scroll_to_load_comments():
                    raise Exception("Échec chargement commentaires")
                
                comments = await scraper.scrape_all_comments()
                
                if not comments:
                    raise Exception("Aucun commentaire trouvé")
                
                # Mettre à jour la session
                active_sessions[session_id].update({
                    "video_data": scraper.video_data,
                    "comments": comments,
                    "status": "ready_for_responses"
                })
                
                await scraper.send_progress("completed", 100, f"Scraping terminé - {len(comments)} commentaires", {
                    "video_info": scraper.video_data,
                    "comments": comments,
                    "session_ready": True
                })
                
            except Exception as e:
                logger.error(f"❌ Erreur reprise scraping: {e}")
                await scraper.send_progress("error", 0, f"Erreur: {str(e)}")
        
        # Lancer en arrière-plan
        asyncio.create_task(continue_scraping())
        
        return {
            "message": "Scraping repris après connexion",
            "session_id": session_id,
            "status": "resumed"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur reprise scraping: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/responses/generate/{session_id}")
async def generate_complete_responses(session_id: str, data: dict):
    """Générer les réponses IA avec toutes les données nécessaires"""
    try:
        comments = data.get("comments", [])
        config = data.get("config", {})
        
        # Récupérer les données de la session si disponibles
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
        
        logger.info(f"🤖 Génération COMPLÈTE de réponses pour {len(comments)} commentaires")
        
        # Service OpenAI complet
        openai_service = OpenAICompleteService(openai_key)
        responses = await openai_service.generate_batch_responses(comments, config)
        
        # Stocker les réponses dans la session
        if session_id in active_sessions:
            active_sessions[session_id]["responses"] = responses
        
        return {
            "session_id": session_id,
            "responses": responses,
            "count": len(responses),
            "ai_mode": "REAL",
            "ready_for_validation": True
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur génération réponses: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/responses/publish/{session_id}")
async def publish_responses(session_id: str, data: dict, background_tasks: BackgroundTasks):
    """Publier les réponses validées sur TikTok (NOUVELLE FONCTIONNALITÉ)"""
    try:
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session non trouvée")
        
        session = active_sessions[session_id]
        driver = session.get("driver")
        
        if not driver:
            raise HTTPException(status_code=500, detail="Driver non disponible pour publication")
        
        validated_responses = data.get("responses", [])
        approved_responses = [r for r in validated_responses if r.get("validated", False)]
        
        logger.info(f"📤 Publication de {len(approved_responses)} réponses sur TikTok")
        
        async def publish_task():
            try:
                await manager.send_message(session_id, {
                    "type": "publishing",
                    "message": f"Publication de {len(approved_responses)} réponses...",
                    "total": len(approved_responses)
                })
                
                success_count = 0
                
                for i, response in enumerate(approved_responses, 1):
                    try:
                        comment_element = response.get("element")
                        if not comment_element:
                            logger.warning(f"Élément manquant pour réponse {i}")
                            continue
                        
                        await manager.send_message(session_id, {
                            "type": "publishing_progress",
                            "message": f"Publication {i}/{len(approved_responses)}: {response.get('username', 'N/A')}",
                            "progress": int((i / len(approved_responses)) * 100)
                        })
                        
                        # Publier la réponse
                        success = await reply_to_comment_selenium(
                            driver, 
                            comment_element, 
                            response.get("chatgpt_response", "")
                        )
                        
                        if success:
                            success_count += 1
                            logger.info(f"✅ Réponse publiée {i}/{len(approved_responses)}")
                        else:
                            logger.error(f"❌ Échec publication {i}/{len(approved_responses)}")
                        
                        # Délai entre publications
                        await asyncio.sleep(3)
                        
                    except Exception as e:
                        logger.error(f"❌ Erreur publication réponse {i}: {e}")
                        continue
                
                await manager.send_message(session_id, {
                    "type": "publishing_complete",
                    "message": f"Publication terminée: {success_count}/{len(approved_responses)} réussies",
                    "success_count": success_count,
                    "total": len(approved_responses)
                })
                
            except Exception as e:
                logger.error(f"❌ Erreur tâche publication: {e}")
                await manager.send_message(session_id, {
                    "type": "publishing_error",
                    "message": f"Erreur publication: {str(e)}"
                })
        
        # Lancer la publication en arrière-plan
        background_tasks.add_task(publish_task)
        
        return {
            "message": "Publication démarrée",
            "session_id": session_id,
            "responses_to_publish": len(approved_responses),
            "status": "publishing"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur démarrage publication: {e}")
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
        # Récupérer les données de la session
        video_title = "TikTok Video"
        if session_id in active_sessions:
            session = active_sessions[session_id]
            if session.get("video_data"):
                video_title = session["video_data"].get("title", "TikTok Video")
        
        # Préparer les données
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

@app.delete("/api/sessions/{session_id}")
async def cleanup_session(session_id: str):
    """Nettoyer une session et fermer le driver"""
    try:
        if session_id in active_sessions:
            session = active_sessions[session_id]
            driver = session.get("driver")
            
            if driver:
                try:
                    driver.quit()
                    logger.info(f"🔒 Driver fermé pour session {session_id}")
                except Exception as e:
                    logger.error(f"Erreur fermeture driver: {e}")
            
            del active_sessions[session_id]
            logger.info(f"🧹 Session {session_id} nettoyée")
        
        return {"message": "Session nettoyée", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT)