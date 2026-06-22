FROM python:3.11-slim

# Installation des dépendances système requises pour psycopg2 (compilation du driver PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copie et installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du dossier api_gateway dans le conteneur
COPY ./api_gateway/ /app/api_gateway/

EXPOSE 8000

# Lancement de l'application via Uvicorn
CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]