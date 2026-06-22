from fastapi import FastAPI, status
from pydantic import BaseModel

app = FastAPI(title="API Reception Client - Banque Partenaire (TFC)")

# Classe de validation mise à jour pour accepter l'intégralité du payload du worker
class NotificationPayload(BaseModel):
    id_score: int | str | None = None
    id_trans: str
    score_valeur: float | None = 0.0
    verdict: bool
    type_menace: str                    # Conforme au Worker unifié
    action_requise: str                 # Conforme au Worker unifié
    message: str | None = None

@app.post("/client/webhook", status_code=status.HTTP_200_OK)
async def recevoir_alerte_fraude(notification: NotificationPayload):
    print(f"\n [NOTIFICATION REÇUE] Transaction : {notification.id_trans}")
    
    # Sécurisation du calcul de score
    score_pourcent = (notification.score_valeur * 100) if notification.score_valeur is not None else 0.0
    print(f"➔ Score de risque calculé par l'IA : {score_pourcent:.2f}%")
    print(f"➔ Type de menace détecté : {notification.type_menace}")
    
    # Arbre de décision applicatif côté client (Banque Partenaire)
    if notification.action_requise == "BLOCK":
        print(" ACTION AUTOMATIQUE : Blocage immédiat de la carte de crédit et gel des fonds.\n")
    elif notification.action_requise == "TRIGGER_OTP":
        print(" ACTION REQUISE : Suspension temporaire. Envoi immédiat d'un code OTP par SMS au client.\n")
    else:
        print(" INFO : Transaction légitime validée.\n")
    
    return {
        "status": "SUCCESS", 
        "detail": f"Action {notification.action_requise} exécutée avec succès"
    }