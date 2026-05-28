import json
import os
import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from kafka import KafkaProducer

# Charger les variables d'environnement depuis le fichier .env local
load_dotenv()

app = FastAPI(title="API Gateway Sécurisée - Credit Card Fraud TFC")

# Récupération sécurisée des configurations (avec valeurs par défaut locales)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "tfc_fraud_db")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS")  # Chargé depuis le fichier .env

DB_URI = f"dbname={DB_NAME} user={DB_USER} password={DB_PASS} host={DB_HOST} port=5432"

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

# Initialisation sécurisée du producteur Kafka
try:
    KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
    producer = KafkaProducer(
        bootstrap_servers=[KAFKA_BROKER],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    print(f"[KAFKA] Producteur connecté avec succès sur {KAFKA_BROKER}")
except Exception as e:
    print(f"[KAFKA ERROR] Connexion au Broker impossible : {e}")
    producer = None

# Schéma Pydantic pour la validation stricte des données d'entrée (MLD)
class CreditCardPayload(BaseModel):
    id_trans: str = Field(..., example="TX_CC_001")
    tx_time: float = Field(..., example=0.0)
    amount: float = Field(..., gt=0, example=149.99)
    v1: float; v2: float; v3: float; v4: float; v5: float
    v6: float; v7: float; v8: float; v9: float; v10: float
    v11: float; v12: float; v13: float; v14: float; v15: float
    v16: float; v17: float; v18: float; v19: float; v20: float
    v21: float; v22: float; v23: float; v24: float; v25: float
    v26: float; v27: float; v28: float

def verifier_authentification_et_role(api_key: str) -> str:
    """
    Vérifie la clé API dans PostgreSQL et retourne le rôle du client (QoS).
    Les connexions et curseurs sont fermés explicitement pour éviter les fuites de ressources.
    """
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(DB_URI)
        cursor = conn.cursor()
        
        # Requête paramétrée pour bloquer les injections SQL
        cursor.execute("SELECT role FROM UTILISATEUR WHERE api_key = %s;", (api_key,))
        result = cursor.fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Clé API invalide ou accès refusé."
            )
        return result[0]
        
    except psycopg2.DatabaseError as e:
        print(f"[DB ERROR] Erreur lors de la vérification : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Une erreur interne est survenue lors de l'authentification."
        )
    finally:
        # Sécurité : On s'assure de libérer les connexions dans tous les scénarios
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.post("/v1/transactions", status_code=status.HTTP_202_ACCEPTED)
async def recevoir_transaction(transaction: CreditCardPayload, api_key: str = Security(api_key_header)):
    """
    Point de terminaison principal (Endpoint) pour recevoir les transactions des banques.
    Identifie le rôle du partenaire et aiguille le payload vers le bon Topic Kafka.
    """
    # 1. Authentification et récupération du rôle (Standard ou Premium)
    role_client = verifier_authentification_et_role(api_key)
    
    # 2. Routage dynamique basé sur la classe de service
    topic_destination = "Topic_Premium" if role_client == "Premium" else "Topic_Standard"
    
    # 3. Validation de la disponibilité de Kafka avant l'envoi
    if not producer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Le service de streaming Kafka est temporairement indisponible."
        )
        
    try:
        # 4. Préparation et enrichissement du payload
        payload = transaction.model_dump()
        payload["id_client"] = 1 if role_client == "Premium" else 2
        
        # 5. Envoi asynchrone dans le bus de messages
        producer.send(topic_destination, value=payload)
        producer.flush() # Force la transmission immédiate
        
    except Exception as e:
        print(f"[KAFKA PUSH ERROR] Échec d'envoi de l'événement : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Impossible d'enregistrer la transaction dans le pipeline."
        )
        
    return {
        "status": "Transaction Reçue et Enregistrée",
        "id_trans": transaction.id_trans,
        "pipeline_affecte": topic_destination
    }