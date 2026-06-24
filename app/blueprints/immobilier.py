"""Blueprint Module AC — Immobilier / VEFA (réf. AC-01→AC-55)."""
from datetime import date as date_type
from flask import Blueprint, jsonify, request, abort
from app import db
from app.models import (
    Entite, Prospect, ProjetImmobilier, Souscription, Acquereur,
    ProgrammeVEFA, TrancheVEFA, AppelFonds, GFA, EcheancierAcquereur,
    Ecriture, LigneEcriture, Compte, Journal, Tiers,
)
from app.context import current_entite, current_role, is_consolidé, module_autorise

immobilier_bp = Blueprint('immobilier', __name__, url_prefix='/api/immobilier')

MODULE = 'immobilier'
OWNER  = 'AC'


def _check_read():
    if not module_autorise(MODULE):
        abort(403)


def _ac_entite():
    """Retourne l'entité AC ou une erreur 403/400 si contexte inadapté."""
    if not module_autorise(MODULE):
        return None, jsonify({'error': 'Module réservé à AC'}), 403
    if is_consolidé():
        return None, jsonify({'error': 'Opération de saisie impossible en vue consolidée'}), 400
    code = current_entite()
    if code != OWNER:
        return None, jsonify({'error': 'Module réservé à AC'}), 403
    entite = Entite.query.filter_by(code=OWNER).first()
    if not entite:
        return None, jsonify({'error': 'Entité AC introuvable'}), 400
    return entite, None, None


def _scope(model):
    if is_consolidé():
        return model.query
    entite = Entite.query.filter_by(code=OWNER).first()
    if entite:
        return model.query.filter_by(entite_id=entite.id)
    return model.query.filter_by(entite_id=-1)


# ── Prospects ────────────────────────────────────────────────────────────────

@immobilier_bp.route('/prospects', methods=['GET'])
def get_prospects():
    _check_read()
    q = _scope(Prospect)
    if s := request.args.get('statut'):
        q = q.filter(Prospect.statut == s)
    return jsonify([p.to_dict() for p in q.all()])


@immobilier_bp.route('/prospects', methods=['POST'])
def create_prospect():
    entite, err, code = _ac_entite()
    if err:
        return err, code
    data = request.get_json(force=True) or {}
    if not data.get('nom'):
        return jsonify({'error': 'Nom requis'}), 400
    p = Prospect(entite_id=entite.id, nom=data['nom'],
                 telephone=data.get('telephone'), email=data.get('email'),
                 projet_interet=data.get('projet_interet'), statut='en_cours')
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201


@immobilier_bp.route('/prospects/<int:pid>/statut', methods=['PUT'])
def update_prospect_statut(pid):
    entite, err, code = _ac_entite()
    if err:
        return err, code
    p = Prospect.query.get_or_404(pid)
    if p.entite_id != entite.id:
        abort(403)
    data = request.get_json(force=True) or {}
    if data.get('statut') in ('en_cours', 'converti', 'perdu'):
        p.statut = data['statut']
    db.session.commit()
    return jsonify(p.to_dict())


# ── Projets ──────────────────────────────────────────────────────────────────

@immobilier_bp.route('/projets', methods=['GET'])
def get_projets():
    _check_read()
    return jsonify([p.to_dict() for p in _scope(ProjetImmobilier).all()])


@immobilier_bp.route('/projets', methods=['POST'])
def create_projet():
    entite, err, code = _ac_entite()
    if err:
        return err, code
    data = request.get_json(force=True) or {}
    if not data.get('nom') or not data.get('code'):
        return jsonify({'error': 'code et nom requis'}), 400
    proj = ProjetImmobilier(
        entite_id=entite.id, code=data['code'], nom=data['nom'],
        axe_analytique=data.get('axe_analytique', data['code']),
        budget=data.get('budget', 0), statut='en_cours',
    )
    db.session.add(proj)
    db.session.commit()
    return jsonify(proj.to_dict()), 201


@immobilier_bp.route('/projets/<int:pid>', methods=['GET'])
def get_projet(pid):
    _check_read()
    proj = ProjetImmobilier.query.get_or_404(pid)
    d = proj.to_dict()
    # Charges analytiques (lignes écriture avec axe = code projet)
    charges = (LigneEcriture.query
               .filter(LigneEcriture.axe_analytique == proj.axe_analytique)
               .all())
    total_charges = sum(float(c.debit) for c in charges)
    d['total_charges'] = total_charges
    d['marge_brute'] = float(proj.budget) - total_charges
    return jsonify(d)


# ── Souscriptions ─────────────────────────────────────────────────────────────

@immobilier_bp.route('/souscriptions', methods=['GET'])
def get_souscriptions():
    _check_read()
    q = _scope(Souscription)
    if pid := request.args.get('projet_id'):
        q = q.filter(Souscription.projet_id == int(pid))
    return jsonify([s.to_dict() for s in q.all()])


@immobilier_bp.route('/souscriptions', methods=['POST'])
def create_souscription():
    entite, err, code = _ac_entite()
    if err:
        return err, code
    data = request.get_json(force=True) or {}
    if not data.get('client_id') or not data.get('projet_id') or not data.get('montant'):
        return jsonify({'error': 'client_id, projet_id et montant requis'}), 400
    s = Souscription(
        entite_id=entite.id, client_id=data['client_id'],
        projet_id=data['projet_id'], montant=data['montant'], statut='active',
    )
    db.session.add(s)
    db.session.commit()
    return jsonify(s.to_dict()), 201


# ── Acquéreurs ────────────────────────────────────────────────────────────────

@immobilier_bp.route('/acquereurs', methods=['GET'])
def get_acquereurs():
    _check_read()
    return jsonify([a.to_dict() for a in _scope(Acquereur).all()])


@immobilier_bp.route('/acquereurs', methods=['POST'])
def create_acquereur():
    entite, err, code = _ac_entite()
    if err:
        return err, code
    data = request.get_json(force=True) or {}
    if not data.get('nom'):
        return jsonify({'error': 'Nom requis'}), 400
    a = Acquereur(entite_id=entite.id, nom=data['nom'],
                  telephone=data.get('telephone'), email=data.get('email'))
    db.session.add(a)
    db.session.commit()
    return jsonify(a.to_dict()), 201


# ── Programmes VEFA ───────────────────────────────────────────────────────────

@immobilier_bp.route('/programmes', methods=['GET'])
def get_programmes():
    _check_read()
    return jsonify([p.to_dict() for p in _scope(ProgrammeVEFA).all()])


@immobilier_bp.route('/programmes', methods=['POST'])
def create_programme():
    entite, err, code = _ac_entite()
    if err:
        return err, code
    data = request.get_json(force=True) or {}
    if not data.get('nom') or not data.get('projet_id'):
        return jsonify({'error': 'nom et projet_id requis'}), 400
    prog = ProgrammeVEFA(
        entite_id=entite.id, projet_id=data['projet_id'],
        nom=data['nom'], nb_lots=data.get('nb_lots', 0),
    )
    db.session.add(prog)
    db.session.flush()
    for t in data.get('tranches', []):
        db.session.add(TrancheVEFA(
            programme_id=prog.id, libelle=t['libelle'],
            pct_avancement=t['pct_avancement'], statut='en_attente',
        ))
    db.session.commit()
    return jsonify(prog.to_dict()), 201


@immobilier_bp.route('/programmes/<int:pid>', methods=['GET'])
def get_programme(pid):
    _check_read()
    prog = ProgrammeVEFA.query.get_or_404(pid)
    d = prog.to_dict()
    d['echeanciers'] = [e.to_dict() for e in
                        EcheancierAcquereur.query.filter_by(programme_id=pid).all()]
    return jsonify(d)


# ── Appels de fonds ───────────────────────────────────────────────────────────

@immobilier_bp.route('/appels-fonds', methods=['GET'])
def get_appels_fonds():
    _check_read()
    q = _scope(AppelFonds)
    if s := request.args.get('statut'):
        q = q.filter(AppelFonds.statut == s)
    return jsonify([a.to_dict() for a in q.all()])


@immobilier_bp.route('/appels-fonds', methods=['POST'])
def create_appel_fonds():
    entite, err, code = _ac_entite()
    if err:
        return err, code
    data = request.get_json(force=True) or {}
    if not all(k in data for k in ('tranche_id', 'acquereur_id', 'montant')):
        return jsonify({'error': 'tranche_id, acquereur_id et montant requis'}), 400
    af = AppelFonds(
        entite_id=entite.id, tranche_id=data['tranche_id'],
        acquereur_id=data['acquereur_id'], montant=data['montant'], statut='emis',
    )
    db.session.add(af)
    db.session.commit()
    return jsonify(af.to_dict()), 201


@immobilier_bp.route('/appels-fonds/<int:aid>/encaisser', methods=['POST'])
def encaisser_appel(aid):
    """Encaissement d'un appel de fonds → avance client 4191 (avant livraison)."""
    entite, err, code = _ac_entite()
    if err:
        return err, code
    af = AppelFonds.query.get_or_404(aid)
    if af.entite_id != entite.id:
        abort(403)
    if af.statut == 'encaisse':
        return jsonify({'error': 'Déjà encaissé'}), 400

    c4191 = Compte.query.filter_by(numero='4191').first()
    c521  = Compte.query.filter_by(numero='521').first()
    journal = Journal.query.filter_by(entite_id=entite.id, code='BQ').first()

    if not c4191 or not c521 or not journal:
        return jsonify({'error': 'Compte 4191, 521 ou journal BQ manquant'}), 500

    tranche = TrancheVEFA.query.get(af.tranche_id)
    prog_nom = tranche.programme.nom if tranche and tranche.programme else 'VEFA'
    libelle = f"Appel de fonds — {af.acquereur.nom} — {prog_nom}"

    ecriture = Ecriture(
        entite_id=entite.id, journal_id=journal.id,
        date=date_type.today(), libelle=libelle,
        reference=f'AF-{aid}', source='immobilier', statut='validee',
        cree_par=current_role(),
    )
    db.session.add(ecriture)
    db.session.flush()

    montant = float(af.montant)
    db.session.add(LigneEcriture(ecriture_id=ecriture.id, compte_id=c521.id,
                                  libelle=libelle, debit=montant, credit=0))
    db.session.add(LigneEcriture(ecriture_id=ecriture.id, compte_id=c4191.id,
                                  libelle=libelle, debit=0, credit=montant,
                                  axe_analytique=tranche.programme.projet.axe_analytique
                                  if tranche and tranche.programme and tranche.programme.projet
                                  else None))

    af.statut = 'encaisse'
    af.ecriture_id = ecriture.id
    db.session.commit()
    return jsonify({'message': 'Encaissé', 'ecriture_id': ecriture.id, 'appel': af.to_dict()})


# ── CA à l'avancement ─────────────────────────────────────────────────────────

@immobilier_bp.route('/tranches/<int:tid>/reconnaitre-ca', methods=['POST'])
def reconnaitre_ca(tid):
    """Reconnaît le CA à l'avancement sur une tranche (débit 4191 / crédit 706)."""
    entite, err, code = _ac_entite()
    if err:
        return err, code
    tranche = TrancheVEFA.query.get_or_404(tid)

    encaisses = [af for af in tranche.appels_fonds if af.statut == 'encaisse']
    montant_ca = sum(float(af.montant) for af in encaisses)
    if montant_ca <= 0:
        return jsonify({'error': 'Aucun encaissement sur cette tranche'}), 400

    c4191 = Compte.query.filter_by(numero='4191').first()
    c706  = Compte.query.filter_by(numero='706').first()
    journal = Journal.query.filter_by(entite_id=entite.id, code='VE').first()

    if not c4191 or not c706 or not journal:
        return jsonify({'error': 'Comptes 4191/706 ou journal VE manquant'}), 500

    axe = (tranche.programme.projet.axe_analytique
           if tranche.programme and tranche.programme.projet else None)
    libelle = f"CA avancement {float(tranche.pct_avancement)}% — {tranche.libelle}"

    ecriture = Ecriture(
        entite_id=entite.id, journal_id=journal.id,
        date=date_type.today(), libelle=libelle,
        reference=f'CA-T{tid}', source='immobilier', statut='validee',
        cree_par=current_role(),
    )
    db.session.add(ecriture)
    db.session.flush()

    db.session.add(LigneEcriture(ecriture_id=ecriture.id, compte_id=c4191.id,
                                  libelle=libelle, debit=montant_ca, credit=0,
                                  axe_analytique=axe))
    db.session.add(LigneEcriture(ecriture_id=ecriture.id, compte_id=c706.id,
                                  libelle=libelle, debit=0, credit=montant_ca,
                                  axe_analytique=axe))

    tranche.statut = 'livre'
    db.session.commit()
    return jsonify({'message': 'CA reconnu', 'ecriture_id': ecriture.id,
                    'montant_ca': montant_ca})


# ── GFA ───────────────────────────────────────────────────────────────────────

@immobilier_bp.route('/gfa', methods=['GET'])
def get_gfa():
    _check_read()
    q = _scope(GFA)
    return jsonify([g.to_dict() for g in q.all()])


@immobilier_bp.route('/gfa', methods=['POST'])
def create_gfa():
    entite, err, code = _ac_entite()
    if err:
        return err, code
    data = request.get_json(force=True) or {}
    if not data.get('programme_id') or not data.get('montant'):
        return jsonify({'error': 'programme_id et montant requis'}), 400
    g = GFA(entite_id=entite.id, programme_id=data['programme_id'],
            montant=data['montant'], organisme=data.get('organisme'),
            statut=data.get('statut', 'en_attente'))
    db.session.add(g)
    db.session.commit()
    return jsonify(g.to_dict()), 201


# ── Échéanciers ───────────────────────────────────────────────────────────────

@immobilier_bp.route('/echeanciers', methods=['GET'])
def get_echeanciers():
    _check_read()
    q = EcheancierAcquereur.query
    if aid := request.args.get('acquereur_id'):
        q = q.filter(EcheancierAcquereur.acquereur_id == int(aid))
    if pid := request.args.get('programme_id'):
        q = q.filter(EcheancierAcquereur.programme_id == int(pid))
    return jsonify([e.to_dict() for e in q.all()])


@immobilier_bp.route('/echeanciers', methods=['POST'])
def create_echeancier():
    entite, err, code = _ac_entite()
    if err:
        return err, code
    data = request.get_json(force=True) or {}
    from datetime import date as _date
    e = EcheancierAcquereur(
        acquereur_id=data['acquereur_id'], programme_id=data['programme_id'],
        echeance=_date.fromisoformat(data['echeance']),
        montant=data['montant'], statut='en_attente',
    )
    db.session.add(e)
    db.session.commit()
    return jsonify(e.to_dict()), 201


# ── Reporting projet ──────────────────────────────────────────────────────────

@immobilier_bp.route('/reporting/<int:projet_id>', methods=['GET'])
def reporting_projet(projet_id):
    _check_read()
    proj = ProjetImmobilier.query.get_or_404(projet_id)

    charges = (LigneEcriture.query
               .filter(LigneEcriture.axe_analytique == proj.axe_analytique)
               .all())
    total_charges = sum(float(c.debit) for c in charges)

    # Encaissements (appels de fonds encaissés sur les tranches du programme)
    encaissements = 0
    for prog in proj.programmes:
        for tranche in prog.tranches:
            for af in tranche.appels_fonds:
                if af.statut == 'encaisse':
                    encaissements += float(af.montant)

    souscriptions_total = sum(float(s.montant) for s in proj.souscriptions if s.statut == 'active')

    return jsonify({
        'projet': proj.to_dict(),
        'budget': float(proj.budget),
        'total_charges': total_charges,
        'marge_brute': float(proj.budget) - total_charges,
        'souscriptions_total': souscriptions_total,
        'encaissements': encaissements,
        'tresorerie_nette': encaissements - total_charges,
    })
