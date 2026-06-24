from flask import Blueprint, jsonify, request
from app import db
from app.models import Tiers, Entite
from app.context import current_entite, is_consolidé

tiers_bp = Blueprint('tiers', __name__, url_prefix='/api/tiers')


def _visible_query():
    """Tiers visibles par l'entité courante = partage groupe + partage entite propres."""
    if is_consolidé():
        return Tiers.query
    code = current_entite()
    entite = Entite.query.filter_by(code=code).first()
    if entite:
        return Tiers.query.filter(
            db.or_(Tiers.partage == 'groupe', Tiers.entite_id == entite.id)
        )
    return Tiers.query.filter(Tiers.partage == 'groupe')


@tiers_bp.route('', methods=['GET'])
def get_tiers():
    query = _visible_query()
    if t := request.args.get('type'):
        query = query.filter(Tiers.type == t)
    if s := request.args.get('statut'):
        query = query.filter(Tiers.statut == s)
    q = request.args.get('q', '').strip()
    if q:
        query = query.filter(
            db.or_(Tiers.nom.ilike(f'%{q}%'), Tiers.code.ilike(f'%{q}%'))
        )
    return jsonify([x.to_dict() for x in query.order_by(Tiers.nom).all()])


@tiers_bp.route('', methods=['POST'])
def create_tiers():
    data = request.get_json(force=True) or {}

    if not data.get('code') or not data.get('nom'):
        return jsonify({'error': 'code et nom requis'}), 400

    if Tiers.query.filter_by(code=data['code']).first():
        return jsonify({'error': f'Code {data["code"]} déjà utilisé'}), 409

    code = current_entite()
    entite = None if is_consolidé() else Entite.query.filter_by(code=code).first()

    t = Tiers(
        type      = data.get('type', 'client'),
        code      = data['code'],
        nom       = data['nom'],
        partage   = data.get('partage', 'entite'),
        entite_id = entite.id if entite else None,
        statut    = data.get('statut', 'actif'),
    )
    db.session.add(t)
    db.session.commit()
    return jsonify(t.to_dict()), 201


@tiers_bp.route('/<int:tid>', methods=['GET'])
def get_un_tiers(tid):
    return jsonify(db.session.get(Tiers, tid).to_dict())


@tiers_bp.route('/<int:tid>', methods=['PUT'])
def update_tiers(tid):
    t = db.session.get(Tiers, tid)
    if not t:
        return jsonify({'error': 'Tiers introuvable'}), 404
    data = request.get_json(force=True) or {}
    for field in ('nom', 'statut', 'partage'):
        if field in data:
            setattr(t, field, data[field])
    db.session.commit()
    return jsonify(t.to_dict())
