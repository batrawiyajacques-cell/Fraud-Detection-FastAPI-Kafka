from fastapi import FastAPI, status
from pydantic import BaseModel

app = FastAPI(title="API Reception Client - Banque Partenaire (TFC)")

# Classe de validation mise a jour pour accepter l'integralite du payload du worker
class NotificationPayload(BaseModel):
    id_score: list | int | None
    id_trans: str
    score_valeur: float
    verdict: bool
    type_menace: str                    # <-- Ajouté pour correspondre au worker
    action_requise: str                 # <-- Ajouté pour correspondre au worker
    message: str | None = None

@app.post("/client/webhook", status_code=status.HTTP_200_OK)
async def recevoir_alerte_fraude(notification: NotificationPayload):
    print(f"\n [NOTIFICATION RECUE] Transaction : {notification.id_trans}")
    print(f"➔ Score de risque calculé par l'IA : {notification.score_valeur * 100:.2f}%")
    print(f"➔ Type de menace détecté : {notification.type_menace}")
    
    # Arbre de décision applicatif côté client
    if notification.action_requise == "BLOCK":
        print(" ACTION AUTOMATIQUE : Blocage immédiat de la carte de crédit et gel des fonds.\n")
    elif notification.action_requise == "TRIGGER_OTP":
        print(" ACTION REQUISE : Suspension temporaire. Envoi immédiat d'un code OTP par SMS au client.\n")
    else:
        print(" INFO : Transaction légitime validée.\n")
    
    return {"status": "SUCCESS", "detail": f"Action {notification.action_requise} exécutée avec succès"}