from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import json
import os

app = FastAPI()

# ✅ Modèle des données attendues (MIS À JOUR)
class Pharmacie(BaseModel):
    Nom_pharmacie: str
    Numero_telephone: str
    Adresse: str
    url: str  # ← AJOUTÉ : champ url obligatoire

# ✅ Page d'accueil
@app.get("/")
def home():
    return {"message": "Bienvenue sur l'API des pharmacies de garde 🚑"}

# ✅ Endpoint pour recevoir les pharmacies (appelé par ton script local)
@app.post("/upload_pharmacies")
def upload_pharmacies(pharmacies: List[Pharmacie]):
    try:
        print(f"📥 Réception de {len(pharmacies)} pharmacies")
        
        # Debug : afficher les données reçues
        for i, ph in enumerate(pharmacies[:3]):  # Affiche les 3 premières
            print(f"  {i+1}. {ph.Nom_pharmacie} - URL: {ph.url}")
        
        with open("pharmacies_cache.json", "w", encoding="utf-8") as f:
            json.dump([ph.dict() for ph in pharmacies], f, ensure_ascii=False, indent=2)
        
        print("✅ Pharmacies sauvegardées avec succès")
        return {"message": f"{len(pharmacies)} pharmacies reçues avec succès"}
    
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        return {"error": str(e)}

# ✅ Endpoint pour fournir les pharmacies (appelé par WordPress)
@app.get("/pharmacies_de_garde")
def get_pharmacies():
    try:
        if os.path.exists("pharmacies_cache.json"):
            with open("pharmacies_cache.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"📤 Envoi de {len(data)} pharmacies")
                return data
        else:
            print("⚠️ Fichier pharmacies_cache.json non trouvé")
            return {"error": "Aucune donnée disponible"}
    except Exception as e:
        print(f"❌ Erreur lors de la lecture: {e}")
        return {"error": str(e)}
