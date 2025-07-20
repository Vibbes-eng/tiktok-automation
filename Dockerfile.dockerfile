# Dockerfile - OPTIMISÉ pour Railway (Chrome garanti)
# Utilise une image qui a déjà Chrome + ChromeDriver installés
FROM selenium/standalone-chrome:4.15.0

# Passer en root pour configuration
USER root

# Installation Python et outils essentiels
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Créer lien symbolique python
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Variables d'environnement Railway
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV RAILWAY_ENVIRONMENT=true
ENV PORT=8000

# Variables Chrome (chemins garantis dans image Selenium)
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV DISPLAY=:99

# Vérification critique que Chrome est disponible
RUN echo "=== VÉRIFICATION CHROME ===" && \
    which google-chrome && \
    which chromedriver && \
    google-chrome --version && \
    chromedriver --version && \
    echo "=== CHROME OK ==="

# Configuration répertoire de travail
WORKDIR /app

# Copie et installation des dépendances Python
COPY requirements.txt .
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Test Selenium OBLIGATOIRE avant de continuer
RUN echo "=== TEST SELENIUM ===" && \
    python3 -c "
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

print('Test Selenium + Chrome...')
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

service = Service('/usr/bin/chromedriver')
driver = webdriver.Chrome(service=service, options=options)
driver.get('data:text/html,<html><head><title>Test OK</title></head><body><h1>Chrome fonctionne!</h1></body></html>')
title = driver.title
body_text = driver.find_element('tag name', 'h1').text
driver.quit()

print(f'✅ Selenium test réussi!')
print(f'Title: {title}')
print(f'Body: {body_text}')
assert 'Test OK' in title, 'Title test failed'
assert 'Chrome fonctionne' in body_text, 'Body test failed'
print('✅ Tous les tests passés!')
" && echo "=== SELENIUM OK ==="

# Copie du code de l'application
COPY . .

# Test de l'application Python
RUN python3 -c "
import main
print('✅ Application importée avec succès')
"

# Créer utilisateur non-root pour sécurité
RUN useradd -m -u 1001 railwayuser && \
    chown -R railwayuser:railwayuser /app

# Basculer vers utilisateur non-root
USER railwayuser

# Port d'exposition
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Commande de démarrage
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]