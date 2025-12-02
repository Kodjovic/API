#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API FLASK POUR RENDER - Pharmacies de Garde
Reçoit les données du script local et notifie WordPress
"""

from flask import Flask, request, jsonify
import json
import os
import requests
from datetime import datetime

app = Flask(__name__)

# 🔧 Configuration
JSON_FILE = "pharmacies.json"
WORDPRESS_WEBHOOK = os.getenv('WORDPRESS_WEBHOOK', 'https://mapharmadegarde.com/wp-json/custom/v1/notify-update')

# ====================
# ENDPOINTS
# ====================

@app.route('/', methods=['GET'])
def home():
    """Page d'accueil de l'API"""
    return jsonify({
        "status": "online",
        "service": "Pharmacies de Garde API",
        "version": "1.0",
        "endpoints": {
            "POST /upload_pharmacies": "Recevoir et sauvegarder les pharmacies",
            "GET /api/pharmacies": "Récupérer les pharmacies"
        }
    }), 200


@app.route('/upload_pharmacies', methods=['POST'])
def upload_pharmacies():
    """
    Reçoit les pharmacies depuis votre machine locale
    Sauvegarde dans pharmacies.json
    Notifie automatiquement WordPress
    """
    try:
        # 1. Récupérer les données
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Aucune donnée reçue"
            }), 400
        
        if not isinstance(data, list):
            return jsonify({
                "success": False,
                "error": "Format invalide. Attendu: liste de pharmacies"
            }), 400
        
        print(f"📥 Reçu {len(data)} pharmacies")
        
        # 2. Ajouter métadonnées
        pharmacies_data = {
            "pharmacies": data,
            "last_update": datetime.now().isoformat(),
            "count": len(data)
        }
        
        # 3. Sauvegarder dans le fichier JSON
        try:
            with open(JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(pharmacies_data, f, ensure_ascii=False, indent=2)
            print(f"💾 Sauvegardé dans {JSON_FILE}")
        except Exception as e:
            print(f"❌ Erreur de sauvegarde: {e}")
            return jsonify({
                "success": False,
                "error": f"Erreur de sauvegarde: {str(e)}"
            }), 500
        
        # 4. Notifier WordPress automatiquement
        print("📤 Notification de WordPress...")
        notification_success = notifier_wordpress(len(data))
        
        # 5. Réponse
        return jsonify({
            "success": True,
            "message": "Pharmacies sauvegardées avec succès",
            "data": {
                "count": len(data),
                "timestamp": pharmacies_data["last_update"],
                "wordpress_notified": notification_success
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/pharmacies', methods=['GET'])
def get_pharmacies():
    """
    Retourne les pharmacies stockées
    Utilisé par WordPress pour récupérer les données
    """
    try:
        # Vérifier si le fichier existe
        if not os.path.exists(JSON_FILE):
            return jsonify({
                "success": False,
                "error": "Aucune donnée disponible",
                "pharmacies": [],
                "count": 0
            }), 404
        
        # Lire le fichier
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"📤 Envoi de {data.get('count', 0)} pharmacies")
        
        return jsonify({
            "success": True,
            "pharmacies": data.get("pharmacies", []),
            "last_update": data.get("last_update"),
            "count": data.get("count", 0)
        }), 200
        
    except json.JSONDecodeError:
        return jsonify({
            "success": False,
            "error": "Fichier JSON corrompu",
            "pharmacies": [],
            "count": 0
        }), 500
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "pharmacies": [],
            "count": 0
        }), 500


def notifier_wordpress(pharmacies_count):
    """
    Envoie une notification à WordPress
    WordPress va ensuite récupérer les données via GET /api/pharmacies
    """
    try:
        print(f"🔔 Notification WordPress: {WORDPRESS_WEBHOOK}")
        
        payload = {
            "message": "Nouvelles pharmacies disponibles",
            "count": pharmacies_count,
            "timestamp": datetime.now().isoformat()
        }
        
        response = requests.post(
            WORDPRESS_WEBHOOK,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ WordPress notifié avec succès")
            return True
        else:
            print(f"⚠️ WordPress a répondu avec le code {response.status_code}")
            print(f"Réponse: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print("⏰ Timeout lors de la notification WordPress")
        return False
        
    except requests.exceptions.ConnectionError:
        print("🌐 Erreur de connexion à WordPress")
        return False
        
    except Exception as e:
        print(f"❌ Erreur lors de la notification WordPress: {e}")
        return False


# ====================
# ENDPOINTS DE DEBUG
# ====================

@app.route('/status', methods=['GET'])
def status():
    """Vérifie l'état du système"""
    file_exists = os.path.exists(JSON_FILE)
    
    status_info = {
        "status": "running",
        "json_file_exists": file_exists,
        "json_file_path": os.path.abspath(JSON_FILE) if file_exists else None,
        "wordpress_webhook": WORDPRESS_WEBHOOK,
        "timestamp": datetime.now().isoformat()
    }
    
    if file_exists:
        try:
            with open(JSON_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            status_info["pharmacies_count"] = data.get("count", 0)
            status_info["last_update"] = data.get("last_update")
        except:
            status_info["json_file_error"] = "Impossible de lire le fichier"
    
    return jsonify(status_info), 200


@app.route('/test-wordpress', methods=['GET'])
def test_wordpress():
    """Teste la connexion à WordPress"""
    success = notifier_wordpress(0)
    
    return jsonify({
        "wordpress_webhook": WORDPRESS_WEBHOOK,
        "notification_sent": success,
        "message": "Notification de test envoyée" if success else "Échec de la notification"
    }), 200 if success else 500


# ====================
# LANCEMENT
# ====================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"🚀 Démarrage de l'API sur le port {port}")
    print(f"📁 Fichier de données: {JSON_FILE}")
    print(f"🔗 Webhook WordPress: {WORDPRESS_WEBHOOK}")
    app.run(host='0.0.0.0', port=port, debug=False)

