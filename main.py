from fastapi import FastAPI
from bs4 import BeautifulSoup
import requests, re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os

app = FastAPI()

# Connexion à Google Sheets
def get_gsheet():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive.file",
             "https://www.googleapis.com/auth/drive"]

    # creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    creds_path = os.path.join(BASE_DIR, "credentials.json")
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)

    client = gspread.authorize(creds)
    sheet = client.open("pharmacies_togo")  # Nom du Google Sheet
    return sheet

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
            # Ajout de l'impression de débogage pour vérifier le contenu des cellules
            print(f"Nom: {nom}, Tel: {tel}, Adresse: {adresse}")
            if adresse: 
                pharmacies.append({
                    "Nom_pharmacie": nom,
                    "Numero_telephone": tel,
                    "Adresse": adresse
                })
            else:
                print(f"Adresse manquante pour la pharmacie: {nom}")
        else:
            print("Ligne mal formée, sautée.")

    return pharmacies

# Comparaison et mise à jour des données dans Google Sheet
def maj_google_sheet(pharmacies):
    sheet = get_gsheet()
    tab_pharmacies = sheet.worksheet("pharmacies")
    tab_gardes = sheet.worksheet("gardes")

    data_existante = tab_pharmacies.get_all_records()
    noms_existants = {ph["Nom_pharmacie"]: ph for ph in data_existante}

    # Mise à jour ou ajout dans "pharmacies"
    for p in pharmacies:
        nom = p["Nom_pharmacie"]
        if nom in noms_existants:
            existant = noms_existants[nom]
            if p["Numero_telephone"] != existant["Numero_telephone"] or p["Adresse"] != existant["Adresse"]:
                idx = list(noms_existants).index(nom) + 2
                tab_pharmacies.update(f"B{idx}", [[p["Numero_telephone"]]])
                tab_pharmacies.update(f"C{idx}", [[p["Adresse"]]])
        else:
            tab_pharmacies.append_row([p["Nom_pharmacie"], p["Numero_telephone"], p["Adresse"]])

    # Ajout du jour dans "gardes"
    today = datetime.today().strftime("%Y-%m-%d")
    for p in pharmacies:
        tab_gardes.append_row([today, p["Nom_pharmacie"], p["Numero_telephone"], p["Adresse"]])

@app.get("/pharmacies_de_garde")
def pharmacies_de_garde():
    return {"message": "API de pharmacies de garde en ligne 🚀"}

    try:
        pharmacies = scraper_pharmacies()
        maj_google_sheet(pharmacies)
        return pharmacies
    except Exception as e:
        return {"error": str(e)}

    pharmacies = scraper_pharmacies()
    maj_google_sheet(pharmacies)
    return pharmacies
