"""Blueprint Module IC — Conseil / Pipeline / KYC (réf. IC-01→IC-06)."""
from datetime import date as date_type
from flask import Blueprint, jsonify, request, abort
from app import db
from app.models import (
    Entite, Dossier, EtapeDossier, Apporteur,
    ContratCommission, NiveauCommission, Commission, PieceDossier,
)
from app.context import current_entite, current_role, is_consolidé, module_autorise

conseil_bp = Blueprint('conseil', __name__, url_prefix='/api/conseil')

MODULE = 'conseil'
OWNER  = 'IC'

STATUTS_PIPELINE = ['prospect', 'en_cours', 'valide', 'rejete']


def _check_read():
    if not module_autorise(MODULE):
        abort(403)


def _ic_entite():
    if not module_autorise(MODULE):
        return None, jsonify({'error': 'Module réservé à IC'}), 403
    if is_consolidé():
        return None, jsonify({'error': 'Opération de saisie impossible en vue consolidée'}), 400
    code = current_entite()
    if code != OWNER:
        return None, jsonify({'error': 'Module réservé à IC'}), 403
    entite = Entite.query.filter_by(code=OWNER).first()
    if not entite:
        return None, jsonify({'error': 'Entité IC introuvable'}), 400
    return entite, None, None


def _scope(model):
    if is_consolidé():
        return model.query
    entite = Entite.query.filter_by(code=OWNER).first()
    if entite:
        return model.query.filter_by(entite_id=entite.id)
    return model.query.filter_by(entite_id=-1)


# ── Pipeline / Dossiers ───────────────────────────────────────────────────────

@conseil_bp.route('/dossiers', methods=['GET'])
def get_dossiers():
    _check_read()
    q = _scope(Dossier)
    if s := request.args.get('statut'):
        q = q.filter(Dossier.statut == s)
    return jsonify([d.to_dict() for d in q.order_by(Dossier.date_creation.desc()).all()])


@conseil_bp.route('/dossiers', methods=['POST'])
def create_dossier():
    entite, err, code = _ic_entite()
    if err:
        return err, code
    data = request.get_json(force=True) or {}
    if not data.get('investisseur'):
        return jsonify({'error': 'investisseur requis'}), 400
    d = Dossier(
        entite_id=entite.id,
        investisseur=data['investisseur'],
        statut='prospect',
        montant=data.get('montant'),
        intervenant=data.get('intervenant', current_role()),
        date_creation=date_type.today(),
        date_maj=date_type.today(),
    )
    db.session.add(d)
    db.session.flush()
    db.session.add(EtapeDossier(
        dossier_id=d.id, libelle='Dossier ouvert',
        date=date_type.today(), intervenant=d.intervenant,
        commentaire='Création du dossier',
    ))
    db.session.commit()
    return jsonify(d.to_dict()), 201


@conseil_bp.route('/dossiers/<int:did>', methods=['GET'])
def get_dossier(did):
    _check_read()
    d = Dossier.query.get_or_404(did)
    result = d.to_dict()
    result['pieces'] = [p.to_dict() for p in d.pieces]
    result['commissions'] = [c.to_dict() for c in d.commissions]
    return jsonify(result)


@conseil_bp.route('/dossiers/<int:did>/avancer', methods=['POST'])
def avancer_dossier(did):
    """Fait progresser un dossier dans le pipeline avec contrôle KYC."""
    entite, err, code = _ic_entite()
    if err:
        return err, code
    d = Dossier.query.get_or_404(did)
    if d.entite_id != entite.id:
        abort(403)

    data = request.get_json(force=True) or {}
    nouveau_statut = data.get('statut')
    if nouveau_statut not in STATUTS_PIPELINE:
        return jsonify({'error': f'statut invalide, doit être parmi {STATUTS_PIPELINE}'}), 400

    # Contrôle LCB-FT : un dossier ne peut être validé que si l'apporteur KYC est validé
    if nouveau_statut == 'valide':
        commissions = Commission.query.filter_by(dossier_id=did).all()
        for c in commissions:
            if c.apporteur and c.apporteur.statut_kyc != 'valide':
                return jsonify({
                    'error': f"KYC de l'apporteur {c.apporteur.nom} non validé — validation bloquée (LCB-FT)"
                }), 400

    d.statut = nouveau_statut
    d.date_maj = date_type.today()

    libelle_etape = {
        'en_cours': 'Dossier mis en instruction',
        'valide':   'Dossier validé',
        'rejete':   'Dossier rejeté',
    }.get(nouveau_statut, f'Statut → {nouveau_statut}')

    db.session.add(EtapeDossier(
        dossier_id=did, libelle=libelle_etape,
        date=date_type.today(),
        intervenant=data.get('intervenant', current_role()),
        commentaire=data.get('commentaire'),
    ))
    db.session.commit()
    return jsonify(d.to_dict())


@conseil_bp.route('/dossiers/<int:did>/etapes', methods=['POST'])
def add_etape(did):
    entite, err, code = _ic_entite()
    if err:
        return err, code
    d = Dossier.query.get_or_404(did)
    if d.entite_id != entite.id:
        abort(403)
    data = request.get_json(force=True) or {}
    if not data.get('libelle'):
        return jsonify({'error': 'libelle requis'}), 400
    e = EtapeDossier(
        dossier_id=did, libelle=data['libelle'],
        date=date_type.today(),
        intervenant=data.get('intervenant', current_role()),
        commentaire=data.get('commentaire'),
    )
    db.session.add(e)
    d.date_maj = date_type.today()
    db.session.commit()
    return jsonify(e.to_dict()), 201


# ── Apporteurs & KYC ─────────────────────────────────────────────────────────

@conseil_bp.route('/apporteurs', methods=['GET'])
def get_apporteurs():
    _check_read()
    q = _scope(Apporteur)
    if s := request.args.get('statut_kyc'):
        q = q.filter(Apporteur.statut_kyc == s)
    return jsonify([a.to_dict() for a in q.all()])


@conseil_bp.route('/apporteurs', methods=['POST'])
def create_apporteur():
    entite, err, code = _ic_entite()
    if err:
        return err, code
    data = request.get_json(force=True) or {}
    if not data.get('nom'):
        return jsonify({'error': 'Nom requis'}), 400
    a = Apporteur(
        entite_id=entite.id, nom=data['nom'],
        telephone=data.get('telephone'), email=data.get('email'),
        statut_kyc='en_attente',
    )
    db.session.add(a)
    db.session.commit()
    return jsonify(a.to_dict()), 201


@conseil_bp.route('/apporteurs/<int:aid>/kyc', methods=['PUT'])
def update_kyc(aid):
    """Valide ou rejette le KYC d'un apporteur (rôle Valideur ou Direction)."""
    entite, err, code = _ic_entite()
    if err:
        return err, code
    if current_role() not in ('Valideur', 'Direction', 'Comptable'):
        return jsonify({'error': 'Rôle Valideur ou Direction requis'}), 403
    a = Apporteur.query.get_or_404(aid)
    if a.entite_id != entite.id:
        abort(403)
    data = request.get_json(force=True) or {}
    if data.get('statut_kyc') in ('valide', 'rejete', 'en_attente'):
        a.statut_kyc = data['statut_kyc']
        a.date_kyc = date_type.today() if data['statut_kyc'] == 'valide' else None
    db.session.commit()
    return jsonify(a.to_dict())


# ── Contrats de commissionnement ──────────────────────────────────────────────

@conseil_bp.route('/contrats', methods=['GET'])
def get_contrats():
    _check_read()
    return jsonify([c.to_dict() for c in _scope(ContratCommission).all()])


@conseil_bp.route('/contrats', methods=['POST'])
def create_contrat():
    entite, err, code = _ic_entite()
    if err:
        return err, code
    data = request.get_json(force=True) or {}
    if not data.get('apporteur_id'):
        return jsonify({'error': 'apporteur_id requis'}), 400
    c = ContratCommission(
        entite_id=entite.id, apporteur_id=data['apporteur_id'],
        description=data.get('description'),
    )
    db.session.add(c)
    db.session.flush()
    for niv in data.get('niveaux', []):
        db.session.add(NiveauCommission(
            contrat_id=c.id,
            niveau=niv['niveau'], taux=niv['taux'],
            description=niv.get('description'),
        ))
    db.session.commit()
    return jsonify(c.to_dict()), 201


# ── Commissions ───────────────────────────────────────────────────────────────

@conseil_bp.route('/commissions', methods=['GET'])
def get_commissions():
    _check_read()
    q = _scope(Commission)
    if did := request.args.get('dossier_id'):
        q = q.filter(Commission.dossier_id == int(did))
    return jsonify([c.to_dict() for c in q.all()])


@conseil_bp.route('/commissions/calculer/<int:dossier_id>', methods=['POST'])
def calculer_commissions(dossier_id):
    """Calcule automatiquement les commissions multi-niveaux sur un dossier."""
    entite, err, code = _ic_entite()
    if err:
        return err, code

    dossier = Dossier.query.get_or_404(dossier_id)
    if dossier.entite_id != entite.id:
        abort(403)
    if not dossier.montant:
        return jsonify({'error': 'Le dossier doit avoir un montant pour calculer les commissions'}), 400

    data = request.get_json(force=True) or {}
    apporteur_id = data.get('apporteur_id')
    if not apporteur_id:
        return jsonify({'error': 'apporteur_id requis'}), 400

    contrat = ContratCommission.query.filter_by(
        entite_id=entite.id, apporteur_id=apporteur_id
    ).first()
    if not contrat:
        return jsonify({'error': 'Pas de contrat de commission pour cet apporteur'}), 404

    created = []
    for niv in contrat.niveaux:
        montant = float(dossier.montant) * float(niv.taux) / 100
        c = Commission(
            entite_id=entite.id, dossier_id=dossier_id,
            apporteur_id=apporteur_id,
            niveau=niv.niveau, taux=float(niv.taux),
            montant=montant, statut='calculee',
        )
        db.session.add(c)
        created.append(c)

    db.session.commit()
    return jsonify([c.to_dict() for c in created]), 201


@conseil_bp.route('/commissions/<int:cid>/verser', methods=['POST'])
def verser_commission(cid):
    entite, err, code = _ic_entite()
    if err:
        return err, code
    c = Commission.query.get_or_404(cid)
    if c.entite_id != entite.id:
        abort(403)
    c.statut = 'versee'
    db.session.commit()
    return jsonify(c.to_dict())


# ── Pièces / GED ──────────────────────────────────────────────────────────────

@conseil_bp.route('/dossiers/<int:did>/pieces', methods=['GET'])
def get_pieces(did):
    _check_read()
    return jsonify([p.to_dict() for p in PieceDossier.query.filter_by(dossier_id=did).all()])


@conseil_bp.route('/dossiers/<int:did>/pieces', methods=['POST'])
def add_piece(did):
    entite, err, code = _ic_entite()
    if err:
        return err, code
    d = Dossier.query.get_or_404(did)
    if d.entite_id != entite.id:
        abort(403)
    data = request.get_json(force=True) or {}
    p = PieceDossier(
        dossier_id=did,
        nom_fichier=data.get('nom_fichier', 'document'),
        type=data.get('type', 'autre'),
        date_upload=date_type.today(),
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201


# ── Reporting AMF-UMOA ────────────────────────────────────────────────────────

@conseil_bp.route('/reporting-amf', methods=['GET'])
def reporting_amf():
    _check_read()
    entite = Entite.query.filter_by(code=OWNER).first()
    if not entite:
        return jsonify({'error': 'Entité IC introuvable'}), 404

    dossiers = Dossier.query.filter_by(entite_id=entite.id).all()
    apporteurs = Apporteur.query.filter_by(entite_id=entite.id).all()

    stats_statuts = {'prospect': 0, 'en_cours': 0, 'valide': 0, 'rejete': 0}
    montant_total = 0
    for d in dossiers:
        stats_statuts[d.statut] = stats_statuts.get(d.statut, 0) + 1
        if d.montant:
            montant_total += float(d.montant)

    stats_kyc = {'en_attente': 0, 'valide': 0, 'rejete': 0}
    for a in apporteurs:
        stats_kyc[a.statut_kyc] = stats_kyc.get(a.statut_kyc, 0) + 1

    commissions = Commission.query.filter_by(entite_id=entite.id).all()
    commissions_total = sum(float(c.montant or 0) for c in commissions)

    return jsonify({
        'date_rapport': date_type.today().isoformat(),
        'entite': 'IC — ISF Conseil',
        'dossiers': {
            'total': len(dossiers),
            'par_statut': stats_statuts,
            'montant_total': montant_total,
        },
        'apporteurs': {
            'total': len(apporteurs),
            'statuts_kyc': stats_kyc,
        },
        'commissions': {
            'total': len(commissions),
            'montant_total': commissions_total,
            'versees': sum(1 for c in commissions if c.statut == 'versee'),
        },
        'tracabilite': [
            {'dossier_id': d.id, 'investisseur': d.investisseur,
             'statut': d.statut, 'nb_etapes': len(d.etapes),
             'date_creation': d.date_creation.isoformat() if d.date_creation else None}
            for d in dossiers
        ],
    })
