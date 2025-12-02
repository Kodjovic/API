#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API Flask pour Render - Pharmacies de Garde
Endpoints:
  POST /save-pharmacies - Reçoit et sauvegarde les données
  GET /api/pharmacies - Retourne les données sauvegardées
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime
import requests

app = Flask(__name__)
CORS(app)

# Configuration
PHARMACIES_FILE = "pharmacies.json"
WORDPRESS_WEBHOOK_URL = os.environ.get('WORDPRESS_WEBHOOK_URL', 'https://mapharmadegarde.com/wp-json/pharmacies/v1/update')

def log_message(message):
    """Affiche un message avec horodatage"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

def charger_pharmacies():
    """Charge les pharmacies depuis le fichier JSON"""
    try:
        if os.path.exists(PHARMACIES_FILE):
            with open(PHARMACIES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                log_message(f"✅ {len(data.get('pharmacies', []))} pharmacies chargées")
                return data
        else:
            log_message("⚠️ Fichier pharmacies.json non trouvé")
            return {"pharmacies": [], "last_update": None}
    except Exception as e:
        log_message(f"❌ Erreur lors du chargement: {e}")
        return {"pharmacies": [], "last_update": None}

def sauvegarder_pharmacies(pharmacies):
    """Sauvegarde les pharmacies dans le fichier JSON"""
    try:
        data = {
            "pharmacies": pharmacies,
            "last_update": datetime.now().isoformat(),
            "count": len(pharmacies)
        }
        
        with open(PHARMACIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        log_message(f"💾 {len(pharmacies)} pharmacies sauvegardées")
        return True
    except Exception as e:
        log_message(f"❌ Erreur lors de la sauvegarde: {e}")
        return False

def notifier_wordpress():
    """Envoie une notification POST à WordPress"""
    try:
        log_message(f"📤 Envoi notification à WordPress: {WORDPRESS_WEBHOOK_URL}")
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Render-Pharmacies-API/1.0"
        }
        
        payload = {
            "event": "pharmacies_updated",
            "timestamp": datetime.now().isoformat(),
            "message": "Nouvelles pharmacies disponibles"
        }
        
        response = requests.post(
            WORDPRESS_WEBHOOK_URL,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            log_message("✅ WordPress notifié avec succès")
            return True
        else:
            log_message(f"⚠️ Notification WordPress - Code: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        log_message("⏰ Timeout lors de la notification WordPress")
        return False
    except Exception as e:
        log_message(f"❌ Erreur notification WordPress: {e}")
        return False

@app.route('/')
def home():
    """Page d'accueil de l'API"""
    data = charger_pharmacies()
    return jsonify({
        "service": "API Pharmacies de Garde - Render",
        "status": "online",
        "endpoints": {
            "save": "POST /save-pharmacies",
            "get": "GET /api/pharmacies"
        },
        "stats": {
            "pharmacies_count": data.get("count", 0),
            "last_update": data.get("last_update", "Jamais")
        }
    })

@app.route('/save-pharmacies', methods=['POST'])
def save_pharmacies():
    """
    Endpoint POST pour recevoir et sauvegarder les pharmacies
    Notifie automatiquement WordPress après sauvegarde
    """
    try:
        log_message("📥 Réception de nouvelles pharmacies")
        
        # Récupérer les données JSON
        pharmacies = request.get_json()
        
        if not pharmacies:
            log_message("❌ Aucune donnée reçue")
            return jsonify({
                "success": False,
                "error": "Aucune donnée fournie"
            }), 400
        
        # Vérifier que c'est une liste
        if not isinstance(pharmacies, list):
            log_message("❌ Format invalide (pas une liste)")
            return jsonify({
                "success": False,
                "error": "Les données doivent être une liste"
            }), 400
        
        log_message(f"📊 {len(pharmacies)} pharmacies reçues")
        
        # Sauvegarder les données
        if not sauvegarder_pharmacies(pharmacies):
            return jsonify({
                "success": False,
                "error": "Erreur lors de la sauvegarde"
            }), 500
        
        # Notifier WordPress (non bloquant)
        wordpress_notified = notifier_wordpress()
        
        response = {
            "success": True,
            "message": "Pharmacies sauvegardées avec succès",
            "count": len(pharmacies),
            "timestamp": datetime.now().isoformat(),
            "wordpress_notified": wordpress_notified
        }
        
        log_message(f"✅ Opération terminée - WordPress notifié: {wordpress_notified}")
        
        return jsonify(response), 200
        
    except Exception as e:
        log_message(f"❌ Erreur dans save_pharmacies: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/pharmacies', methods=['GET'])
def get_pharmacies():
    """
    Endpoint GET pour récupérer les pharmacies sauvegardées
    Utilisé par WordPress pour récupérer les données
    """
    try:
        log_message("📤 Demande de récupération des pharmacies")
        
        data = charger_pharmacies()
        
        if not data.get("pharmacies"):
            log_message("⚠️ Aucune pharmacie disponible")
            return jsonify({
                "success": True,
                "pharmacies": [],
                "count": 0,
                "last_update": None,
                "message": "Aucune pharmacie disponible"
            }), 200
        
        response = {
            "success": True,
            "pharmacies": data["pharmacies"],
            "count": data.get("count", len(data["pharmacies"])),
            "last_update": data.get("last_update"),
            "timestamp": datetime.now().isoformat()
        }
        
        log_message(f"✅ {response['count']} pharmacies envoyées")
        
        return jsonify(response), 200
        
    except Exception as e:
        log_message(f"❌ Erreur dans get_pharmacies: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de santé pour Render"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    log_message(f"🚀 Démarrage de l'API sur le port {port}")
    log_message(f"🔗 WordPress Webhook: {WORDPRESS_WEBHOOK_URL}")
    app.run(host='0.0.0.0', port=port, debug=False)
