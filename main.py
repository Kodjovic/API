from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import json
import os
import httpx  # ← AJOUT : pour appeler WordPress
from datetime import datetime

app = FastAPI()

# ✅ Configuration WordPress (à modifier avec votre URL)
WORDPRESS_WEBHOOK_URL = "https://votresite.com/wp-json/pharmacies/v1/update"

# ✅ Modèle des données
class Pharmacie(BaseModel):
    Nom_pharmacie: str
    Numero_telephone: str
    Adresse: str
    url: str

# ✅ Page d'accueil
@app.get("/")
def home():
    return {
        "message": "API des pharmacies de garde 🚑",
        "endpoints": {
            "upload": "/upload_pharmacies",
            "get": "/pharmacies_de_garde"
        }
    }

# ✅ Endpoint pour recevoir les pharmacies (appelé par ton script local)
@app.post("/upload_pharmacies")
async def upload_pharmacies(pharmacies: List[Pharmacie]):
    try:
        print(f"📥 Réception de {len(pharmacies)} pharmacies à {datetime.now()}")
        
        # 1️⃣ Sauvegarder les données dans le fichier JSON
        pharmacies_data = [ph.dict() for ph in pharmacies]
        
        with open("pharmacies_cache.json", "w", encoding="utf-8") as f:
            json.dump(pharmacies_data, f, ensure_ascii=False, indent=2)
        
        print("✅ Pharmacies sauvegardées dans pharmacies_cache.json")
        
        # 2️⃣ Notifier WordPress automatiquement
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    WORDPRESS_WEBHOOK_URL,
                    json={"action": "update", "count": len(pharmacies)}
                )
                
                if response.status_code == 200:
                    print(f"✅ WordPress notifié avec succès: {response.json()}")
                else:
                    print(f"⚠️ WordPress a répondu avec le code {response.status_code}")
        
        except Exception as webhook_error:
            print(f"⚠️ Échec de notification WordPress: {webhook_error}")
            # On continue quand même (les données sont sauvegardées)
        
        return {
            "success": True,
            "message": f"{len(pharmacies)} pharmacies reçues et sauvegardées",
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        return {"success": False, "error": str(e)}

# ✅ Endpoint pour fournir les pharmacies (appelé par WordPress)
@app.get("/pharmacies_de_garde")
def get_pharmacies():
    try:
        if os.path.exists("pharmacies_cache.json"):
            with open("pharmacies_cache.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"📤 Envoi de {len(data)} pharmacies à WordPress")
                return {
                    "success": True,
                    "count": len(data),
                    "pharmacies": data
                }
        else:
            print("⚠️ Fichier pharmacies_cache.json non trouvé")
            return {"success": False, "error": "Aucune donnée disponible"}
    
    except Exception as e:
        print(f"❌ Erreur lors de la lecture: {e}")
        return {"success": False, "error": str(e)}
