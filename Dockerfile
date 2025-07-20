FROM python:3.11-slim

WORKDIR /app

# Dépendances minimales
RUN pip install fastapi uvicorn

# Copie des fichiers
COPY main_minimal.py main.py
COPY start.py start.py

# Variables d'environnement
ENV PYTHONUNBUFFERED=1

# Port
EXPOSE 8000

# Utilise le script de démarrage Python qui gère PORT
CMD ["python", "start.py"]