import os
from flask import Blueprint, send_from_directory

pages_bp = Blueprint('pages', __name__)

# Racine du repo (un niveau au-dessus de app/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HTML_FILES = [
    'Tableau-de-bord.html',
    'Budget.html',
    'Comptabilite-Generale.html',
    'Comptabilité-analytics.html',
    'Gestion-des-contrats.html',
    'cockpit-tresorie.html',
    'gestion-des-immobiliers.html',
]


@pages_bp.route('/')
def index():
    return send_from_directory(BASE_DIR, 'Tableau-de-bord.html')


@pages_bp.route('/<path:filename>')
def serve_file(filename):
    """Sert les fichiers HTML, JS, CSS et assets depuis la racine du repo."""
    filepath = os.path.join(BASE_DIR, filename)
    if os.path.isfile(filepath):
        return send_from_directory(BASE_DIR, filename)
    return f'Fichier introuvable : {filename}', 404
