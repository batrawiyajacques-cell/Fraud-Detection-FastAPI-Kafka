FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# On force Python à s'exécuter à l'emplacement des scripts du consommateur IA
WORKDIR /app/ml_consumer

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copie de vos scripts et du fichier .joblib dans le dossier courant
COPY ./ml_consumer/ .

# Démarrage direct de votre worker IA
CMD ["python", "worker.py"]
