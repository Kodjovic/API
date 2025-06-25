from fastapi import FastAPI
from bs4 import BeautifulSoup
import requests
import re
from datetime import datetime, timedelta
from typing import List, Dict

app = FastAPI()

# Cache global pour stocker les données
CACHE = {
    "data": [],
    "last_update": None,
    "cache_duration_minutes": 5  # Cache pendant 5 minutes
}

# Session réutilisable pour optimiser les requêtes HTTP
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

# Nettoyage du texte (inchangé)
def nettoyer_texte(texte):
    texte = texte.strip()
    texte = texte.replace("☎", "").replace("â˜Ž", "").replace("Â", "")
    return re.sub(r"\s{2,}", " ", texte)

# Vérifier si le cache est encore valide
def is_cache_valid() -> bool:
    if not CACHE["last_update"]:
        return False
    
    elapsed = datetime.now() - CACHE["last_update"]
    return elapsed.total_seconds() < (CACHE["cache_duration_minutes"] * 60)

# Scraping optimisé avec gestion d'erreurs
def scraper_pharmacies():
    url = "https://www.inam.tg/pharmacies-de-garde/"
    
    try:
        # Utiliser la session avec timeout
        response = session.get(url, timeout=10)
        response.raise_for_status()  # Lève une exception si statut HTTP d'erreur
        
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find('table')
        
        if not table:
            print("Aucune table trouvée sur la page")
            return []
        
        pharmacies = []
        rows = table.find_all('tr')[1:]  # Skip header
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 3:
                nom = nettoyer_texte(cells[0].text)
                tel = nettoyer_texte(cells[1].text)
                adresse = nettoyer_texte(cells[2].text)
                
                if adresse:  # Vérification que l'adresse existe
                    pharmacies.append({
                        "Nom_pharmacie": nom,
                        "Numero_telephone": tel,
                        "Adresse": adresse
                    })
        
        print(f"Scraping réussi: {len(pharmacies)} pharmacies trouvées")
        return pharmacies
        
    except requests.exceptions.RequestException as e:
        print(f"Erreur de requête HTTP: {e}")
        return []
    except Exception as e:
        print(f"Erreur de scraping: {e}")
        return []

# Route d'accueil
@app.get("/")
def home():
    return {
        "message": "Bienvenue sur l'API de pharmacies de garde en ligne 🚑",
        "endpoints": {
            "/pharmacies_de_garde": "Récupérer les pharmacies de garde",
            "/pharmacies_de_garde?force_update=true": "Forcer la mise à jour des données",
            "/status": "Statut du cache et dernière mise à jour"
        }
    }

# Route principale optimisée avec cache
@app.get("/pharmacies_de_garde")
def pharmacies_de_garde(force_update: bool = False):
    """
    Récupère les pharmacies de garde avec cache intelligent
    
    Args:
        force_update (bool): Si True, force la mise à jour même si le cache est valide
    
    Returns:
        dict: Données des pharmacies avec métadonnées
    """
    
    # Si le cache est valide et qu'on ne force pas la mise à jour
    if is_cache_valid() and not force_update and CACHE["data"]:
        return {
            "data": CACHE["data"],
            "metadata": {
                "source": "cache",
                "last_update": CACHE["last_update"].isoformat(),
                "count": len(CACHE["data"]),
                "cache_expires_in_minutes": CACHE["cache_duration_minutes"] - 
                    (datetime.now() - CACHE["last_update"]).total_seconds() / 60
            }
        }
    
    # Sinon, récupérer des données fraîches
    try:
        print("Récupération de nouvelles données...")
        pharmacies = scraper_pharmacies()
        
        if pharmacies:
            # Mettre à jour le cache
            CACHE["data"] = pharmacies
            CACHE["last_update"] = datetime.now()
            
            return {
                "data": pharmacies,
                "metadata": {
                    "source": "fresh_data",
                    "last_update": CACHE["last_update"].isoformat(),
                    "count": len(pharmacies),
                    "cache_duration_minutes": CACHE["cache_duration_minutes"]
                }
            }
        else:
            # Si le scraping échoue mais qu'on a des données en cache
            if CACHE["data"]:
                return {
                    "data": CACHE["data"],
                    "metadata": {
                        "source": "cache_fallback",
                        "last_update": CACHE["last_update"].isoformat() if CACHE["last_update"] else None,
                        "count": len(CACHE["data"]),
                        "warning": "Scraping échoué, données du cache retournées"
                    }
                }
            else:
                return {
                    "data": [],
                    "metadata": {
                        "source": "error",
                        "error": "Impossible de récupérer les données et aucun cache disponible",
                        "count": 0
                    }
                }
                
    except Exception as e:
        # En cas d'erreur, retourner le cache s'il existe
        if CACHE["data"]:
            return {
                "data": CACHE["data"],
                "metadata": {
                    "source": "cache_error_fallback",
                    "last_update": CACHE["last_update"].isoformat() if CACHE["last_update"] else None,
                    "count": len(CACHE["data"]),
                    "error": f"Erreur: {str(e)}"
                }
            }
        else:
            return {
                "data": [],
                "metadata": {
                    "source": "error",
                    "error": str(e),
                    "count": 0
                }
            }

# Route pour obtenir le statut du cache
@app.get("/status")
def get_status():
    """Retourne le statut du cache et des données"""
    return {
        "cache_status": {
            "is_cache_valid": is_cache_valid(),
            "last_update": CACHE["last_update"].isoformat() if CACHE["last_update"] else None,
            "cached_pharmacies_count": len(CACHE["data"]),
            "cache_duration_minutes": CACHE["cache_duration_minutes"]
        },
        "next_update_in_minutes": max(0, CACHE["cache_duration_minutes"] - 
            (datetime.now() - CACHE["last_update"]).total_seconds() / 60) if CACHE["last_update"] else 0
    }

# Route pour vider le cache (utile pour les tests)
@app.delete("/cache")
def clear_cache():
    """Vide le cache pour forcer la prochaine mise à jour"""
    CACHE["data"] = []
    CACHE["last_update"] = None
    return {"message": "Cache vidé avec succès"}

# Pré-chargement des données au démarrage de l'API
@app.on_event("startup")
async def startup_event():
    """Pré-charge les données au démarrage pour une première requête rapide"""
    print("🚀 Démarrage de l'API - Pré-chargement des données...")
    try:
        pharmacies = scraper_pharmacies()
        if pharmacies:
            CACHE["data"] = pharmacies
            CACHE["last_update"] = datetime.now()
            print(f"✅ Cache initialisé avec {len(pharmacies)} pharmacies")
        else:
            print("⚠️  Aucune donnée récupérée au démarrage")
    except Exception as e:
        print(f"❌ Erreur lors du pré-chargement: {e}")
