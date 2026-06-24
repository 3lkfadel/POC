"""Blueprint Module TC — Production bois (réf. TC-01→TC-46)."""
from datetime import date as date_type
from flask import Blueprint, jsonify, request, abort
from app import db
from app.models import (
    Entite, FamilleArticle, Article, OrdreProduction,
    EtapeProduction, MouvementStock,
)
from app.context import current_entite, current_role, is_consolidé, module_autorise

production_bp = Blueprint('production', __name__, url_prefix='/api/production')

MODULE = 'production'
OWNER  = 'TC'

ETAPES_ORDRE = ['sciage', 'sechage', 'rabotage', 'usinage']


def _check_read():
    if not module_autorise(MODULE):
        abort(403)


def _tc_entite():
    if not module_autorise(MODULE):
        return None, jsonify({'error': 'Module réservé à TC'}), 403
    if is_consolidé():
        return None, jsonify({'error': 'Opération de saisie impossible en vue consolidée'}), 400
    code = current_entite()
    if code != OWNER:
        return None, jsonify({'error': 'Module réservé à TC'}), 403
    entite = Entite.query.filter_by(code=OWNER).first()
    if not entite:
        return None, jsonify({'error': 'Entité TC introuvable'}), 400
    return entite, None, None


def _scope(model):
    if is_consolidé():
        return model.query
    entite = Entite.query.filter_by(code=OWNER).first()
    if entite:
        return model.query.filter_by(entite_id=entite.id)
    return model.query.filter_by(entite_id=-1)


# ── Familles d'articles ───────────────────────────────────────────────────────

@production_bp.route('/familles', methods=['GET'])
def get_familles():
    _check_read()
    return jsonify([f.to_dict() for f in _scope(FamilleArticle).all()])


@production_bp.route('/familles', methods=['POST'])
def create_famille():
    entite, err, code = _tc_entite()
    if err:
        return err, code
    data = request.get_json(force=True) or {}
    if not data.get('nom') or not data.get('code'):
        return jsonify({'error': 'code et nom requis'}), 400
    f = FamilleArticle(entite_id=entite.id, code=data['code'], nom=data['nom'])
    db.session.add(f)
    db.session.commit()
    return jsonify(f.to_dict()), 201


# ── Articles ──────────────────────────────────────────────────────────────────

@production_bp.route('/articles', methods=['GET'])
def get_articles():
    _check_read()
    q = _scope(Article)
    if cat := request.args.get('categorie'):
        q = q.filter(Article.categorie == cat)
    return jsonify([a.to_dict() for a in q.all()])


@production_bp.route('/articles', methods=['POST'])
def create_article():
    entite, err, code = _tc_entite()
    if err:
        return err, code
    data = request.get_json(force=True) or {}
    if not data.get('code') or not data.get('nom') or not data.get('categorie'):
        return jsonify({'error': 'code, nom et categorie requis'}), 400
    a = Article(
        entite_id=entite.id, famille_id=data.get('famille_id'),
        code=data['code'], nom=data['nom'], unite=data.get('unite', 'm³'),
        categorie=data['categorie'],
        methode_valo=data.get('methode_valo', 'CUMP'),
        stock_qty=0, valeur_stock=0,
    )
    db.session.add(a)
    db.session.commit()
    return jsonify(a.to_dict()), 201


# ── Ordres de production ──────────────────────────────────────────────────────

@production_bp.route('/ordres', methods=['GET'])
def get_ordres():
    _check_read()
    q = _scope(OrdreProduction)
    if s := request.args.get('statut'):
        q = q.filter(OrdreProduction.statut == s)
    return jsonify([o.to_dict() for o in q.order_by(OrdreProduction.id.desc()).all()])


@production_bp.route('/ordres', methods=['POST'])
def create_ordre():
    entite, err, code = _tc_entite()
    if err:
        return err, code
    data = request.get_json(force=True) or {}
    if not data.get('article_fini_id') or not data.get('quantite'):
        return jsonify({'error': 'article_fini_id et quantite requis'}), 400
    from datetime import date as _d
    o = OrdreProduction(
        entite_id=entite.id, article_fini_id=data['article_fini_id'],
        quantite=data['quantite'], statut='ouvert', cout_total=0,
        date_debut=_d.today(),
    )
    db.session.add(o)
    db.session.commit()
    return jsonify(o.to_dict()), 201


@production_bp.route('/ordres/<int:oid>', methods=['GET'])
def get_ordre(oid):
    _check_read()
    o = OrdreProduction.query.get_or_404(oid)
    return jsonify(o.to_dict())


@production_bp.route('/ordres/<int:oid>/etapes', methods=['POST'])
def add_etape(oid):
    """Ajoute une étape de production et accumule les coûts sur l'ordre."""
    entite, err, code = _tc_entite()
    if err:
        return err, code
    ordre = OrdreProduction.query.get_or_404(oid)
    if ordre.entite_id != entite.id:
        abort(403)
    if ordre.statut == 'termine':
        return jsonify({'error': 'Ordre terminé'}), 400

    data = request.get_json(force=True) or {}
    if not data.get('type') or data['type'] not in ETAPES_ORDRE:
        return jsonify({'error': f'type doit être parmi {ETAPES_ORDRE}'}), 400

    etape = EtapeProduction(
        ordre_id=oid,
        type=data['type'],
        cout_matiere=data.get('cout_matiere', 0),
        cout_mo=data.get('cout_mo', 0),
        cout_frais=data.get('cout_frais', 0),
        quantite_encours=data.get('quantite_encours', float(ordre.quantite)),
        statut='en_cours',
    )
    db.session.add(etape)
    db.session.flush()

    cout_etape = etape.cout_etape
    ordre.cout_total = float(ordre.cout_total or 0) + cout_etape
    if ordre.statut == 'ouvert':
        ordre.statut = 'en_cours'

    db.session.commit()
    return jsonify(etape.to_dict()), 201


@production_bp.route('/ordres/<int:oid>/terminer', methods=['POST'])
def terminer_ordre(oid):
    """Clôture l'ordre : valorise le PF et génère un mouvement de stock."""
    entite, err, code = _tc_entite()
    if err:
        return err, code
    ordre = OrdreProduction.query.get_or_404(oid)
    if ordre.entite_id != entite.id:
        abort(403)
    if ordre.statut == 'termine':
        return jsonify({'error': 'Déjà terminé'}), 400

    pf = ordre.article_fini
    qte = float(ordre.quantite)
    valeur_totale = float(ordre.cout_total or 0)

    # Valorisation CUMP : ajout au stock
    pf.stock_qty = float(pf.stock_qty or 0) + qte
    pf.valeur_stock = float(pf.valeur_stock or 0) + valeur_totale

    # Mouvement d'entrée PF
    mv = MouvementStock(
        entite_id=entite.id, article_id=pf.id,
        type='entree', quantite=qte, valeur=valeur_totale,
        date=date_type.today(), reference=f'OP-{oid}',
    )
    db.session.add(mv)

    # Terminer les étapes
    for etape in ordre.etapes:
        etape.statut = 'termine'

    ordre.statut = 'termine'
    ordre.date_fin = date_type.today()
    db.session.commit()
    return jsonify({'message': 'Ordre terminé', 'pf': pf.to_dict(), 'mouvement': mv.to_dict()})


# ── Mouvements de stock ────────────────────────────────────────────────────────

@production_bp.route('/mouvements', methods=['GET'])
def get_mouvements():
    _check_read()
    q = _scope(MouvementStock)
    if aid := request.args.get('article_id'):
        q = q.filter(MouvementStock.article_id == int(aid))
    return jsonify([m.to_dict() for m in q.order_by(MouvementStock.date.desc()).all()])


@production_bp.route('/mouvements', methods=['POST'])
def create_mouvement():
    """Entrée/sortie de stock manuelle avec mise à jour CUMP."""
    entite, err, code = _tc_entite()
    if err:
        return err, code
    data = request.get_json(force=True) or {}
    if not all(k in data for k in ('article_id', 'type', 'quantite', 'valeur')):
        return jsonify({'error': 'article_id, type, quantite, valeur requis'}), 400

    art = Article.query.get_or_404(data['article_id'])
    if art.entite_id != entite.id:
        abort(403)

    qte = float(data['quantite'])
    val = float(data['valeur'])

    if data['type'] == 'entree':
        art.stock_qty = float(art.stock_qty or 0) + qte
        art.valeur_stock = float(art.valeur_stock or 0) + val
    elif data['type'] == 'sortie':
        if float(art.stock_qty or 0) < qte:
            return jsonify({'error': 'Stock insuffisant'}), 400
        valeur_sortie = art.cump * qte
        art.stock_qty = float(art.stock_qty or 0) - qte
        art.valeur_stock = float(art.valeur_stock or 0) - valeur_sortie
        val = valeur_sortie

    from datetime import date as _d
    mv = MouvementStock(
        entite_id=entite.id, article_id=art.id,
        type=data['type'], quantite=qte, valeur=val,
        date=_d.fromisoformat(data.get('date', _d.today().isoformat())),
        reference=data.get('reference'),
    )
    db.session.add(mv)
    db.session.commit()
    return jsonify(mv.to_dict()), 201


# ── Coûts de revient (synthèse par ordre) ────────────────────────────────────

@production_bp.route('/couts-revient', methods=['GET'])
def couts_revient():
    _check_read()
    ordres = _scope(OrdreProduction).filter(OrdreProduction.statut == 'termine').all()
    result = []
    for o in ordres:
        par_type = {}
        for e in o.etapes:
            t = e.type
            par_type.setdefault(t, {'cout_matiere': 0, 'cout_mo': 0, 'cout_frais': 0})
            par_type[t]['cout_matiere'] += float(e.cout_matiere or 0)
            par_type[t]['cout_mo']      += float(e.cout_mo or 0)
            par_type[t]['cout_frais']   += float(e.cout_frais or 0)
        result.append({
            'ordre_id': o.id,
            'article': o.article_fini.nom if o.article_fini else None,
            'quantite': float(o.quantite),
            'cout_total': float(o.cout_total or 0),
            'cout_unitaire': float(o.cout_total or 0) / float(o.quantite) if float(o.quantite) > 0 else 0,
            'detail_etapes': par_type,
        })
    return jsonify(result)


# ── Valorisation stock ────────────────────────────────────────────────────────

@production_bp.route('/valorisation', methods=['GET'])
def valorisation_stock():
    _check_read()
    articles = _scope(Article).all()
    categories = {}
    for a in articles:
        cat = a.categorie
        categories.setdefault(cat, {'articles': [], 'total_valeur': 0, 'total_qty': 0})
        categories[cat]['articles'].append(a.to_dict())
        categories[cat]['total_valeur'] += float(a.valeur_stock or 0)
        categories[cat]['total_qty']    += float(a.stock_qty or 0)
    return jsonify({'categories': categories,
                    'total_global': sum(c['total_valeur'] for c in categories.values())})
