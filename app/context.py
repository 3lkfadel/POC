"""
Helpers d'isolation par entité.

- current_entite() / current_role() : lus depuis la session Flask.
- scope(query, model)               : filtre un query SQLAlchemy par entité courante.
  Si la holding est en mode "Consolidé" (code == 'CONSOLIDE'), aucun filtre n'est appliqué
  → la holding voit tous les enregistrements.
"""
from flask import session

HOLDING_CODE = 'MDP'
ROLES = ['Saisie', 'Valideur', 'Comptable', 'Trésorier', 'Direction']


def current_entite() -> str | None:
    """Code de l'entité courante, ou None si non défini."""
    return session.get('entite_code')


def current_role() -> str:
    """Rôle courant (défaut : Direction)."""
    return session.get('role', 'Direction')


def is_consolidé() -> bool:
    """True si on est en vue consolidée (holding, aucun filtre entité)."""
    return session.get('entite_code') in (None, 'CONSOLIDE', 'MDP')


MODULE_OWNERS = {
    'immobilier': 'AC',
    'production': 'TC',
    'hotellerie': 'SW',
    'conseil':    'IC',
}


def module_autorise(code_module: str) -> bool:
    """True si l'entité courante peut accéder au module métier.
    Propriétaire → lecture+écriture. MDP/Consolidé → lecture seule (contrôle).
    Toute autre entité → False → 403.
    """
    if is_consolidé():
        return True
    owner = MODULE_OWNERS.get(code_module)
    return current_entite() == owner


def scope(query, model):
    """
    Filtre un SQLAlchemy query par entité courante.
    Pré-condition : model doit avoir un attribut `entite_id`.
    Usage :
        rows = scope(MonModel.query, MonModel).all()
    """
    from app.models import Entite

    if is_consolidé():
        return query  # Holding : toutes les entités

    code = current_entite()
    entite = Entite.query.filter_by(code=code).first()
    if entite and hasattr(model, 'entite_id'):
        return query.filter(model.entite_id == entite.id)

    return query
