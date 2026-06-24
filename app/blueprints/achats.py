import re as _re
import io as _io
from datetime import date as date_type, datetime, timedelta
from flask import Blueprint, jsonify, request
from app import db
from app.models import (
    DemandeAchat, LigneDA, BonCommande, LigneBC,
    Reception, LigneReception, FactureFournisseur,
    ConfigAchat, Entite, Tiers, Compte, Journal, Ecriture, LigneEcriture
)
from app.context import current_entite, current_role, is_consolidé

achats_bp = Blueprint('achats', __name__, url_prefix='/api')


def _entite_or_400():
    code = current_entite()
    if not code or code == 'CONSOLIDE':
        return None, jsonify({'error': 'Sélectionnez une filiale (pas Consolidé)'}), 400
    entite = Entite.query.filter_by(code=code).first()
    if not entite:
        return None, jsonify({'error': 'Entité introuvable'}), 400
    return entite, None, None


def _scope_da():
    if is_consolidé():
        return DemandeAchat.query
    code = current_entite()
    entite = Entite.query.filter_by(code=code).first()
    return DemandeAchat.query.filter_by(entite_id=entite.id) if entite else DemandeAchat.query.filter_by(entite_id=-1)


def _scope_bc():
    if is_consolidé():
        return BonCommande.query
    code = current_entite()
    entite = Entite.query.filter_by(code=code).first()
    return BonCommande.query.filter_by(entite_id=entite.id) if entite else BonCommande.query.filter_by(entite_id=-1)


def _scope_fact():
    if is_consolidé():
        return FactureFournisseur.query
    code = current_entite()
    entite = Entite.query.filter_by(code=code).first()
    return FactureFournisseur.query.filter_by(entite_id=entite.id) if entite else FactureFournisseur.query.filter_by(entite_id=-1)


# ── Demandes d'achat ──────────────────────────────────────────────────────────

@achats_bp.route('/da', methods=['GET'])
def get_da():
    query = _scope_da()
    if s := request.args.get('statut'):
        query = query.filter(DemandeAchat.statut == s)
    return jsonify([d.to_dict() for d in query.order_by(DemandeAchat.date.desc()).all()])


@achats_bp.route('/da', methods=['POST'])
def create_da():
    entite, err, code = _entite_or_400()
    if err:
        return err, code

    data = request.get_json(force=True) or {}
    lignes = data.get('lignes', [])
    if not lignes:
        return jsonify({'error': 'Au moins une ligne requise'}), 400

    montant_estime = sum(
        float(l.get('quantite', 0)) * float(l.get('prix_unitaire_estime', 0))
        for l in lignes
    )

    count = DemandeAchat.query.filter_by(entite_id=entite.id).count()
    numero = f"DA-{entite.code}-{date_type.today().year}-{count+1:04d}"

    da = DemandeAchat(
        entite_id      = entite.id,
        numero         = numero,
        date           = date_type.today(),
        objet          = data.get('objet', ''),
        montant_estime = montant_estime,
        statut         = 'brouillon',
        cree_par       = data.get('cree_par', current_role()),
    )
    db.session.add(da)
    db.session.flush()

    for l in lignes:
        db.session.add(LigneDA(
            da_id                = da.id,
            designation          = l.get('designation', ''),
            quantite             = float(l.get('quantite', 1)),
            prix_unitaire_estime = float(l.get('prix_unitaire_estime', 0)),
            compte_charge_id     = l.get('compte_charge_id'),
        ))

    db.session.commit()
    return jsonify(da.to_dict()), 201


@achats_bp.route('/da/<int:did>/soumettre', methods=['POST'])
def soumettre_da(did):
    da = db.session.get(DemandeAchat, did)
    if not da:
        return jsonify({'error': 'DA introuvable'}), 404
    if da.statut != 'brouillon':
        return jsonify({'error': f'Statut actuel {da.statut}, doit être brouillon'}), 400
    da.statut = 'soumise'
    db.session.commit()
    return jsonify(da.to_dict())


@achats_bp.route('/da/<int:did>/valider', methods=['POST'])
def valider_da(did):
    da = db.session.get(DemandeAchat, did)
    if not da:
        return jsonify({'error': 'DA introuvable'}), 404
    if da.statut != 'soumise':
        return jsonify({'error': f'Statut actuel {da.statut}, doit être soumise'}), 400

    data = request.get_json(force=True) or {}
    validateur = data.get('validateur', current_role())

    if validateur == da.cree_par:
        return jsonify({'error': 'Séparation des tâches : impossible de valider sa propre DA'}), 403

    role = current_role()
    config = ConfigAchat.query.filter_by(entite_id=da.entite_id).first()
    seuil = float(config.seuil_validation) if config else 0

    if float(da.montant_estime) > seuil and role not in ('Direction',):
        return jsonify({
            'error': f'Montant {float(da.montant_estime):,.0f} FCFA > seuil {seuil:,.0f} FCFA : validation Direction requise'
        }), 403

    da.statut     = 'validee'
    da.valide_par = validateur
    db.session.commit()
    return jsonify(da.to_dict())


@achats_bp.route('/da/<int:did>/refuser', methods=['POST'])
def refuser_da(did):
    da = db.session.get(DemandeAchat, did)
    if not da:
        return jsonify({'error': 'DA introuvable'}), 404
    if da.statut not in ('soumise',):
        return jsonify({'error': 'Seule une DA soumise peut être refusée'}), 400

    data = request.get_json(force=True) or {}
    da.statut      = 'refusee'
    da.motif_refus = data.get('motif', 'Refusée sans motif')
    da.valide_par  = data.get('validateur', current_role())
    db.session.commit()
    return jsonify(da.to_dict())


# ── Bons de commande ──────────────────────────────────────────────────────────

@achats_bp.route('/bc', methods=['GET'])
def get_bc():
    query = _scope_bc()
    if s := request.args.get('statut'):
        query = query.filter(BonCommande.statut == s)
    if fid := request.args.get('fournisseur_id'):
        query = query.filter(BonCommande.fournisseur_id == int(fid))
    return jsonify([b.to_dict() for b in query.order_by(BonCommande.date.desc()).all()])


@achats_bp.route('/bc', methods=['POST'])
def create_bc():
    entite, err, code = _entite_or_400()
    if err:
        return err, code

    data = request.get_json(force=True) or {}
    da_id = data.get('da_id')
    if not da_id:
        return jsonify({'error': 'da_id requis (BC créé depuis une DA validée)'}), 400

    da = db.session.get(DemandeAchat, da_id)
    if not da or da.statut != 'validee':
        return jsonify({'error': 'DA introuvable ou non validée'}), 400

    fournisseur_id = data.get('fournisseur_id')
    if not fournisseur_id:
        return jsonify({'error': 'fournisseur_id requis'}), 400

    fourn = db.session.get(Tiers, fournisseur_id)
    if not fourn:
        return jsonify({'error': 'Fournisseur introuvable'}), 404
    if fourn.statut in ('bloque', 'suspendu'):
        return jsonify({'error': f'Fournisseur « {fourn.nom} » est {fourn.statut} — BC refusé'}), 422

    count = BonCommande.query.filter_by(entite_id=entite.id).count()
    numero = f"BC-{entite.code}-{date_type.today().year}-{count+1:04d}"

    bc = BonCommande(
        entite_id      = entite.id,
        numero         = numero,
        fournisseur_id = fournisseur_id,
        da_id          = da_id,
        date           = date_type.today(),
        statut         = 'brouillon',
        cree_par       = data.get('cree_par', current_role()),
    )
    db.session.add(bc)
    db.session.flush()

    lignes = data.get('lignes', [])
    if not lignes:
        for lda in da.lignes:
            db.session.add(LigneBC(
                bc_id            = bc.id,
                designation      = lda.designation,
                quantite         = float(lda.quantite),
                prix_unitaire    = float(lda.prix_unitaire_estime),
                compte_charge_id = lda.compte_charge_id or _compte_601_id(),
            ))
    else:
        for l in lignes:
            db.session.add(LigneBC(
                bc_id            = bc.id,
                designation      = l.get('designation', ''),
                quantite         = float(l.get('quantite', 1)),
                prix_unitaire    = float(l.get('prix_unitaire', 0)),
                compte_charge_id = l.get('compte_charge_id') or _compte_601_id(),
            ))

    da.statut = 'transformee'
    db.session.commit()
    return jsonify(bc.to_dict()), 201


def _compte_601_id():
    c = Compte.query.filter_by(numero='601').first()
    return c.id if c else 1


@achats_bp.route('/bc/<int:bid>/envoyer', methods=['POST'])
def envoyer_bc(bid):
    bc = db.session.get(BonCommande, bid)
    if not bc:
        return jsonify({'error': 'BC introuvable'}), 404
    if bc.statut != 'brouillon':
        return jsonify({'error': f'Statut actuel {bc.statut}'}), 400
    bc.statut     = 'envoye'
    data          = request.get_json(force=True) or {}
    bc.valide_par = data.get('valide_par', current_role())
    db.session.commit()
    return jsonify(bc.to_dict())


# ── Réceptions ────────────────────────────────────────────────────────────────

@achats_bp.route('/receptions', methods=['GET'])
def get_receptions():
    query = Reception.query
    if not is_consolidé():
        code = current_entite()
        entite = Entite.query.filter_by(code=code).first()
        if entite:
            query = query.filter_by(entite_id=entite.id)
    if bc := request.args.get('bc'):
        query = query.filter(Reception.bc_id == int(bc))
    return jsonify([r.to_dict() for r in query.order_by(Reception.date.desc()).all()])


@achats_bp.route('/receptions', methods=['POST'])
def create_reception():
    entite, err, code = _entite_or_400()
    if err:
        return err, code

    data = request.get_json(force=True) or {}
    bc_id = data.get('bc_id')
    bc = db.session.get(BonCommande, bc_id)
    if not bc or bc.statut not in ('envoye', 'recu_partiel'):
        return jsonify({'error': 'BC introuvable ou non envoyé'}), 400

    lignes_data = data.get('lignes', [])
    if not lignes_data:
        return jsonify({'error': 'Au moins une ligne requise'}), 400

    count = Reception.query.filter_by(entite_id=entite.id).count()
    numero = f"REC-{entite.code}-{date_type.today().year}-{count+1:04d}"

    rec = Reception(
        entite_id = entite.id,
        numero    = numero,
        bc_id     = bc_id,
        date      = date_type.today(),
        type      = 'partielle',
        recu_par  = data.get('recu_par', current_role()),
    )
    db.session.add(rec)
    db.session.flush()

    for l in lignes_data:
        lbc = db.session.get(LigneBC, l['ligne_bc_id'])
        if not lbc:
            continue
        qr = float(l.get('quantite_recue', 0))
        if qr <= 0:
            continue
        db.session.add(LigneReception(
            reception_id   = rec.id,
            ligne_bc_id    = lbc.id,
            quantite_recue = qr,
        ))
        lbc.quantite_recue = float(lbc.quantite_recue) + qr

    total_cmd = sum(float(l.quantite) for l in bc.lignes)
    total_rec = sum(float(l.quantite_recue) for l in bc.lignes)

    if total_rec >= total_cmd:
        bc.statut  = 'recu_total'
        rec.type   = 'totale'
    else:
        bc.statut  = 'recu_partiel'

    db.session.commit()
    return jsonify(rec.to_dict()), 201


# ── Factures fournisseurs ─────────────────────────────────────────────────────

@achats_bp.route('/factures', methods=['GET'])
def get_factures():
    query = _scope_fact()
    if s := request.args.get('statut'):
        query = query.filter(FactureFournisseur.statut == s)
    if bc := request.args.get('bc_id'):
        query = query.filter(FactureFournisseur.bc_id == int(bc))
    return jsonify([f.to_dict() for f in query.order_by(FactureFournisseur.date.desc()).all()])


@achats_bp.route('/factures', methods=['POST'])
def create_facture():
    entite, err, code = _entite_or_400()
    if err:
        return err, code

    data = request.get_json(force=True) or {}
    bc_id = data.get('bc_id')
    bc    = db.session.get(BonCommande, bc_id) if bc_id else None

    montant_ht  = float(data.get('montant_ht', 0))
    taux_tva    = float(data.get('taux_tva', 18))
    montant_tva = round(montant_ht * taux_tva / 100, 2)
    montant_ttc = round(montant_ht + montant_tva, 2)

    ecart = False
    if bc:
        montant_recu = sum(
            float(l.quantite_recue) * float(l.prix_unitaire)
            for l in bc.lignes
        )
        if montant_ht > montant_recu * 1.001:
            ecart = True

    count  = FactureFournisseur.query.filter_by(entite_id=entite.id).count()
    numero = data.get('numero') or f"FACT-{entite.code}-{date_type.today().year}-{count+1:04d}"

    f = FactureFournisseur(
        entite_id           = entite.id,
        numero              = numero,
        fournisseur_id      = data.get('fournisseur_id') or (bc.fournisseur_id if bc else None),
        bc_id               = bc_id,
        date                = date_type.today(),
        date_echeance       = (date_type.today() + timedelta(days=30)),
        montant_ht          = montant_ht,
        taux_tva            = taux_tva,
        montant_tva         = montant_tva,
        montant_ttc         = montant_ttc,
        statut              = 'a_payer',
        ecart_rapprochement = ecart,
    )
    db.session.add(f)

    if bc and bc.statut in ('recu_partiel', 'recu_total'):
        bc.statut = 'facture'

    db.session.commit()
    return jsonify(f.to_dict()), 201


@achats_bp.route('/factures/<int:fid>/comptabiliser', methods=['POST'])
def comptabiliser_facture(fid):
    role = current_role()
    if role not in ('Comptable', 'Direction'):
        return jsonify({'error': f'Rôle {role} non autorisé à comptabiliser'}), 403

    fact = db.session.get(FactureFournisseur, fid)
    if not fact:
        return jsonify({'error': 'Facture introuvable'}), 404
    if fact.statut != 'a_payer':
        return jsonify({'error': f'Facture déjà {fact.statut}'}), 400

    entite = db.session.get(Entite, fact.entite_id)

    journal = Journal.query.filter_by(entite_id=entite.id, type='AC').first()
    if not journal:
        return jsonify({'error': 'Journal AC introuvable pour cette entité'}), 400

    compte_401 = Compte.query.filter_by(numero='401').first()
    compte_tva  = Compte.query.filter_by(numero='445').first() or Compte.query.filter_by(numero='441').first()
    if not compte_401:
        return jsonify({'error': 'Compte 401 manquant dans le plan comptable'}), 400

    data      = request.get_json(force=True) or {}
    cree_par  = data.get('cree_par', role)

    e = Ecriture(
        entite_id  = entite.id,
        journal_id = journal.id,
        date       = fact.date,
        libelle    = f"Facture {fact.numero} — {fact.fournisseur.nom if fact.fournisseur else ''}",
        reference  = fact.numero,
        source     = 'achats',
        statut     = 'validee',
        cree_par   = cree_par,
        valide_par = cree_par,
    )
    db.session.add(e)
    db.session.flush()

    bc = fact.bc
    if bc and bc.lignes:
        total_ht_bc = sum(float(l.quantite) * float(l.prix_unitaire) for l in bc.lignes)
        for lbc in bc.lignes:
            if lbc.compte_charge:
                prop = (float(lbc.quantite) * float(lbc.prix_unitaire)) / total_ht_bc if total_ht_bc else 0
                montant = round(float(fact.montant_ht) * prop, 2)
                if montant > 0:
                    db.session.add(LigneEcriture(
                        ecriture_id = e.id,
                        compte_id   = lbc.compte_charge_id,
                        libelle     = lbc.designation,
                        debit       = montant,
                        credit      = 0,
                    ))
    else:
        compte_601 = Compte.query.filter_by(numero='601').first()
        db.session.add(LigneEcriture(
            ecriture_id = e.id,
            compte_id   = compte_601.id if compte_601 else compte_401.id,
            libelle     = f"Charges — {fact.numero}",
            debit       = float(fact.montant_ht),
            credit      = 0,
        ))

    if float(fact.montant_tva) > 0 and compte_tva:
        db.session.add(LigneEcriture(
            ecriture_id = e.id,
            compte_id   = compte_tva.id,
            libelle     = f"TVA déductible {float(fact.taux_tva):.0f}%",
            debit       = float(fact.montant_tva),
            credit      = 0,
        ))
    elif float(fact.montant_tva) > 0:
        db.session.add(LigneEcriture(
            ecriture_id = e.id,
            compte_id   = compte_401.id,
            libelle     = f"TVA incluse dans 401",
            debit       = float(fact.montant_tva),
            credit      = 0,
        ))

    db.session.add(LigneEcriture(
        ecriture_id = e.id,
        compte_id   = compte_401.id,
        libelle     = f"{fact.fournisseur.nom if fact.fournisseur else 'Fournisseur'} — {fact.numero}",
        debit       = 0,
        credit      = float(fact.montant_ttc),
    ))

    fact.statut      = 'comptabilisee'
    fact.ecriture_id = e.id
    db.session.commit()
    return jsonify({'facture': fact.to_dict(), 'ecriture': e.to_dict()})


# ── Engagements ───────────────────────────────────────────────────────────────

@achats_bp.route('/engagements', methods=['GET'])
def get_engagements():
    query = _scope_bc().filter(
        BonCommande.statut.in_(['envoye', 'recu_partiel', 'facture'])
    )
    bcs   = query.order_by(BonCommande.date.desc()).all()
    total = sum(b.montant_total_ht for b in bcs)

    rows = []
    for b in bcs:
        montant_recu = sum(
            float(l.quantite_recue) * float(l.prix_unitaire)
            for l in b.lignes
        )
        rows.append({
            **b.to_dict(),
            'montant_engage':   b.montant_total_ht,
            'montant_recu':     montant_recu,
            'montant_restant':  b.montant_total_ht - montant_recu,
        })

    return jsonify({
        'consolide': is_consolidé(),
        'entite':    current_entite() or 'CONSOLIDE',
        'bcs':       rows,
        'total_engage': total,
    })


# ── OCR — Extraction de factures ──────────────────────────────────────────

def _parse_amount(s):
    s = str(s).strip().replace('\xa0', '').replace(' ', '').replace(' ', '')
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        v = float(s)
        return v if 0 < v < 1_000_000_000 else None
    except Exception:
        return None


def _parse_invoice_text(text):
    result = {}
    for pat in [
        r'(?:n[o°]\s*|num[eé]ro\s*|facture\s*n[o°]?\s*)[:\-]?\s*([A-Z0-9][A-Z0-9\-_/\.]{2,25})',
        r'(?:FACT|INV|FAC)[-\s]?([A-Z0-9\-]{3,20})',
    ]:
        m = _re.search(pat, text, _re.IGNORECASE)
        if m:
            result['numero'] = m.group(1).strip()
            break

    dates = _re.findall(r'\b(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})\b', text)
    if dates:
        d, mo, y = dates[0]
        result['date'] = f"{y}-{mo}-{d}"

    m = _re.search(r'(?:total|montant|base)\s+h\.?\s*t\.?\s*[:\-=]?\s*([\d\s\xa0 ,\.]+)', text, _re.IGNORECASE)
    if m:
        val = _parse_amount(m.group(1).split()[0] if m.group(1).strip() else '')
        if val:
            result['montant_ht'] = val

    m = _re.search(r't\.?\s*v\.?\s*a\.?\s*(?:\d+\s*%\s*)?[:\-=]\s*([\d\s\xa0 ,\.]+)', text, _re.IGNORECASE)
    if m:
        val = _parse_amount(m.group(1).split()[0] if m.group(1).strip() else '')
        if val and result.get('montant_ht') and val < result['montant_ht']:
            result['montant_tva'] = val

    for pat in [
        r'(?:total|montant|net)\s+(?:à\s+payer|t\.?\s*t\.?\s*c\.?)\s*[:\-=]?\s*([\d\s\xa0 ,\.]+)',
        r't\.?\s*t\.?\s*c\.?\s*[:\-=]\s*([\d\s\xa0 ,\.]+)',
    ]:
        m = _re.search(pat, text, _re.IGNORECASE)
        if m:
            val = _parse_amount(m.group(1).split()[0] if m.group(1).strip() else '')
            if val:
                result['montant_ttc'] = val
                break

    if result.get('montant_ht') and result.get('montant_tva'):
        result['taux_tva'] = round(result['montant_tva'] / result['montant_ht'] * 100)
    else:
        m = _re.search(r'(?:tva|t\.v\.a\.)\s*(?:à|de|:)?\s*(\d+)\s*%', text, _re.IGNORECASE)
        if m:
            result['taux_tva'] = int(m.group(1))

    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if lines:
        result['fournisseur_hint'] = lines[0][:80]

    return result


@achats_bp.route('/ocr/facture', methods=['POST'])
def ocr_facture():
    if 'file' not in request.files:
        return jsonify({'error': 'Champ file manquant'}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'Fichier vide'}), 400

    fname = (f.filename or '').lower()
    file_bytes = f.read()
    text = ''
    method = 'none'

    if fname.endswith('.pdf'):
        try:
            import pdfplumber
            with pdfplumber.open(_io.BytesIO(file_bytes)) as pdf:
                text = '\n'.join(p.extract_text() or '' for p in pdf.pages).strip()
                if text:
                    method = 'pdfplumber'
        except ImportError:
            pass
        except Exception:
            pass

    if not text:
        try:
            import pytesseract
            from PIL import Image
            if fname.endswith('.pdf'):
                try:
                    from pdf2image import convert_from_bytes
                    images = convert_from_bytes(file_bytes, dpi=200)
                    text = '\n'.join(
                        pytesseract.image_to_string(img, lang='fra+eng') for img in images
                    ).strip()
                    if text:
                        method = 'tesseract-pdf'
                except ImportError:
                    pass
            else:
                img = Image.open(_io.BytesIO(file_bytes))
                text = pytesseract.image_to_string(img, lang='fra+eng').strip()
                if text:
                    method = 'tesseract-image'
        except ImportError:
            pass
        except Exception:
            pass

    if not text:
        return jsonify({
            'warning': 'Aucun texte extrait. Installez pdfplumber (PDF texte) ou pytesseract + Tesseract (images/scans).',
            'fields': {},
            'method': 'none',
        })

    fields = _parse_invoice_text(text)
    return jsonify({'method': method, 'fields': fields, 'raw_text': text[:400]})
