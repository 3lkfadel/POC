from datetime import date as date_type, datetime
from flask import Blueprint, jsonify, request
from sqlalchemy import func
from app import db
from app.models import Compte, Journal, Ecriture, LigneEcriture, Entite
from app.context import current_entite, current_role, is_consolidé

compta_bp = Blueprint('compta', __name__, url_prefix='/api')


# ── Plan comptable ─────────────────────────────────────────────────────────

@compta_bp.route('/comptes')
def get_comptes():
    q = request.args.get('q', '').strip()
    query = Compte.query
    if q:
        query = query.filter(
            db.or_(Compte.numero.ilike(f'{q}%'), Compte.libelle.ilike(f'%{q}%'))
        )
    return jsonify([c.to_dict() for c in query.order_by(Compte.numero).all()])


# ── Journaux ───────────────────────────────────────────────────────────────

@compta_bp.route('/journaux')
def get_journaux():
    if is_consolidé():
        rows = Journal.query.order_by(Journal.code).all()
    else:
        code = current_entite()
        entite = Entite.query.filter_by(code=code).first()
        rows = Journal.query.filter_by(entite_id=entite.id).order_by(Journal.code).all() if entite else []
    return jsonify([j.to_dict() for j in rows])


# ── Écritures — création ───────────────────────────────────────────────────

@compta_bp.route('/ecritures', methods=['POST'])
def create_ecriture():
    data = request.get_json(force=True) or {}
    lignes = data.get('lignes', [])

    if not lignes:
        return jsonify({'error': 'Au moins une ligne requise'}), 400

    total_d = round(sum(float(l.get('debit',  0)) for l in lignes), 2)
    total_c = round(sum(float(l.get('credit', 0)) for l in lignes), 2)
    if total_d != total_c:
        return jsonify({'error': f'Écriture déséquilibrée : débit {total_d:,.0f} ≠ crédit {total_c:,.0f} FCFA'}), 400

    code = current_entite()
    if not code or code == 'CONSOLIDE':
        return jsonify({'error': 'Sélectionnez une filiale (pas Consolidé) pour saisir une écriture'}), 400

    entite = Entite.query.filter_by(code=code).first()
    if not entite:
        return jsonify({'error': 'Entité introuvable'}), 400

    date_str = data.get('date', date_type.today().isoformat())
    e = Ecriture(
        entite_id  = entite.id,
        journal_id = data.get('journal_id'),
        date       = datetime.strptime(date_str, '%Y-%m-%d').date(),
        libelle    = data.get('libelle', ''),
        reference  = data.get('reference', ''),
        source     = 'manuel',
        statut     = 'brouillon',
        cree_par   = data.get('cree_par', current_role()),
    )
    db.session.add(e)
    db.session.flush()

    for l in lignes:
        db.session.add(LigneEcriture(
            ecriture_id = e.id,
            compte_id   = l.get('compte_id'),
            libelle     = l.get('libelle', e.libelle),
            debit       = float(l.get('debit',  0)),
            credit      = float(l.get('credit', 0)),
        ))

    db.session.commit()
    return jsonify(e.to_dict()), 201


# ── Écritures — liste ──────────────────────────────────────────────────────

@compta_bp.route('/ecritures', methods=['GET'])
def get_ecritures():
    if is_consolidé():
        query = Ecriture.query
    else:
        code = current_entite()
        entite = Entite.query.filter_by(code=code).first()
        query = Ecriture.query.filter_by(entite_id=entite.id) if entite else Ecriture.query.filter_by(entite_id=-1)

    if jid := request.args.get('journal_id'):
        query = query.filter(Ecriture.journal_id == int(jid))
    if statut := request.args.get('statut'):
        query = query.filter(Ecriture.statut == statut)

    return jsonify([e.to_dict() for e in query.order_by(Ecriture.date.desc()).all()])


# ── Valider une écriture ───────────────────────────────────────────────────

@compta_bp.route('/ecritures/<int:eid>/valider', methods=['POST'])
def valider_ecriture(eid):
    role = current_role()
    if role not in ('Comptable', 'Valideur', 'Direction'):
        return jsonify({'error': f'Rôle « {role} » non autorisé à valider une écriture'}), 403

    e = db.session.get(Ecriture, eid)
    if not e:
        return jsonify({'error': 'Écriture introuvable'}), 404
    if e.statut == 'validee':
        return jsonify({'error': 'Écriture déjà validée'}), 400

    data = request.get_json(force=True) or {}
    validateur = data.get('validateur', role)

    if validateur == e.cree_par:
        return jsonify({'error': 'Séparation des tâches : vous ne pouvez pas valider votre propre écriture'}), 403

    e.statut     = 'validee'
    e.valide_par = validateur
    db.session.commit()
    return jsonify(e.to_dict())


# ── Grand livre ────────────────────────────────────────────────────────────

@compta_bp.route('/grand-livre')
def grand_livre():
    compte_id = request.args.get('compte_id', type=int)
    if not compte_id:
        return jsonify({'error': 'compte_id requis'}), 400

    compte = db.session.get(Compte, compte_id)
    if not compte:
        return jsonify({'error': 'Compte introuvable'}), 404

    query = (db.session.query(LigneEcriture)
             .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
             .filter(LigneEcriture.compte_id == compte_id))

    if not is_consolidé():
        code = current_entite()
        entite = Entite.query.filter_by(code=code).first()
        if entite:
            query = query.filter(Ecriture.entite_id == entite.id)

    lignes = query.order_by(Ecriture.date).all()
    total_d = sum(float(l.debit)  for l in lignes)
    total_c = sum(float(l.credit) for l in lignes)

    return jsonify({
        'compte':        compte.to_dict(),
        'lignes': [
            {**l.to_dict(),
             'date':             l.ecriture.date.isoformat(),
             'ecriture_libelle': l.ecriture.libelle,
             'journal_code':     l.ecriture.journal.code if l.ecriture.journal else None,
             'entite_code':      l.ecriture.entite.code if l.ecriture.entite else None}
            for l in lignes
        ],
        'total_debit':  total_d,
        'total_credit': total_c,
        'solde':        total_d - total_c,
    })


# ── Balance ────────────────────────────────────────────────────────────────

@compta_bp.route('/balance')
def balance():
    base = (db.session.query(
                Compte.id,
                Compte.numero,
                Compte.libelle,
                Compte.classe,
                func.coalesce(func.sum(LigneEcriture.debit),  0).label('total_debit'),
                func.coalesce(func.sum(LigneEcriture.credit), 0).label('total_credit'),
            )
            .outerjoin(LigneEcriture, LigneEcriture.compte_id == Compte.id)
            .outerjoin(Ecriture, Ecriture.id == LigneEcriture.ecriture_id))

    if not is_consolidé():
        code = current_entite()
        entite = Entite.query.filter_by(code=code).first()
        if entite:
            base = base.filter(
                db.or_(Ecriture.entite_id == entite.id, LigneEcriture.id.is_(None))
            )

    rows = (base.group_by(Compte.id)
                .having(db.or_(func.sum(LigneEcriture.debit) > 0,
                               func.sum(LigneEcriture.credit) > 0))
                .order_by(Compte.numero)
                .all())

    comptes = [{'numero': r.numero, 'libelle': r.libelle, 'classe': r.classe,
                'total_debit': float(r.total_debit), 'total_credit': float(r.total_credit),
                'solde': float(r.total_debit) - float(r.total_credit)} for r in rows]

    return jsonify({
        'entite':              current_entite() or 'CONSOLIDE',
        'comptes':             comptes,
        'grand_total_debit':  sum(r['total_debit']  for r in comptes),
        'grand_total_credit': sum(r['total_credit'] for r in comptes),
    })
