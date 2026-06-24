from flask import Blueprint, jsonify, request, session
from app.models import Entite, Utilisateur
from app.context import ROLES, HOLDING_CODE

api_bp = Blueprint('api', __name__, url_prefix='/api')


# ── GET /api/entites ───────────────────────────────────────────────────────
@api_bp.route('/entites')
def get_entites():
    """Retourne toutes les entités + l'option 'Consolidé' pour la holding."""
    entites = [e.to_dict() for e in Entite.query.order_by(Entite.type.desc(), Entite.code).all()]

    # Prepend "Consolidé" — vue agrégée disponible quand l'entité courante est MDP
    consolide = {
        'id':     'CONSOLIDE',
        'code':   'CONSOLIDE',
        'nom':    'Consolidé (Groupe)',
        'type':   'consolide',
        'devise': 'XOF',
    }
    return jsonify([consolide] + entites)


# ── GET /api/roles ─────────────────────────────────────────────────────────
@api_bp.route('/roles')
def get_roles():
    return jsonify(ROLES)


# ── GET /api/contexte ──────────────────────────────────────────────────────
@api_bp.route('/contexte', methods=['GET'])
def get_contexte():
    code = session.get('entite_code')
    role = session.get('role', 'Direction')

    entite = None
    if code == 'CONSOLIDE':
        entite = {'code': 'CONSOLIDE', 'nom': 'Consolidé (Groupe)', 'type': 'consolide'}
    elif code:
        e = Entite.query.filter_by(code=code).first()
        if e:
            entite = e.to_dict()

    return jsonify({'entite_code': code, 'role': role, 'entite': entite})


# ── POST /api/contexte ─────────────────────────────────────────────────────
@api_bp.route('/contexte', methods=['POST'])
def set_contexte():
    """Change l'entité et/ou le rôle en session."""
    data = request.get_json(force=True) or {}

    if 'entite_code' in data:
        code = data['entite_code']
        if code == 'CONSOLIDE' or Entite.query.filter_by(code=code).first():
            session['entite_code'] = code
        else:
            return jsonify({'error': f'Entité inconnue : {code}'}), 400

    if 'role' in data:
        if data['role'] in ROLES:
            session['role'] = data['role']
        else:
            return jsonify({'error': f'Rôle inconnu : {data["role"]}'}), 400

    return jsonify({
        'ok':          True,
        'entite_code': session.get('entite_code'),
        'role':        session.get('role', 'Direction'),
    })
