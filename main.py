import requests
from bs4 import BeautifulSoup
import json
import re
import unicodedata
from datetime import datetime
import ssl
import urllib3
import time
import sys

# 🔧 Configuration
URL_SOURCE = "https://www.inam.tg/pharmacies-de-garde/"
URL_API = "https://api-y5ud.onrender.com/upload_pharmacies"

# Configuration SSL simplifiée
def configurer_ssl():
    """Configure les paramètres SSL pour éviter les erreurs de certificat"""
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    session = requests.Session()
    session.verify = False
    
    # Configuration d'adaptateur simple (sans retry complexe)
    from requests.adapters import HTTPAdapter
    
    adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

# Nettoyage du texte
def nettoyer_texte(texte):
    if not texte:
        return ""
    texte = texte.strip()
    texte = texte.replace("☎", "").replace("â˜Ž", "").replace("Â", "")
    return re.sub(r"\s{2,}", " ", texte)

# Génération d'URL complète
def generer_url_complete(nom):
    """Génère l'URL complète à partir du nom de la pharmacie"""
    if not nom:
        return ""
    
    slug = unicodedata.normalize('NFKD', nom)
    slug = slug.encode('ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', slug.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    slug = slug.strip('-')
    
    return f"https://mapharmadegarde.com/pharmacies/{slug}"

# Scraping avec tentatives multiples
def scraper_pharmacies(max_attempts=3, timeout_progression=[30, 60, 120]):
    """Scrape les pharmacies avec plusieurs tentatives et timeouts progressifs"""
    
    for attempt in range(max_attempts):
        timeout = timeout_progression[min(attempt, len(timeout_progression)-1)]
        print(f"🔍 Tentative {attempt + 1}/{max_attempts} - Timeout: {timeout}s")
        print(f"📡 Scraping: {URL_SOURCE}")
        
        session = configurer_ssl()
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            }
            
            print("🔐 Configuration SSL et retry appliquée...")
            
            # Faire la requête avec le timeout progressif
            response = session.get(URL_SOURCE, headers=headers, timeout=timeout, stream=True)
            
            # Lire le contenu par chunks pour éviter les timeouts
            content = b""
            for chunk in response.iter_content(chunk_size=8192, decode_unicode=False):
                if chunk:
                    content += chunk
            
            response._content = content
            response.raise_for_status()
            
            print(f"✅ Réponse reçue (Status: {response.status_code}, Taille: {len(content)} bytes)")
            
            # Parser le HTML
            soup = BeautifulSoup(content, "lxml")
            table = soup.find('table')

            if not table:
                print("❌ Aucune table trouvée sur la page.")
                
                # Recherche alternative plus exhaustive
                print("🔍 Recherche d'autres structures possibles...")
                
                # Essayer différents sélecteurs
                selectors = [
                    'table',
                    '.pharmacy-table',
                    '.pharmacie-table', 
                    'div[class*="pharmacy"]',
                    'div[class*="pharmacie"]',
                    'ul[class*="pharmacy"]',
                    'ul[class*="pharmacie"]'
                ]
                
                for selector in selectors:
                    elements = soup.select(selector)
                    if elements:
                        print(f"📋 {len(elements)} éléments trouvés avec sélecteur: {selector}")
                        break
                
                # Afficher un échantillon du contenu pour debug
                text_content = soup.get_text()[:1000]
                print(f"📄 Contenu de la page (premiers 1000 caractères):")
                print(text_content)
                print("...")
                
                if attempt < max_attempts - 1:
                    print(f"⏳ Attente de 5 secondes avant la prochaine tentative...")
                    time.sleep(5)
                    continue
                else:
                    return []

            # Traitement de la table trouvée
            pharmacies = []
            rows = table.find_all('tr')[1:]  # Skip header
            
            print(f"📊 {len(rows)} lignes trouvées dans la table")
            
            for i, row in enumerate(rows, 1):
                cells = row.find_all('td')
                if len(cells) >= 3:
                    nom = nettoyer_texte(cells[0].text)
                    tel = nettoyer_texte(cells[1].text)
                    adresse = nettoyer_texte(cells[2].text)

                    if nom and adresse:
                        url_complete = generer_url_complete(nom)
                        
                        pharmacies.append({
                            "Nom_pharmacie": nom,
                            "Numero_telephone": tel,
                            "Adresse": adresse,
                            "url": url_complete
                        })
                        print(f"  → {i:2d}. {nom}")
                        if tel:
                            print(f"      📞 {tel}")
                        print(f"      📍 {adresse}")

            print(f"✅ {len(pharmacies)} pharmacies trouvées et traitées.")
            return pharmacies

        except requests.exceptions.ReadTimeout as timeout_err:
            print(f"⏰ Timeout après {timeout}s : {timeout_err}")
            if attempt < max_attempts - 1:
                print(f"💡 Nouvelle tentative avec timeout plus long...")
                time.sleep(2)
                continue
            else:
                print("❌ Toutes les tentatives ont échoué avec timeout")
                return []
                
        except requests.exceptions.SSLError as ssl_err:
            print(f"🔐 Erreur SSL : {ssl_err}")
            if attempt < max_attempts - 1:
                print("💡 Nouvelle tentative...")
                time.sleep(2)
                continue
            else:
                return []
                
        except requests.exceptions.ConnectionError as conn_err:
            print(f"🌐 Erreur de connexion : {conn_err}")
            if attempt < max_attempts - 1:
                print("💡 Nouvelle tentative...")
                time.sleep(5)
                continue
            else:
                return []
                
        except Exception as e:
            print(f"❌ Erreur inattendue : {e}")
            print(f"📊 Type d'erreur: {type(e).__name__}")
            if attempt < max_attempts - 1:
                print("💡 Nouvelle tentative...")
                time.sleep(2)
                continue
            else:
                return []
        
        finally:
            session.close()
    
    return []

# Envoi à l'API avec retry
def envoyer_vers_api(pharmacies, max_attempts=3):
    """Envoie les données à l'API avec tentatives multiples"""
    if not pharmacies:
        print("❌ Aucune pharmacie à envoyer.")
        return False
    
    for attempt in range(max_attempts):
        print(f"📤 Tentative d'envoi {attempt + 1}/{max_attempts}")
        print(f"📡 Envoi de {len(pharmacies)} pharmacies à l'API : {URL_API}")
        
        session = configurer_ssl()
        
        try:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "pharmacie-garde-togo/1.0",
                "Accept": "application/json"
            }
            
            response = session.post(URL_API, json=pharmacies, headers=headers, timeout=60)
            
            print(f"📊 Réponse API - Code: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Données envoyées avec succès à l'API !")
                try:
                    response_json = response.json()
                    print(f"📄 Réponse: {response_json}")
                except:
                    print(f"📄 Réponse (texte): {response.text[:200]}...")
                return True
            else:
                print(f"❌ Échec de l'envoi. Code : {response.status_code}")
                print(f"📄 Erreur: {response.text[:500]}...")
                
                if attempt < max_attempts - 1:
                    print("💡 Nouvelle tentative dans 5 secondes...")
                    time.sleep(5)
                    continue
                else:
                    return False
                    
        except Exception as e:
            print(f"❌ Erreur lors de l'envoi à l'API : {e}")
            if attempt < max_attempts - 1:
                print("💡 Nouvelle tentative...")
                time.sleep(3)
                continue
            else:
                return False
        
        finally:
            session.close()
    
    return False

# Test de connectivité amélioré
def tester_connectivite():
    """Teste la connectivité vers le site cible avec plusieurs méthodes"""
    print("🔍 Test de connectivité...")
    session = configurer_ssl()
    
    try:
        # Test HEAD plus rapide
        response = session.head(URL_SOURCE, timeout=15)
        print(f"✅ Site accessible via HEAD (Status: {response.status_code})")
        return True
    except:
        try:
            # Si HEAD échoue, essayer GET avec timeout court
            response = session.get(URL_SOURCE, timeout=10, stream=True)
            print(f"✅ Site accessible via GET (Status: {response.status_code})")
            return True
        except Exception as e:
            print(f"❌ Site inaccessible : {e}")
            return False
    finally:
        session.close()

# Sauvegarde avec horodatage
def sauvegarder_localement(pharmacies, raison="backup"):
    """Sauvegarde les données localement"""
    if not pharmacies:
        return None
        
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"pharmacies_{raison}_{timestamp}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(pharmacies, f, ensure_ascii=False, indent=2)
        print(f"💾 Sauvegarde créée: {filename}")
        return filename
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        return None

# Fonction principale avec gestion d'erreur globale
def main():
    """Fonction principale avec gestion complète des erreurs"""
    try:
        print("🏥 SCRAPER ET ENVOYER LES PHARMACIES DE GARDE")
        print("=" * 50)
        print(f"📅 Démarré le: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Test de connectivité préalable
        if not tester_connectivite():
            print("❌ Impossible de se connecter au site. Arrêt du processus.")
            return False
        
        print()
        
        # Scraping des pharmacies avec retry
        print("🔄 Début du scraping avec gestion des timeouts...")
        pharmacies = scraper_pharmacies(max_attempts=3, timeout_progression=[45, 90, 180])
        
        if not pharmacies:
            print("❌ Aucune pharmacie trouvée après toutes les tentatives.")
            print("💡 Conseils de dépannage:")
            print("   - Le site pourrait être temporairement surchargé")
            print("   - Vérifiez votre connexion internet")
            print("   - Essayez de relancer le script dans 10-15 minutes")
            print("   - La structure HTML du site a peut-être changé")
            return False
        
        # Sauvegarde préventive
        sauvegarder_localement(pharmacies, "pre_upload")
        
        print()
        
        # Envoi vers l'API
        print("📤 Envoi vers l'API...")
        success = envoyer_vers_api(pharmacies, max_attempts=3)
        
        print()
        print("🏁 RÉSULTATS")
        print(f"📊 Total pharmacies scrapées: {len(pharmacies)}")
        print(f"📤 Envoi API: {'✅ Succès' if success else '❌ Échec'}")
        
        # Sauvegarde de secours si échec API
        if not success:
            backup_file = sauvegarder_localement(pharmacies, "api_failed")
            if backup_file:
                print(f"🔄 Vous pouvez réessayer l'upload plus tard avec: {backup_file}")
        
        return success
        
    except KeyboardInterrupt:
        print("\n⚠️ Interruption par l'utilisateur (Ctrl+C)")
        return False
    except Exception as e:
        print(f"❌ Erreur fatale dans le programme principal: {e}")
        return False

if __name__ == "__main__":
    # Empêcher les exécutions multiples accidentelles
    print("🚀 Lancement du scraper...")
    success = main()
    
    if success:
        print("🎉 Mission accomplie !")
        sys.exit(0)
    else:
        print("💥 Mission échouée - voir les détails ci-dessus")
        sys.exit(1)
