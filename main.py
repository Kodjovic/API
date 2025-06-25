from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import json
import os

app = FastAPI()

# ✅ Modèle des données attendues
class Pharmacie(BaseModel):
    Nom_pharmacie: str
    Numero_telephone: str
    Adresse: str

# ✅ Page d'accueil
@app.get("/")
def home():
    return {"message": "Bienvenue sur l'API des pharmacies de garde 🚑"}

# ✅ Endpoint pour recevoir les pharmacies (appelé par ton script local)
@app.post("/upload_pharmacies")
def upload_pharmacies(pharmacies: List[Pharmacie]):
    try:
        with open("pharmacies_cache.json", "w", encoding="utf-8") as f:
            json.dump([ph.dict() for ph in pharmacies], f, ensure_ascii=False, indent=2)
        return {"message": f"{len(pharmacies)} pharmacies reçues avec succès"}
    except Exception as e:
        return {"error": str(e)}

# ✅ Endpoint pour fournir les pharmacies (appelé par WordPress)
@app.get("/pharmacies_de_garde")
def get_pharmacies():
    if os.path.exists("pharmacies_cache.json"):
        with open("pharmacies_cache.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {"error": "Aucune donnée disponible"}
