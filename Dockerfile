FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11-slim

# Passer en root pour installer Chrome
USER root

# Installation des outils nécessaires pour Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installation Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Installation ChromeDriver
RUN CHROMEDRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE) \
    && wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip \
    && unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm /tmp/chromedriver.zip

# Installation Selenium
RUN pip install --no-cache-dir selenium==4.15.2

# Variables d'environnement Chrome
ENV CHROME_BIN=/usr/bin/google-chrome-stable
ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver
ENV RAILWAY_ENVIRONMENT=true

# Test que Chrome fonctionne
RUN google-chrome-stable --version && chromedriver --version

# Copie des fichiers d'application
COPY main_phase1.py /app/main.py
COPY start.py /app/start.py

# Retour à l'utilisateur root (nécessaire pour Chrome sur Railway)
USER root

WORKDIR /app

# Démarrage avec script Python
CMD ["python", "start.py"]