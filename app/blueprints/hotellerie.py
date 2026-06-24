"""Blueprint Module SW — Hôtellerie / USALI (réf. SW-01→SW-26)."""
import csv
import io
from datetime import date as date_type
from flask import Blueprint, jsonify, request, abort
from app import db
from app.models import (
    Entite, ImportPMS, LigneVenteSW, PreEcritureSW,
    Ecriture, LigneEcriture, Compte, Journal,
)
from app.context import current_entite, current_role, is_consolidé, module_autorise

hotellerie_bp = Blueprint('hotellerie', __name__, url_prefix='/api/hotellerie')

MODULE = 'hotellerie'
OWNER  = 'SW'

# Mapping département → compte produit (701=hébergt, 706=services)
DEPT_COMPTES = {
    'hebergement': '701',
    'restauration': '701',
    'wellness':     '706',
}


def _check_read():
    if not module_autorise(MODULE):
        abort(403)


def _sw_entite():
    if not module_autorise(MODULE):
        return None, jsonify({'error': 'Module réservé à SW'}), 403
    if is_consolidé():
        return None, jsonify({'error': 'Opération de saisie impossible en vue consolidée'}), 400
    code = current_entite()
    if code != OWNER:
        return None, jsonify({'error': 'Module réservé à SW'}), 403
    entite = Entite.query.filter_by(code=OWNER).first()
    if not entite:
        return None, jsonify({'error': 'Entité SW introuvable'}), 400
    return entite, None, None


def _scope(model):
    if is_consolidé():
        return model.query
    entite = Entite.query.filter_by(code=OWNER).first()
    if entite:
        return model.query.filter_by(entite_id=entite.id)
    return model.query.filter_by(entite_id=-1)


# ── Imports PMS/POS ───────────────────────────────────────────────────────────

@hotellerie_bp.route('/imports', methods=['GET'])
def get_imports():
    _check_read()
    q = _scope(ImportPMS)
    if s := request.args.get('statut'):
        q = q.filter(ImportPMS.statut == s)
    return jsonify([i.to_dict() for i in q.order_by(ImportPMS.date.desc()).all()])


@hotellerie_bp.route('/imports/<int:iid>', methods=['GET'])
def get_import(iid):
    _check_read()
    imp = ImportPMS.query.get_or_404(iid)
    d = imp.to_dict()
    d['pre_ecritures'] = [p.to_dict() for p in imp.pre_ecritures]
    return jsonify(d)


@hotellerie_bp.route('/imports', methods=['POST'])
def create_import():
    """Import de données PMS/POS depuis un payload JSON (simulation CSV)."""
    entite, err, code = _sw_entite()
    if err:
        return err, code

    data = request.get_json(force=True) or {}
    if not data.get('date') or not data.get('source'):
        return jsonify({'error': 'date et source requis'}), 400

    from datetime import date as _d
    imp = ImportPMS(
        entite_id=entite.id,
        date=_d.fromisoformat(data['date']),
        source=data['source'],
        statut='importe',
        nom_fichier=data.get('nom_fichier', 'saisie_manuelle'),
    )
    db.session.add(imp)
    db.session.flush()

    for ligne in data.get('lignes', []):
        db.session.add(LigneVenteSW(
            import_id=imp.id,
            departement=ligne['departement'],
            libelle=ligne.get('libelle', ''),
            montant_ht=ligne['montant_ht'],
            tva=ligne.get('tva', 0),
        ))

    db.session.commit()
    return jsonify(imp.to_dict()), 201


@hotellerie_bp.route('/imports/csv', methods=['POST'])
def import_csv():
    """Upload d'un fichier CSV PMS/POS."""
    entite, err, code = _sw_entite()
    if err:
        return err, code

    if 'file' not in request.files:
        return jsonify({'error': 'Fichier CSV requis'}), 400

    f = request.files['file']
    content = f.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(content))

    from datetime import date as _d
    imp = ImportPMS(
        entite_id=entite.id,
        date=_d.today(),
        source=request.form.get('source', 'PMS'),
        statut='importe',
        nom_fichier=f.filename,
    )
    db.session.add(imp)
    db.session.flush()

    count = 0
    for row in reader:
        dept = row.get('departement', '').strip().lower()
        if dept not in ('hebergement', 'restauration', 'wellness'):
            dept = 'hebergement'
        try:
            montant_ht = float(row.get('montant_ht', 0))
            tva        = float(row.get('tva', 0))
        except ValueError:
            continue
        db.session.add(LigneVenteSW(
            import_id=imp.id,
            departement=dept,
            libelle=row.get('libelle', ''),
            montant_ht=montant_ht,
            tva=tva,
        ))
        count += 1

    db.session.commit()
    return jsonify({'import': imp.to_dict(), 'lignes_importees': count}), 201


@hotellerie_bp.route('/imports/<int:iid>/generer-pre-ecritures', methods=['POST'])
def generer_pre_ecritures(iid):
    """Génère des pré-écritures contrôlables depuis un import PMS."""
    entite, err, code = _sw_entite()
    if err:
        return err, code
    imp = ImportPMS.query.get_or_404(iid)
    if imp.entite_id != entite.id:
        abort(403)
    if imp.statut != 'importe':
        return jsonify({'error': 'Import déjà contrôlé ou comptabilisé'}), 400

    # Agrégation par département
    dept_totaux = {}
    for ligne in imp.lignes:
        dept = ligne.departement
        dept_totaux.setdefault(dept, {'ht': 0, 'tva': 0})
        dept_totaux[dept]['ht'] += float(ligne.montant_ht)
        dept_totaux[dept]['tva'] += float(ligne.tva or 0)

    pre_ecritures = []
    for dept, montants in dept_totaux.items():
        ht  = montants['ht']
        tva = montants['tva']
        cpte_produit = DEPT_COMPTES.get(dept, '706')

        # 411 / 70x
        pe1 = PreEcritureSW(import_id=imp.id,
                            compte_debit='411', compte_credit=cpte_produit,
                            montant=ht,
                            libelle=f'Revenus {dept} — {imp.nom_fichier}',
                            statut='a_valider')
        db.session.add(pe1)
        pre_ecritures.append(pe1)

        # TVA si non nulle
        if tva > 0:
            pe2 = PreEcritureSW(import_id=imp.id,
                               compte_debit='411', compte_credit='443',
                               montant=tva,
                               libelle=f'TVA {dept} — {imp.nom_fichier}',
                               statut='a_valider')
            db.session.add(pe2)
            pre_ecritures.append(pe2)

    imp.statut = 'controle'
    db.session.commit()
    return jsonify({'pre_ecritures': [p.to_dict() for p in pre_ecritures]})


@hotellerie_bp.route('/pre-ecritures', methods=['GET'])
def list_pre_ecritures():
    _check_read()
    statut = request.args.get('statut')
    imports_q = _scope(ImportPMS)
    import_ids = [i.id for i in imports_q.all()]
    q = PreEcritureSW.query.filter(PreEcritureSW.import_id.in_(import_ids))
    if statut:
        q = q.filter(PreEcritureSW.statut == statut)
    pes = q.order_by(PreEcritureSW.id.desc()).all()
    return jsonify([pe.to_dict() for pe in pes])


@hotellerie_bp.route('/pre-ecritures/<int:pid>/valider', methods=['POST'])
def valider_pre_ecriture(pid):
    entite, err, code = _sw_entite()
    if err:
        return err, code
    if current_role() not in ('Comptable', 'Direction'):
        return jsonify({'error': 'Rôle Comptable ou Direction requis'}), 403
    pe = PreEcritureSW.query.get_or_404(pid)
    pe.statut = 'valide'
    db.session.commit()
    return jsonify(pe.to_dict())


@hotellerie_bp.route('/imports/<int:iid>/comptabiliser', methods=['POST'])
def comptabiliser_import(iid):
    """Comptabilise les pré-écritures validées dans le journal VE de SW."""
    entite, err, code = _sw_entite()
    if err:
        return err, code
    if current_role() not in ('Comptable', 'Direction'):
        return jsonify({'error': 'Rôle Comptable ou Direction requis'}), 403

    imp = ImportPMS.query.get_or_404(iid)
    if imp.entite_id != entite.id:
        abort(403)
    if imp.statut == 'comptabilise':
        return jsonify({'error': 'Déjà comptabilisé'}), 400

    valides = [pe for pe in imp.pre_ecritures if pe.statut == 'valide']
    if not valides:
        return jsonify({'error': 'Aucune pré-écriture validée'}), 400

    journal = Journal.query.filter_by(entite_id=entite.id, code='VE').first()
    if not journal:
        return jsonify({'error': 'Journal VE SW introuvable'}), 500

    ecriture = Ecriture(
        entite_id=entite.id, journal_id=journal.id,
        date=imp.date,
        libelle=f'Import PMS/POS {imp.source} — {imp.nom_fichier}',
        reference=f'PMS-{imp.id}', source='hotellerie', statut='validee',
        cree_par=current_role(),
    )
    db.session.add(ecriture)
    db.session.flush()

    compte_cache = {}
    def _get_compte(num):
        if num not in compte_cache:
            compte_cache[num] = Compte.query.filter_by(numero=num).first()
        return compte_cache[num]

    for pe in valides:
        cd = _get_compte(pe.compte_debit)
        cc = _get_compte(pe.compte_credit)
        if cd and cc:
            montant = float(pe.montant or 0)
            db.session.add(LigneEcriture(ecriture_id=ecriture.id, compte_id=cd.id,
                                          libelle=pe.libelle, debit=montant, credit=0))
            db.session.add(LigneEcriture(ecriture_id=ecriture.id, compte_id=cc.id,
                                          libelle=pe.libelle, debit=0, credit=montant))

    imp.statut = 'comptabilise'
    imp.ecriture_id = ecriture.id
    db.session.commit()
    return jsonify({'ecriture_id': ecriture.id, 'message': 'Comptabilisé'})


# ── Reporting USALI ───────────────────────────────────────────────────────────

@hotellerie_bp.route('/reporting-usali', methods=['GET'])
def reporting_usali():
    _check_read()
    entite = Entite.query.filter_by(code=OWNER).first()
    if not entite:
        return jsonify({'error': 'Entité SW introuvable'}), 404

    periode = request.args.get('periode')  # ex: '2026-01'

    q = ImportPMS.query.filter_by(entite_id=entite.id, statut='comptabilise')
    if periode:
        annee, mois = periode.split('-')
        q = q.filter(
            db.func.strftime('%Y', ImportPMS.date) == annee,
            db.func.strftime('%m', ImportPMS.date) == mois.zfill(2),
        )

    imports = q.all()
    dept_totaux = {'hebergement': 0, 'restauration': 0, 'wellness': 0}

    for imp in imports:
        for ligne in imp.lignes:
            dept = ligne.departement
            if dept in dept_totaux:
                dept_totaux[dept] += float(ligne.montant_ht)

    total = sum(dept_totaux.values())
    repartition = {dept: {'montant': v, 'pct': round(v / total * 100, 1) if total > 0 else 0}
                   for dept, v in dept_totaux.items()}

    return jsonify({
        'periode': periode or 'tout',
        'nb_imports': len(imports),
        'total_revenus': total,
        'repartition': repartition,
    })
