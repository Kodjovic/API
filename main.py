@app.delete("/cache")
def clear_cache():
    """Vide le cache"""
    CACHE["data"] = []
    CACHE["last_update"] = None
    CACHE["is_updating"] = False
    return {"message": "Cache vidé avec succès"}

# Données de fallback en cas d'échec total du scraping
FALLBACK_DATA = [
    {
        "Nom_pharmacie": "Pharmacie de l'Étoile",
        "Numero_telephone": "22 21 27 64",
        "Adresse": "Rue de l'Indépendance, Lomé"
    },
    {
        "Nom_pharmacie": "Pharmacie du Centre",
        "Numero_telephone": "22 21 35 42",
        "Adresse": "Avenue du 24 Janvier, Lomé"
    },
    {
        "Nom_pharmacie": "Pharmacie de la Paix",
        "Numero_telephone": "22 21 45 67",
        "Adresse": "Boulevard du 13 Janvier, Lomé"
    }
]

@app.get("/fallback_data")
def get_fallback_data():
    """Retourne des données de fallback pour tests"""
    return {
        "data": FALLBACK_DATA,
        "metadata": {
            "source": "fallback",
            "count": len(FALLBACK_DATA),
            "note": "Données de test - remplacer par scraping réel"
        }
    }from fastapi import FastAPI, BackgroundTasks
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
    'timeout': aiohttp.ClientTimeout(total=30, connect=10, sock_read=20),
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
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
    """Scraping asynchrone des pharmacies avec retry et multiples stratégies"""
    urls_to_try = [
        "https://www.inam.tg/pharmacies-de-garde/",
        "http://www.inam.tg/pharmacies-de-garde/",  # Fallback HTTP
    ]
    
    # Différents User-Agents à essayer
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0'
    ]
    
    for attempt in range(3):  # 3 tentatives
        for url in urls_to_try:
            for user_agent in user_agents:
                try:
                    logger.info(f"Tentative {attempt + 1}: {url} avec UA: {user_agent[:50]}...")
                    
                    # Configuration spécifique pour cette tentative
                    timeout = aiohttp.ClientTimeout(
                        total=45,  # Timeout total augmenté
                        connect=15,  # Timeout de connexion
                        sock_read=30  # Timeout de lecture
                    )
                    
                    headers = REQUEST_CONFIG['headers'].copy()
                    headers['User-Agent'] = user_agent
                    
                    # Connector avec SSL désactivé si nécessaire
                    connector = aiohttp.TCPConnector(
                        limit=30,
                        ttl_dns_cache=300,
                        use_dns_cache=True,
                        verify_ssl=False  # Désactiver SSL pour les sites avec certificats problématiques
                    )
                    
                    async with aiohttp.ClientSession(
                        timeout=timeout,
                        connector=connector,
                        headers=headers
                    ) as session:
                        
                        # Essayer avec delay progressif
                        if attempt > 0:
                            await asyncio.sleep(2 ** attempt)  # 2, 4, 8 secondes
                        
                        async with session.get(url, allow_redirects=True) as response:
                            logger.info(f"Status: {response.status}, Headers: {dict(response.headers)}")
                            
                            if response.status == 200:
                                html_content = await response.text()
                                logger.info(f"Contenu HTML récupéré ({len(html_content)} caractères)")
                                
                                # Vérifier si on a du contenu utile
                                if len(html_content) > 1000:  # Minimum de contenu attendu
                                    pharmacies = parse_html_content(html_content)
                                    if pharmacies:
                                        logger.info(f"✅ Succès avec {url}: {len(pharmacies)} pharmacies")
                                        return pharmacies
                                    else:
                                        logger.warning(f"HTML récupéré mais aucune pharmacie trouvée")
                                        # Log d'un échantillon du HTML pour debug
                                        logger.debug(f"Échantillon HTML: {html_content[:500]}...")
                                else:
                                    logger.warning(f"Contenu HTML trop court: {len(html_content)} caractères")
                            
                            elif response.status in [403, 406]:
                                logger.warning(f"Accès refusé ({response.status}), tentative avec autre User-Agent")
                                continue
                            else:
                                logger.warning(f"HTTP {response.status}: {response.reason}")
                
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout avec {url} (tentative {attempt + 1})")
                    continue
                except aiohttp.ClientError as e:
                    logger.warning(f"Erreur client avec {url}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Erreur avec {url}: {e}")
                    continue
    
    logger.error("❌ Toutes les tentatives de scraping ont échoué")
    return []

def parse_html_content(html_content: str) -> List[Dict]:
    """Parse le contenu HTML et extrait les pharmacies"""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Log de la structure pour debug
        logger.info(f"Titre de la page: {soup.title.string if soup.title else 'N/A'}")
        
        # Multiples stratégies de recherche
        table = None
        strategies = [
            lambda: soup.find('table'),
            lambda: soup.find('div', class_='pharmacies'),
            lambda: soup.find('div', id='pharmacies'),
            lambda: soup.find('div', class_='table-responsive'),
            lambda: soup.find('tbody'),
            lambda: soup.select('.pharmacy-list tr'),
            lambda: soup.select('table tr'),
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                result = strategy()
                if result:
                    table = result
                    logger.info(f"✅ Stratégie {i+1} réussie: {table.name}")
                    break
            except Exception as e:
                logger.debug(f"Stratégie {i+1} échouée: {e}")
                continue
        
        if not table:
            logger.error("❌ Aucune table/structure trouvée avec toutes les stratégies")
            # Log des balises principales pour debug
            main_tags = [tag.name for tag in soup.find_all()[:20]]
            logger.debug(f"Principales balises trouvées: {main_tags}")
            return []
        
        pharmacies = []
        
        # Traitement selon le type d'élément trouvé
        if table.name == 'table' or table.name == 'tbody':
            rows = table.find_all('tr')[1:] if table.find_all('tr') else []
        else:
            rows = table.find_all('div', class_='pharmacy-row') if hasattr(table, 'find_all') else []
        
        logger.info(f"Trouvé {len(rows)} lignes à traiter")
        
        for i, row in enumerate(rows):
            try:
                if row.find_all('td'):
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        nom = nettoyer_texte(cells[0].get_text())
                        tel = nettoyer_texte(cells[1].get_text())
                        adresse = nettoyer_texte(cells[2].get_text())
                    else:
                        continue
                else:
                    # Stratégie alternative
                    nom = nettoyer_texte(row.find(class_='nom').get_text() if row.find(class_='nom') else "")
                    tel = nettoyer_texte(row.find(class_='tel').get_text() if row.find(class_='tel') else "")
                    adresse = nettoyer_texte(row.find(class_='adresse').get_text() if row.find(class_='adresse') else "")
                
                if nom and len(nom) > 2:  # Validation plus stricte
                    pharmacies.append({
                        "Nom_pharmacie": nom,
                        "Numero_telephone": tel,
                        "Adresse": adresse
                    })
                    
            except Exception as e:
                logger.warning(f"Erreur ligne {i}: {e}")
                continue
        
        logger.info(f"✅ Parsing terminé: {len(pharmacies)} pharmacies extraites")
        return pharmacies
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du parsing HTML: {e}")
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

@app.get("/test_scraping")
async def test_scraping():
    """Endpoint de test pour diagnostiquer les problèmes de scraping"""
    url = "https://www.inam.tg/pharmacies-de-garde/"
    
    results = {
        "url": url,
        "tests": [],
        "final_result": None
    }
    
    # Test de connectivité basique
    try:
        import socket
        socket.setdefaulttimeout(10)
        host = "www.inam.tg"
        port = 443
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((host, port))
        sock.close()
        
        connectivity_test = {
            "test": "connectivity",
            "success": result == 0,
            "details": f"Connexion TCP vers {host}:{port} {'réussie' if result == 0 else 'échouée'}"
        }
        results["tests"].append(connectivity_test)
        
    except Exception as e:
        results["tests"].append({
            "test": "connectivity",
            "success": False,
            "error": str(e)
        })
    
    # Test HTTP basique
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(verify_ssl=False)
        ) as session:
            async with session.get(url) as response:
                http_test = {
                    "test": "http_basic",
                    "success": response.status == 200,
                    "status": response.status,
                    "headers": dict(response.headers),
                    "content_length": len(await response.text()) if response.status == 200 else 0
                }
                results["tests"].append(http_test)
                
    except Exception as e:
        results["tests"].append({
            "test": "http_basic",
            "success": False,
            "error": str(e)
        })
    
    # Test de scraping complet
    try:
        pharmacies = await scraper_pharmacies_async()
        scraping_test = {
            "test": "full_scraping",
            "success": len(pharmacies) > 0,
            "pharmacies_found": len(pharmacies),
            "sample_data": pharmacies[:2] if pharmacies else None
        }
        results["tests"].append(scraping_test)
        results["final_result"] = pharmacies
        
    except Exception as e:
        results["tests"].append({
            "test": "full_scraping",
            "success": False,
            "error": str(e)
        })
    
    return results
