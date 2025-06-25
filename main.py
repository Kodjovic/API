from fastapi import FastAPI, BackgroundTasks
from bs4 import BeautifulSoup
import requests
import re
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
from contextlib import asynccontextmanager

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache global pour stocker les données
CACHE = {
    "data": [],
    "last_update": None,
    "cache_duration_minutes": 30,  # Augmenté à 30 minutes
    "is_updating": False  # Flag pour éviter les requêtes multiples
}

# Configuration des requêtes
REQUEST_CONFIG = {
    'timeout': aiohttp.ClientTimeout(total=15, connect=5),
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
}

def nettoyer_texte(texte: str) -> str:
    """Nettoie et normalise le texte"""
    if not texte:
        return ""
    
    texte = texte.strip()
    texte = texte.replace("☎", "").replace("â˜Ž", "").replace("Â", "")
    texte = re.sub(r"\s{2,}", " ", texte)
    texte = re.sub(r"[^\w\s\-\+\(\)\.\/,]", "", texte)
    return texte

def is_cache_valid() -> bool:
    """Vérifie si le cache est encore valide"""
    if not CACHE["last_update"] or not CACHE["data"]:
        return False
    
    elapsed = datetime.now() - CACHE["last_update"]
    return elapsed.total_seconds() < (CACHE["cache_duration_minutes"] * 60)

async def scraper_pharmacies_async() -> List[Dict]:
    """Scraping asynchrone des pharmacies"""
    url = "https://www.inam.tg/pharmacies-de-garde/"
    
    try:
        async with aiohttp.ClientSession(timeout=REQUEST_CONFIG['timeout']) as session:
            logger.info(f"Tentative de scraping: {url}")
            
            async with session.get(url, headers=REQUEST_CONFIG['headers']) as response:
                if response.status != 200:
                    logger.error(f"Erreur HTTP {response.status}")
                    return []
                
                html_content = await response.text()
                logger.info(f"Contenu HTML récupéré ({len(html_content)} caractères)")
                
        # Parsing avec BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Recherche de table avec plusieurs stratégies
        table = soup.find('table')
        if not table:
            # Stratégie alternative - chercher par classe ou ID
            table = soup.find('div', class_='pharmacies') or soup.find('div', id='pharmacies')
            if not table:
                logger.warning("Aucune table trouvée, structure de page peut-être changée")
                return []
        
        pharmacies = []
        
        # Traitement des données
        if table.name == 'table':
            rows = table.find_all('tr')[1:]  # Skip header
        else:
            rows = table.find_all('div', class_='pharmacy-row') if table else []
        
        logger.info(f"Trouvé {len(rows)} lignes à traiter")
        
        for i, row in enumerate(rows):
            try:
                if table.name == 'table':
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        nom = nettoyer_texte(cells[0].get_text())
                        tel = nettoyer_texte(cells[1].get_text())
                        adresse = nettoyer_texte(cells[2].get_text())
                else:
                    # Stratégie alternative pour d'autres structures
                    nom = nettoyer_texte(row.find(class_='nom').get_text() if row.find(class_='nom') else "")
                    tel = nettoyer_texte(row.find(class_='tel').get_text() if row.find(class_='tel') else "")
                    adresse = nettoyer_texte(row.find(class_='adresse').get_text() if row.find(class_='adresse') else "")
                
                if nom and adresse:  # Validation minimale
                    pharmacies.append({
                        "Nom_pharmacie": nom,
                        "Numero_telephone": tel,
                        "Adresse": adresse
                    })
                    
            except Exception as e:
                logger.warning(f"Erreur lors du traitement de la ligne {i}: {e}")
                continue
        
        logger.info(f"Scraping réussi: {len(pharmacies)} pharmacies trouvées")
        return pharmacies
        
    except asyncio.TimeoutError:
        logger.error("Timeout lors du scraping")
        return []
    except Exception as e:
        logger.error(f"Erreur de scraping: {e}")
        return []

async def update_cache_background():
    """Met à jour le cache en arrière-plan"""
    if CACHE["is_updating"]:
        logger.info("Mise à jour déjà en cours, ignorée")
        return
    
    CACHE["is_updating"] = True
    try:
        pharmacies = await scraper_pharmacies_async()
        if pharmacies:
            CACHE["data"] = pharmacies
            CACHE["last_update"] = datetime.now()
            logger.info(f"Cache mis à jour avec {len(pharmacies)} pharmacies")
        else:
            logger.warning("Aucune donnée récupérée lors de la mise à jour")
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du cache: {e}")
    finally:
        CACHE["is_updating"] = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Démarrage de l'API - Pré-chargement des données...")
    await update_cache_background()
    
    # Démarrage d'une tâche de mise à jour périodique
    async def periodic_update():
        while True:
            await asyncio.sleep(CACHE["cache_duration_minutes"] * 60)
            if not is_cache_valid():
                await update_cache_background()
    
    task = asyncio.create_task(periodic_update())
    
    yield
    
    # Shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

@app.get("/")
def home():
    return {
        "message": "API de pharmacies de garde en ligne 🚑",
        "status": "active",
        "endpoints": {
            "/pharmacies_de_garde": "Récupérer les pharmacies de garde",
            "/pharmacies_de_garde?force_update=true": "Forcer la mise à jour",
            "/status": "Statut du cache",
            "/health": "Vérification de santé"
        }
    }

@app.get("/health")
def health_check():
    """Endpoint de vérification de santé pour Render"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "cache_status": is_cache_valid(),
        "pharmacies_count": len(CACHE["data"])
    }

@app.get("/pharmacies_de_garde")
async def pharmacies_de_garde(background_tasks: BackgroundTasks, force_update: bool = False):
    """
    Récupère les pharmacies de garde avec cache intelligent
    """
    
    # Si le cache est valide et qu'on ne force pas la mise à jour
    if is_cache_valid() and not force_update:
        return {
            "data": CACHE["data"],
            "metadata": {
                "source": "cache",
                "last_update": CACHE["last_update"].isoformat(),
                "count": len(CACHE["data"]),
                "cache_expires_in_minutes": round(CACHE["cache_duration_minutes"] - 
                    (datetime.now() - CACHE["last_update"]).total_seconds() / 60, 2)
            }
        }
    
    # Si on force la mise à jour ou si le cache n'est pas valide
    if force_update or not is_cache_valid():
        # Lancer la mise à jour en arrière-plan pour les prochaines requêtes
        background_tasks.add_task(update_cache_background)
        
        # Si on a des données en cache (même expirées), les retourner immédiatement
        if CACHE["data"]:
            return {
                "data": CACHE["data"],
                "metadata": {
                    "source": "cache_stale",
                    "last_update": CACHE["last_update"].isoformat() if CACHE["last_update"] else None,
                    "count": len(CACHE["data"]),
                    "note": "Données en cache retournées, mise à jour en cours en arrière-plan"
                }
            }
    
    # Si vraiment aucune donnée n'est disponible, faire une requête synchrone
    try:
        pharmacies = await scraper_pharmacies_async()
        if pharmacies:
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
            return {
                "data": [],
                "metadata": {
                    "source": "error",
                    "error": "Aucune donnée trouvée sur le site source",
                    "count": 0,
                    "suggestion": "Le site source peut être temporairement indisponible"
                }
            }
            
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des données: {e}")
        return {
            "data": [],
            "metadata": {
                "source": "error",
                "error": f"Erreur technique: {str(e)}",
                "count": 0,
                "suggestion": "Réessayez dans quelques minutes"
            }
        }

@app.get("/status")
def get_status():
    """Retourne le statut détaillé du cache et des données"""
    next_update = 0
    if CACHE["last_update"]:
        elapsed_minutes = (datetime.now() - CACHE["last_update"]).total_seconds() / 60
        next_update = max(0, CACHE["cache_duration_minutes"] - elapsed_minutes)
    
    return {
        "cache_status": {
            "is_cache_valid": is_cache_valid(),
            "is_updating": CACHE["is_updating"],
            "last_update": CACHE["last_update"].isoformat() if CACHE["last_update"] else None,
            "cached_pharmacies_count": len(CACHE["data"]),
            "cache_duration_minutes": CACHE["cache_duration_minutes"],
            "next_update_in_minutes": round(next_update, 2)
        },
        "system_info": {
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.0"
        }
    }

@app.post("/force_update")
async def force_update():
    """Force la mise à jour immédiate du cache"""
    await update_cache_background()
    return {
        "message": "Mise à jour forcée terminée",
        "count": len(CACHE["data"]),
        "last_update": CACHE["last_update"].isoformat() if CACHE["last_update"] else None
    }

@app.delete("/cache")
def clear_cache():
    """Vide le cache"""
    CACHE["data"] = []
    CACHE["last_update"] = None
    CACHE["is_updating"] = False
    return {"message": "Cache vidé avec succès"}
