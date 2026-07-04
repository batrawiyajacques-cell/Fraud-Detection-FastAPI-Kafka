FROM python:3.11-slim

WORKDIR /app

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie de l'intégralité du code source
COPY . .

# Définir le PYTHONPATH pour qu'Uvicorn trouve "app" même s'il est dans un sous-dossier
ENV PYTHONPATH=/app:/app/client_api

# Exposition du port d'écoute
EXPOSE 8001

# Lancement du serveur Uvicorn (avec recherche adaptative du module)
CMD ["uvicorn", "client_api.app:app", "--host", "0.0.0.0", "--port", "8001"]