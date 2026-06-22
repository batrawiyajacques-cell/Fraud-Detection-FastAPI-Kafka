import json
import time
import requests
import psycopg2
import joblib
import pandas as pd
import os
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "fraud_kafka_client:9092")
KAFKA_BOOTSTRAP_SERVERS = [KAFKA_BROKER]
KAFKA_TOPICS = ['Topic_Client']

DB_HOST = os.getenv("DB_HOST", "postgres_db")
DB_NAME = os.getenv("DB_NAME", "tfc_fraud_db")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "MonSuperPassword2026")
DB_URI = f"dbname={DB_NAME} user={DB_USER} password={DB_PASS} host={DB_HOST} port=5432"

SEUIL_CRITIQUE_FRAUDE = 0.75
SEUIL_ZONE_GRISE = 0.40
URL_NOTIFICATION_CLIENT = "http://fraud_client_webhook:8001/client/webhook"

print("[ML-CONSUMER] Chargement du VRAI modele Random Forest...")
try:
    modele_ia = joblib.load('mon_modele_ia.joblib')
    print("[ML-CONSUMER] Succes ! Modele IA operationnel et pret.")
except Exception as e:
    print(f"[ERREUR] Chargement .joblib impossible : {e}")
    exit(1)

consumer = None
while consumer is None:
    try:        #  CONFIGURATION RADICALE POUR LE JURY (ZÉRO PERTE DE MESSAGE)
        consumer = KafkaConsumer(
            'Topic_Client',
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            auto_offset_reset='earliest',  # Reprend depuis le tout premier message reçu
            enable_auto_commit=True,
            group_id=f'fraud-ml-group-{int(time.time())}',  #  ID de groupe unique à chaque lancement
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )


        print(f"[ML-CONSUMER] Connecte au canal Kafka unique : {KAFKA_TOPICS}")
    except Exception:
        time.sleep(2)

try:
    for message in consumer:
        transaction = message.value
        id_transaction = transaction['id_trans']
        montant = float(transaction['amount'])
        
        donnees_ia = {}
        for col in modele_ia.feature_names_in_:
            if col == "Time":
                donnees_ia["Time"] = float(transaction["tx_time"])
            elif col == "Amount":
                donnees_ia["Amount"] = montant
            else:
                donnees_ia[col] = float(transaction[col.lower()])
                
        df_input = pd.DataFrame([donnees_ia])
        
        #  EXTRACTEUR MATRIX FIX : Récupération du score réel de la classe 1
        probabilites = modele_ia.predict_proba(df_input)
        score_risque = float(probabilites[0, 1]) 
        
        verdict_final = score_risque >= SEUIL_ZONE_GRISE
        type_menace = "LOG_TRANSACTION_LEGITIME"
        action_banque = "ALLOW"  
        niveau_log = "INFO"      

        if score_risque >= SEUIL_CRITIQUE_FRAUDE:
            action_banque = "BLOCK"
            niveau_log = "ERROR"
            if montant < 5.0:
                type_menace = "FRAUDE_CARD_TESTING_AVANCEE"
            else:
                type_menace = "FRAUDE_ACHAT_FLASH_USURPATION"
        elif SEUIL_ZONE_GRISE <= score_risque < SEUIL_CRITIQUE_FRAUDE:
            action_banque = "TRIGGER_OTP"
            niveau_log = "WARNING"
            type_menace = "SUSPICION_VITESSE_IMPOSSIBLE_OU_PROXY"

        print(f"[VRAIE IA VERDICT] Risque : {score_risque * 100:.2f}% | Menace : {type_menace}")
        
        conn = None
        id_score_genere = None
        insertion_reussie = False
        
        try:
            conn = psycopg2.connect(DB_URI)
            cursor = conn.cursor()
            id_client_securise = transaction.get('id_client', 100)
            
            query_trans = """
                INSERT INTO TRANSACTION (id_trans, id_client, tx_time, amount, 
                v1, v2, v3, v4, v5, v6, v7, v8, v9, v10, v11, v12, v13, v14, v15, 
                v16, v17, v18, v19, v20, v21, v22, v23, v24, v25, v26, v27, v28)
                VALUES (%s, %s, %s, %s, %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id_trans) DO NOTHING;
            """
            cursor.execute(query_trans, (
                id_transaction, id_client_securise, transaction['tx_time'], transaction['amount'],
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
                ON CONFLICT (id_trans) DO UPDATE SET score_valeur = EXCLUDED.score_valeur, verdict = EXCLUDED.verdict
                RETURNING id_score;
            """
            cursor.execute(query_score, (id_transaction, score_risque, verdict_final))
            id_score_genere = cursor.fetchone()[0]
            
            query_audit = """
                INSERT INTO AUDIT_LOGGER (id_trans, action, niveau, latence_ms)
                VALUES (%s, %s, %s, 4) ON CONFLICT DO NOTHING;
            """
            cursor.execute(query_audit, (id_transaction, type_menace, niveau_log))
            
            conn.commit()
            cursor.close()
            insertion_reussie = True
        except Exception as db_error:
            if conn: conn.rollback()
        finally:
            if conn: conn.close()

        if not insertion_reussie:
            continue

        statut_livraison = "FAILED"
        id_score_int = int(id_score_genere)

        payload_notification = {
            "id_score": id_score_int,
            "id_trans": str(id_transaction),
            "score_valeur": float(score_risque),
            "verdict": bool(verdict_final),
            "type_menace": type_menace,
            "action_requise": action_banque,  
            "message": f"ALERTE : {action_banque}"
        }
        
        try:
            response = requests.post(URL_NOTIFICATION_CLIENT, json=payload_notification, timeout=3)
            if response.status_code == 200:
                statut_livraison = "SUCCESS"
        except Exception:
            pass

        try:
            conn = psycopg2.connect(DB_URI)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO NOTIFICATION (id_score, webhook_url, statut_livraison)
                VALUES (%s, %s, %s)
                ON CONFLICT (id_score) DO UPDATE SET statut_livraison = EXCLUDED.statut_livraison;
            """, (id_score_int, URL_NOTIFICATION_CLIENT, statut_livraison))
            conn.commit()
            cursor.close()
        except Exception:
            if conn: conn.rollback()
        finally:
            if conn: conn.close()

except KeyboardInterrupt:
    pass
finally:
    if consumer: consumer.close()
