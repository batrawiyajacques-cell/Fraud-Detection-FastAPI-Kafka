FROM python:3.11-slim

# Installation des paquets système nécessaires à la compilation de psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copie et installation des dépendances Python à la racine de l'application
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du dossier ml_consumer vers /app/ml_consumer
COPY ./ml_consumer/ /app/ml_consumer/

# Déplacement de l'exécution dans le bon répertoire pour que python trouve worker.py et le modèle .joblib
WORKDIR /app/ml_consumer

# Démarrage direct de votre worker IA
CMD ["python", "worker.py"]