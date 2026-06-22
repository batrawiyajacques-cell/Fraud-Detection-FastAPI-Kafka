FROM python:3.11-slim

WORKDIR /app

# Installation des dépendances Python (Mise en cache optimale de la couche)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie de l'intégralité du code source du webhook dans le conteneur
COPY . .

# Exposition du port d'écoute configuré dans le docker-compose
EXPOSE 8001

# Lancement du serveur Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]