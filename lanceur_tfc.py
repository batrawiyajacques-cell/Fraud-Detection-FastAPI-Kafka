import csv
import time
import requests

FICHIER_CSV = "creditcard.csv"
URL_API = "http://localhost:8000/v1/transactions"
HEADERS = {"X-API-Key": "tfc_key_premium_8cf90a32"}

print("[TFC] Separation et preparation des lignes (Normales vs Fraudes)...")

lignes_normales = []
lignes_fraudeuses = []

try:
    with open(FICHIER_CSV, mode='r') as file:
        reader = csv.DictReader(file)
        for idx, row in enumerate(reader):
            # Construction du payload adapté aux microservices
            payload = {
                "id_trans": f"TX_CC_{idx}_{row['Time']}",
                "tx_time": float(row['Time']),
                "amount": float(row['Amount']),
                **{f"v{i}": float(row[f'V{i}']) for i in range(1, 29)}
            }
            
            if row['Class'] == '1':
                lignes_fraudeuses.append(payload)
            else:
                if len(lignes_normales) < 200:
                    lignes_normales.append(payload)
                    
            if len(lignes_fraudeuses) >= 40:
                break
except FileNotFoundError:
    print("[ERREUR] Fichier creditcard.csv introuvable à la racine du projet.")
    exit(1)

print(f"[TFC] Preparation terminee. {len(lignes_normales)} normales et {len(lignes_fraudeuses)} fraudes chargees.")
print("[TFC] Lancement de la simulation mixte en boucle continue...")

try:
    while True: # Boucle infinie pour la démonstration devant le jury
        idx_norm = 0
        idx_fraud = 0 # <-- Corrigé : Réinitialisation à 0 ici pour inclure les fraudes à chaque nouveau cycle
        
        while idx_norm < len(lignes_normales):
            # Envoi de 5 transactions normales
            for _ in range(5):
                if idx_norm >= len(lignes_normales): 
                    break
                tx = lignes_normales[idx_norm]
                idx_norm += 1
                try:
                    requests.post(URL_API, json=tx, headers=HEADERS, timeout=5)
                    print(f"[SIMULATEUR] Envoi transaction normale {tx['id_trans']}")
                except Exception as e:
                    print(f"[SIMULATEUR ERROR] API indisponible pour la transaction normale.")
                time.sleep(1)
                
            # Envoi de 1 vraie fraude garantie
            if idx_fraud < len(lignes_fraudeuses):
                tx_f = lignes_fraudeuses[idx_fraud]
                idx_fraud += 1
                try:
                    requests.post(URL_API, json=tx_f, headers=HEADERS, timeout=5)
                    print(f"\n⚡ [SIMULATEUR] INJECTION D'ONE VRAIE FRAUDE REELLE : {tx_f['id_trans']} ⚠️\n")
                except Exception as e:
                    print(f"[SIMULATEUR ERROR] API indisponible pour l'injection de la fraude.")
                time.sleep(1)
        
        print("\n [SIMULATEUR] Fin de l'échantillon complet. Redémarrage du flux au début pour le jury...\n")
        time.sleep(2)

except KeyboardInterrupt:
    print("\n Simulation interrompue proprement par l'utilisateur.")