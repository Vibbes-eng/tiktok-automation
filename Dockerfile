# Dockerfile - Chrome garanti pour Railway
FROM selenium/standalone-chrome:4.15.0

# Passer en root
USER root

# Installation Python
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Lien symbolique python
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV RAILWAY_ENVIRONMENT=true
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV DISPLAY=:99

# Vérification Chrome
RUN google-chrome --version && chromedriver --version

# Répertoire de travail
WORKDIR /app

# Installation dépendances Python
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Test Selenium
RUN python3 -c "
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
driver = webdriver.Chrome(options=options)
driver.get('data:text/html,<h1>Test OK</h1>')
driver.quit()
print('✅ Selenium + Chrome fonctionnel')
"

# Copie du code
COPY . .

# Utilisateur non-root
RUN useradd -m railwayuser && chown -R railwayuser:railwayuser /app
USER railwayuser

# Port
EXPOSE 8000

# Démarrage
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]