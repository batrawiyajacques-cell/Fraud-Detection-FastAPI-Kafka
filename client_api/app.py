from fastapi import FastAPI, status
from pydantic import BaseModel

app = FastAPI(title="API Reception Client - Banque Partenaire (TFC)")

# Classe de validation corrigee sans aucune erreur de syntaxe
class NotificationPayload(BaseModel):
    id_score: list | int | None
    id_trans: str
    score_valeur: float
    verdict: bool
    message: str | None = None

@app.post("/client/webhook", status_code=status.HTTP_200_OK)
async def recevoir_alerte_fraude(notification: NotificationPayload):
    # Ce point de contact simule la reception des alertes chez le client
    if notification.verdict:
        print(f"\n [ALERTE BANQUE CLIENT] RETRAIT/ACHAT SUSPECT DETECTE : {notification.id_trans}")
        print(f"➔ Score de risque calcule par l'IA : {notification.score_valeur * 100:.2f}%")
        print("➔ Action automatique : Blocage immediat de la carte de credit.\n")
    else:
        print(f" [INFO BANQUE CLIENT] Transaction legitime acceptee : {notification.id_trans} (Risque : {notification.score_valeur * 100:.2f}%)")
    
    return {"status": "SUCCESS", "detail": "Alerte recue et traitee"}
