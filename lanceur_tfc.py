import csv
import time
import requests
import os

FICHIER_CSV = "creditcard.csv"
URL_API = os.getenv("URL_API", "http://fraud_api_gateway:8000/v1/transactions")
HEADERS = {"X-API-Key": "tfc_key_client_8cf90a32"}

if __name__ == "__main__":
    # ÉTAPE 1 : Attente de l'initialisation complète de l'infrastructure Docker
    print("[TFC]  Temporisation de sécurité... Attente de 20 secondes que Kafka et la Gateway soient prêts...")
    time.sleep(20)

    print("[TFC] Extraction et isolation des quotas exacts pour le jury (150 Légitimes vs 100 Fraudes)...")

    lignes_normales = []
    lignes_fraudeuses = []

    try:
        with open(FICHIER_CSV, mode='r') as file:
            reader = csv.DictReader(file)
            for idx, row in enumerate(reader):
                
                # Arrêt immédiat de la lecture dès que les deux quotas distincts sont pleinement atteints
                if len(lignes_normales) == 150 and len(lignes_fraudeuses) == 100:
                    break
                    
                payload = {
                    #  FIX UNICITÉ CRITIQUE : Identifiant unique basé sur la milliseconde d'exécution
                    "id_trans": f"TX_CC_{idx}_{int(time.time() * 1000)}",
                    "tx_time": float(row['Time']),
                    "amount": float(row['Amount']),
                    **{f"v{i}": float(row[f'V{i}']) for i in range(1, 29)}
                }
                
                # Isolement strict selon la classe du jeu de données (Class 1 = Fraude, Class 0 = Légitime)
                if row['Class'] == '1':
                    if len(lignes_fraudeuses) < 100:
                        lignes_fraudeuses.append(payload)
                else:
                    if len(lignes_normales) < 150:
                        lignes_normales.append(payload)
                        
    except FileNotFoundError:
        print(f"[ERREUR] Fichier {FICHIER_CSV} introuvable à la racine du projet.")
        exit(1)

    # Validation de sécurité avant de lancer l'injection réseau
    if len(lignes_normales) < 150 or len(lignes_fraudeuses) < 100:
        print(f"[ATTENTION] Quotas insuffisants dans le CSV. Trouvé : {len(lignes_normales)} normales, {len(lignes_fraudeuses)} fraudes.")
        exit(1)

    print(f"[TFC] Réserve validée : {len(lignes_normales)} normales et {len(lignes_fraudeuses)} fraudes prêtes.")
    print("[TFC]  Lancement de l'injection dynamique en temps réel .")

    idx_norm = 0
    idx_fraud = 0

    try:
        # La boucle s'exécute jusqu'à l'envoi total des 250 payloads
        while idx_norm < len(lignes_normales) or idx_fraud < len(lignes_fraudeuses):
            
            # --- SALVE DE TRANSACTIONS NORMALES (Rythme de 3 transactions) ---
            for _ in range(3):
                if idx_norm < len(lignes_normales):
                    tx = lignes_normales[idx_norm]
                    idx_norm += 1
                    try:
                        response = requests.post(URL_API, json=tx, headers=HEADERS, timeout=5)
                        if response.status_code == 202:
                            print(f"[SIMULATEUR] ({idx_norm + idx_fraud}/250) Transaction normale {tx['id_trans']} -> Envoyée (HTTP 202)")
                    except Exception as e:
                        print(f"[SIMULATEUR ERROR] Erreur envoi normale : {e}")
                    
                    time.sleep(0.4)
            
            # --- INJECTION D'UNE TRANSACTION FRAUDEUSE ---
            if idx_fraud < len(lignes_fraudeuses):
                tx_f = lignes_fraudeuses[idx_fraud]
                idx_fraud += 1
                try:
                    response = requests.post(URL_API, json=tx_f, headers=HEADERS, timeout=5)
                    if response.status_code == 202:
                        print(f"\n [SIMULATEUR] ({idx_norm + idx_fraud}/250) INJECTION FRAUDE NUMÉRO {idx_fraud} : {tx_f['id_trans']} (HTTP 202)\n")
                except Exception as e:
                    print(f"[SIMULATEUR ERROR] Erreur injection fraude : {e}")
                
                time.sleep(0.6)

        print("\n [DÉMONSTRATION TERMINÉE] Le quota exact a été injecté avec succès !")
        print(f"Total Transactions Évaluées : {idx_norm + idx_fraud} | Légitimes : {idx_norm} | Alertes IA : {idx_fraud}")
        print("Le Dashboard est figé à l'état final. Prêt pour les questions du jury. \n")
        
        # Maintien du conteneur en vie pour l'analyse des logs par le jury
        while True:
            time.sleep(3600)

    except KeyboardInterrupt:
        print("\n Simulation interrompue proprement.")
