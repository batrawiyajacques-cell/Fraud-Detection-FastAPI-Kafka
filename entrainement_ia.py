import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib

FICHIER_CSV = "creditcard.csv"

print("[DATA SCIENCE] 1. Chargement du fichier Credit Card (Veuillez patienter)...")
try:
    df = pd.read_csv(FICHIER_CSV)
    print(f"[DATA SCIENCE] Succes ! Nombre de lignes chargees : {len(df)}")
except FileNotFoundError:
    print(f"[ERREUR] Le fichier '{FICHIER_CSV}' est introuvable a la racine.")
    exit(1)

print("[DATA SCIENCE] 2. Preparation des caracteristiques...")
# On separe les variables explicatives (Time, V1 a V28, Amount) de la cible 'Class' (0=Normal, 1=Fraude)
X = df.drop(columns=['Class'])
y = df['Class']

print("[DATA SCIENCE] 3. Division des donnees (70% Entrainement / 30% Test)...")
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)

print("[DATA SCIENCE] 4. Entrainement du modele Random Forest...")
# Configuration equilibree pour un entrainement robuste et ultra-rapide (moins de 30 secondes)
modele_rf = RandomForestClassifier(n_estimators=15, max_depth=12, random_state=42, n_jobs=-1)
modele_rf.fit(X_train, y_train)
print("[DATA SCIENCE] Entrainement termine avec succes !")

print("[DATA SCIENCE] 5. Evaluation des performances du modele...")
y_pred = modele_rf.predict(X_test)
print(f"-> Precision Globale : {accuracy_score(y_test, y_pred) * 100:.2f}%")
print("\n--- Rapport de Classification ---")
print(classification_report(y_test, y_pred))

# ─── AJOUT EXCLUSIF TFC : ANALYSE DES CAS DE FRAUDE VIA L'IMPORTANCE DES VARIABLES ───
print("\n--- Analyse Methodologique de la Fraud-Detection ---")
importances = modele_rf.feature_importances_
features_df = pd.DataFrame({'Variable': X.columns, 'Importance': importances})
features_df = features_df.sort_values(by='Importance', ascending=False).reset_index(drop=True)

print("Top 5 des variables decisives utilisees par l'IA pour classifier la menace :")
for i in range(5):
    print(f"  {i+1}. {features_df.loc[i, 'Variable']} ({features_df.loc[i, 'Importance']*100:.2f}%)")

print("\n[EXPLICATION METIER POUR LE RAPPORT] :")
print("- Si les variables temporelles/profils dominent (ex: V17, V14, Time) : L'IA intercepte les 'Vitesses Impossibles'.")
print("- Si la variable 'Amount' montre un ecart type fort : L'IA discrimine le 'Card Testing' (montants infimes) des 'Achats Flash' (gros montants).")
# ───────────────────────────────────────────────────────────────────────────────────

print("\n[DATA SCIENCE] 6. Exportation du modele...")
joblib.dump(modele_rf, 'mon_modele_ia.joblib')
print("[DATA SCIENCE] Le fichier 'mon_modele_ia.joblib' a ete mis a jour a la racine.")