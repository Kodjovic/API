from fastapi import FastAPI
from bs4 import BeautifulSoup
import requests
import re

app = FastAPI()

# Nettoyage du texte
def nettoyer_texte(texte):
    texte = texte.strip()
    texte = texte.replace("☎", "").replace("â˜Ž", "").replace("Â", "")
    return re.sub(r"\s{2,}", " ", texte)

# Scraping du site
def scraper_pharmacies():
    url = "https://www.inam.tg/pharmacies-de-garde/"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find('table')
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
        # Tu peux ajouter un log si tu veux voir ce qui est ignoré

    return pharmacies

# Route d’accueil
@app.get("/")
def home():
    return {"message": "Bienvenue sur l'API de pharmacies de garde en ligne 🚑"}

# Route principale de l’API
@app.get("/pharmacies_de_garde")
def pharmacies_de_garde():
    try:
        pharmacies = scraper_pharmacies()
        return pharmacies
    except Exception as e:
        return {"error": str(e)}
