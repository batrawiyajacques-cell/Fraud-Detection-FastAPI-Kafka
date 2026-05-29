import json
import time
import requests
import psycopg2
import joblib
import pandas as pd
import os
from kafka import KafkaConsumer

# --- CONFIGURATION RÉSEAU DOCKER DYNAMIQUE ---
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_BOOTSTRAP_SERVERS = [KAFKA_BROKER]
KAFKA_TOPICS = ['Topic_Premium', 'Topic_Standard']

# Extraction des variables d'environnement de la base de données
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "tfc_fraud_db")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "MonSuperPassword2026")

DB_URI = f"dbname={DB_NAME} user={DB_USER} password={DB_PASS} host={DB_HOST} port=5432"

# SEUILS LOGIQUES APPLICATIFS (Gestion de la Zone Grise)
SEUIL_CRITIQUE_FRAUDE = 0.75  # Au-dessus : Bloqué direct (Achat Flash / Vitesse Impossible)
SEUIL_ZONE_GRISE = 0.40       # Entre 0.40 et 0.75 : Zone suspecte nécessitant un OTP/SMS
URL_NOTIFICATION_CLIENT = "http://client_webhook:8001/client/webhook" # Redirection vers le bon webhook Docker

print("[ML-CONSUMER] Chargement du VRAI modele Random Forest (Credit Card)...")
try:
    modele_ia = joblib.load('mon_modele_ia.joblib')
    print("[ML-CONSUMER] Succes ! Modele IA operationnel et pret.")
except Exception as e:
    print(f"[ERREUR] Chargement .joblib impossible : {e}")
    exit(1)

try:
    consumer = KafkaConsumer(
        *KAFKA_TOPICS,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset='latest',
        enable_auto_commit=True,
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    print(f"[ML-CONSUMER] Connecte aux canaux Kafka : {KAFKA_TOPICS}")
except Exception as e:
    print(f"[ERREUR KAFKA] Liaison impossible : {e}")
    exit(1)

for message in consumer:
    transaction = message.value
    id_transaction = transaction['id_trans']
    montant = float(transaction['amount'])
    
    print(f"\n[ANALYSE] Transaction interceptee : {id_transaction}")
    
    # Alignement rigoureux des colonnes avec l'apprentissage du modele
    donnees_ia = {}
    for col in modele_ia.feature_names_in_:
        if col == "Time":
            donnees_ia["Time"] = float(transaction["tx_time"])
        elif col == "Amount":
            donnees_ia["Amount"] = montant
        else:
            donnees_ia[col] = float(transaction[col.lower()])
            
    df_input = pd.DataFrame([donnees_ia])
    
    # Calcul de la probabilite reelle de fraude par l'IA
    probabilites = modele_ia.predict_proba(df_input)
    score_risque = float(probabilites[0, 1]) 
    
    # ─── EXTRACTION DE LA LOGIQUE ET DU TYPE DE MENACE ───
    verdict_final = score_risque >= SEUIL_ZONE_GRISE  # Suspect dès qu'on entre en zone grise
    
    # Qualification métier par arbre de décision applicatif (Post-Inférence)
    type_menace = "LOG_TRANSACTION_LEGITIME"
    action_banque = "ALLOW"  # Comportement par défaut
    niveau_log = "INFO"

    if score_risque >= SEUIL_CRITIQUE_FRAUDE:
        action_banque = "BLOCK"
        niveau_log = "ERROR"
        # Distinction sémantique selon le montant
        if montant < 5.0:
            type_menace = "FRAUDE_CARD_TESTING_AVANCEE"
        else:
            type_menace = "FRAUDE_ACHAT_FLASH_USURPATION"
            
    elif SEUIL_ZONE_GRISE <= score_risque < SEUIL_CRITIQUE_FRAUDE:
        action_banque = "TRIGGER_OTP"  # Demande d'envoi de SMS/OTP à la banque
        niveau_log = "WARNING"
        type_menace = "SUSPICION_VITESSE_IMPOSSIBLE_OU_PROXY"

    print(f"[VRAIE IA VERDICT] Risque : {score_risque * 100:.2f}% | Menace : {type_menace} | Action : {action_banque}")
    
    # 1. Persistance SQL securisee (Conforme MLD)
    conn = None
    id_score_genere = None
    try:
        conn = psycopg2.connect(DB_URI)
        cursor = conn.cursor()
        
        query_trans = """
            INSERT INTO TRANSACTION (id_trans, id_client, tx_time, amount, 
            v1, v2, v3, v4, v5, v6, v7, v8, v9, v10, v11, v12, v13, v14, v15, 
            v16, v17, v18, v19, v20, v21, v22, v23, v24, v25, v26, v27, v28)
            VALUES (%s, %s, %s, %s, %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id_trans) DO NOTHING;
        """
        cursor.execute(query_trans, (
            id_transaction, transaction['id_client'], transaction['tx_time'], transaction['amount'],
            transaction['v1'], transaction['v2'], transaction['v3'], transaction['v4'], transaction['v5'],
            transaction['v6'], transaction['v7'], transaction['v8'], transaction['v9'], transaction['v10'],
            transaction['v11'], transaction['v12'], transaction['v13'], transaction['v14'], transaction['v15'],
            transaction['v16'], transaction['v17'], transaction['v18'], transaction['v19'], transaction['v20'],
            transaction['v21'], transaction['v22'], transaction['v23'], transaction['v24'], transaction['v25'],
            transaction['v26'], transaction['v27'], transaction['v28']
        ))
        
        query_score = """
            INSERT INTO RESULTAT_STORE (id_trans, id_detector, score_valeur, verdict)
            VALUES (%s, 1, %s, %s)
            ON CONFLICT (id_trans) DO UPDATE 
            SET score_valeur = EXCLUDED.score_valeur, verdict = EXCLUDED.verdict
            RETURNING id_score;
        """
        cursor.execute(query_score, (id_transaction, score_risque, verdict_final))
        id_score_genere = cursor.fetchone()[0]
        
        # Injection du vrai type de menace dans l'historique d'audit pour Streamlit
        query_audit = """
            INSERT INTO AUDIT_LOGGER (id_trans, action, niveau, latence_ms)
            VALUES (%s, %s, %s, 4) ON CONFLICT DO NOTHING;
        """
        cursor.execute(query_audit, (id_transaction, type_menace, niveau_log))
        conn.commit()
        cursor.close()
        print(f"[DATABASE SUCCESS] Verdict et type de menace synchronises (ID Score: {id_score_genere})")
    except Exception as db_error:
        print(f"[DATABASE ERROR] SQL Error : {db_error}")
        if conn: conn.rollback()
        continue
    finally:
        if conn: conn.close()

    # 2. DECLENCHEMENT DU WEBHOOK AVEC INSTRUCTION APPLICATIVE (OTP/BLOCK/ALLOW)
    statut_livraison = "FAILED"
    payload_notification = {
        "id_score": int(id_score_genere) if id_score_genere else None,
        "id_trans": str(id_transaction),
        "score_valeur": float(score_risque),
        "verdict": bool(verdict_final),
        "type_menace": type_menace,
        "action_requise": action_banque,  # BLOCK, TRIGGER_OTP, ou ALLOW
        "message": f"ALERTE : MODE {action_banque} INITIALISE POUR {type_menace}"
    }
    
    try:
        response = requests.post(URL_NOTIFICATION_CLIENT, json=payload_notification, timeout=3)
        if response.status_code == 200:
            statut_livraison = "SUCCESS"
            print(f"[WEBHOOK] Payload d'action {action_banque} transmis au point d'ecoute client.")
    except requests.exceptions.RequestException:
        print(f"[WEBHOOK WARNING] Client bancaire hors-ligne pour la transaction {id_transaction}")

    # Enregistrement de la tracabilite
    try:
        conn = psycopg2.connect(DB_URI)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO NOTIFICATION (id_score, webhook_url, statut_livraison)
            VALUES (%s, %s, %s)
            ON CONFLICT (id_score) DO UPDATE SET statut_livraison = EXCLUDED.statut_livraison;
        """, (id_score_genere, URL_NOTIFICATION_CLIENT, statut_livraison))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as n_error:
        print(f"[DATABASE ERROR] Echec de mise a jour du registre de notification : {n_error}")
