# Alvéole — SI de gestion Groupe MDP

Application web de gestion multi-sociétés pour le groupe **MD Participations (MDP)**, conforme SYSCOHADA.

## Groupe (5 entités)

| Code | Entité | Secteur |
|------|--------|---------|
| MDP | MD Participations | Holding (vue consolidée) |
| AC | AIC | Immobilier / Construction / VEFA |
| TC | Trenchaine Bois | Industrie du bois |
| SW | Synergy Wellness | Hôtellerie / Wellness |
| IC | ISF Conseil | Conseil / Marchés financiers |

## Stack technique

- **Backend** : Flask (app factory + blueprints) + SQLAlchemy + SQLite
- **Frontend** : HTML/CSS/JS vanilla · Tailwind CSS v3 CDN · Geist font · Material Symbols
- **Comptabilité** : SYSCOHADA (plan de comptes OHADA, journaux, grand-livre, balance)

## Installation

```bash
# Cloner le dépôt
git clone <url-du-repo>
cd <nom-du-repo>

# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate      # Mac/Linux
# venv\Scripts\activate       # Windows

# Installer les dépendances
pip install -r requirements.txt

# Initialiser la base de données avec les données de démo
python seed.py

# Lancer l'application
python run.py
```

L'application est disponible sur **http://localhost:5001**

## Modules disponibles

### Modules transversaux (toutes entités)
| Module | URL |
|--------|-----|
| Tableau de bord stratégique | `/Tableau-de-bord.html` |
| Comptabilité générale (journal, grand-livre, balance) | `/compta-journal.html` |
| Saisie d'écritures | `/saisie-ecriture.html` |
| Plan comptable | `/plan-comptable.html` |
| Tiers (fournisseurs, clients) | `/tiers.html` |
| Achats (DA → BC → Réception → Facture) | `/demandes-achat.html` |
| Cockpit trésorerie | `/cockpit-tresorie.html` |
| Comptabilité analytique | `/Comptabilité-analytics.html` |
| Contrôle budgétaire | `/Budget.html` |
| Immobilisations | `/gestion-des-immobiliers.html` |
| Contrats | `/Gestion-des-contrats.html` |

### Module AC — Immobilier / VEFA
| Page | URL |
|------|-----|
| Prospects & acquéreurs | `/ac-prospects.html` |
| Projets & chantiers | `/ac-projets.html` |
| Programmes VEFA & appels de fonds | `/ac-vefa.html` |
| Reporting projet | `/ac-reporting.html` |

### Module TC — Production Bois
| Page | URL |
|------|-----|
| Articles & familles | `/tc-articles.html` |
| Ordres de production | `/tc-ordres-production.html` |
| Stocks & valorisation | `/tc-stocks.html` |

### Module SW — Hôtellerie / USALI
| Page | URL |
|------|-----|
| Import PMS/POS | `/sw-import-pms.html` |
| Pré-écritures | `/sw-pre-ecritures.html` |
| Reporting USALI | `/sw-reporting-usali.html` |

### Module IC — Conseil / KYC / AMF
| Page | URL |
|------|-----|
| Pipeline dossiers (Kanban) | `/ic-pipeline.html` |
| Apporteurs & contrôle KYC | `/ic-apporteurs.html` |
| Commissions & contrats | `/ic-commissions.html` |
| Reporting AMF-UMOA | `/ic-reporting-amf.html` |

## Utilisation

1. Ouvrir l'application dans le navigateur
2. Sélectionner une **entité** et un **rôle** dans la barre haute (topbar)
3. Les modules métier de l'entité apparaissent automatiquement dans la sidebar
4. **MDP** donne accès à la vue consolidée (lecture seule sur tous les modules)

## Rôles disponibles

| Rôle | Droits |
|------|--------|
| Saisie | Création d'enregistrements |
| Valideur | Validation (ne peut pas valider ce qu'il a saisi) |
| Comptable | Comptabilisation des écritures |
| Trésorier | Gestion des paiements |
| Direction | Accès complet |

## Réinitialiser la base de données

```bash
python seed.py
```

Remet la base dans un état de démo propre avec des données cohérentes sur toutes les entités.

## Structure du projet

```
.
├── app/
│   ├── __init__.py          # App factory
│   ├── context.py           # Helpers cloisonnement par entité
│   ├── models.py            # Tous les modèles SQLAlchemy
│   └── blueprints/
│       ├── api.py           # API core (comptes, écritures, tiers…)
│       ├── achats.py        # Module achats
│       ├── immobilier.py    # Module AC — VEFA
│       ├── production.py    # Module TC — Bois
│       ├── hotellerie.py    # Module SW — USALI
│       └── conseil.py       # Module IC — KYC/AMF
├── static/
│   └── js/
│       └── context_bar.js   # Sélecteurs Entité/Rôle (topbar)
├── *.html                   # Pages frontend
├── seed.py                  # Données de démo
├── run.py                   # Point d'entrée
└── requirements.txt
```
