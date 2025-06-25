#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCRIPT FINAL : Scraper et envoyer directement les pharmacies à l'API Render
Installation : pip install requests beautifulsoup4
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

# 🔧 Configuration
URL_SOURCE = "https://www.inam.tg/pharmacies-de-garde/"
URL_API = "https://api-y5ud.onrender.com/upload_pharmacies"  # ✅ la bonne route POST

# Nettoyage du texte
def nettoyer_texte(texte):
    texte = texte.strip()
    texte = texte.replace("☎", "").replace("â˜Ž", "").replace("Â", "")
    return re.sub(r"\s{2,}", " ", texte)

# Scraping du site
def scraper_pharmacies():
    print(f"🔍 Scraping: {URL_SOURCE}")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(URL_SOURCE, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        table = soup.find('table')

        if not table:
            print("❌ Aucune table trouvée sur la page.")
            return []

        pharmacies = []
        for row in table.find_all('tr')[1:]:
            cells = row.find_all('td')
            if len(cells) >= 3:
                nom = nettoyer_texte(cells[0].text)
                tel = nettoyer_texte(cells[1].text)
                adresse = nettoyer_texte(cells[2].text)

                if adresse:
                    pharmacies.append({
                        "Nom_pharmacie": nom,
                        "Numero_telephone": tel,
                        "Adresse": adresse
                    })

        print(f"✅ {len(pharmacies)} pharmacies trouvées.")
        return pharmacies

    except Exception as e:
        print(f"❌ Erreur lors du scraping : {e}")
        return []

# Envoi à l'API Render
def envoyer_vers_api(pharmacies):
    if not pharmacies:
        print("❌ Aucune pharmacie à envoyer.")
        return False
    try:
        print(f"📤 Envoi à l'API : {URL_API}")
        response = requests.post(URL_API, json=pharmacies)
        if response.status_code == 200:
            print("✅ Données envoyées avec succès à l'API !")
            return True
        else:
            print(f"❌ Échec de l'envoi. Code : {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi à l'API : {e}")
        return False

# Exécution principale
if __name__ == "__main__":
    print("🏥 SCRAPER ET ENVOYER LES PHARMACIES DE GARDE")
    print("=" * 50)

    pharmacies = scraper_pharmacies()
    if pharmacies:
        envoyer_vers_api(pharmacies)
    else:
        print("❌ Rien à envoyer.")
