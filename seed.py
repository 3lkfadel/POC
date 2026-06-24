"""Reset complet de la base de démo. Usage : python seed.py"""
import os, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db
from app.models import (
    Entite, Utilisateur, Compte, Journal, Ecriture, LigneEcriture, Tiers,
    ConfigAchat, DemandeAchat, LigneDA, BonCommande, LigneBC,
    Reception, LigneReception, FactureFournisseur,
    # Module AC — Immobilier/VEFA
    ProjetImmobilier, ProgrammeVEFA, TrancheVEFA, Acquereur, AppelFonds,
    GFA, EcheancierAcquereur, Souscription, Prospect,
    # Module TC — Production bois
    FamilleArticle, Article, OrdreProduction, EtapeProduction, MouvementStock,
    # Module SW — Hôtellerie
    ImportPMS, LigneVenteSW, PreEcritureSW,
    # Module IC — Conseil
    Dossier, EtapeDossier, Apporteur, ContratCommission, NiveauCommission,
    Commission, PieceDossier,
)

# ── Lot 0 — Entités & utilisateurs ────────────────────────────────────────

ENTITES = [
    ('MDP', 'MD Participations', 'holding', 'XOF'),
    ('IC',  'ISF Conseil',       'filiale', 'XOF'),
    ('SW',  'Synergy Wellness',  'filiale', 'XOF'),
    ('TC',  'Trenchaine Bois',   'filiale', 'XOF'),
    ('AC',  'AIC',               'filiale', 'XOF'),
]

UTILISATEURS = [
    ('Admin Groupe',    'Direction',  'MDP'),
    ('Camille Saisie',  'Saisie',     'IC'),
    ('Jordan Valideur', 'Valideur',   'IC'),
    ('Alex Comptable',  'Comptable',  'SW'),
    ('Sam Trésorier',   'Trésorier',  'TC'),
    ('Pat Direction',   'Direction',  'AC'),
    ('Léa Saisie',      'Saisie',     'SW'),
    ('Marc Valideur',   'Valideur',   'TC'),
    ('Nina Comptable',  'Comptable',  'AC'),
]

# ── Lot 1 — Plan comptable SYSCOHADA (~37 comptes) ────────────────────────

COMPTES = [
    # (numero, libelle, classe)
    # Classe 1 — Capitaux
    ('101', 'Capital social', 1),
    ('104', 'Réserves légales', 1),
    ('111', "Résultat net de l'exercice", 1),
    ('161', 'Emprunts bancaires', 1),
    # Classe 2 — Immobilisations
    ('212', 'Terrains', 2),
    ('221', 'Bâtiments', 2),
    ('244', 'Matériel informatique', 2),
    ('245', 'Mobilier de bureau', 2),
    ('281', 'Amortissements des bâtiments', 2),
    ('284', 'Amortissements du matériel informatique', 2),
    # Classe 3 — Stocks
    ('311', 'Marchandises', 3),
    ('351', 'Matières premières', 3),
    ('361', 'Produits finis', 3),
    # Classe 4 — Tiers
    ('401', 'Fournisseurs', 4),
    ('4191', 'Avances et acomptes reçus sur commandes clients', 4),
    ('408', 'Fournisseurs — Factures à recevoir', 4),
    ('411', 'Clients', 4),
    ('418', 'Clients — Produits à recevoir', 4),
    ('421', 'Personnel — Rémunérations dues', 4),
    ('431', 'Sécurité sociale (CNPS)', 4),
    ('441', 'État — Impôt sur les bénéfices (IS)', 4),
    ('443', 'État — TVA facturée', 4),
    ('444', 'État — TVA récupérable', 4),
    ('445', 'État — TVA déductible sur achats', 4),
    ('447', 'État — Impôts retenus à la source (ITS)', 4),
    # Classe 5 — Trésorerie
    ('521', 'Banques locales', 5),
    ('531', 'CCP', 5),
    ('571', 'Caisse principale', 5),
    # Classe 6 — Charges
    ('601', 'Achats de marchandises', 6),
    ('604', 'Achats de matières premières et fournitures', 6),
    ('612', 'Locations et charges locatives', 6),
    ('621', 'Publicité, publications, relations publiques', 6),
    ('641', 'Transports sur achats', 6),
    ('661', 'Rémunérations du personnel', 6),
    ('664', 'Charges sociales patronales (CNPS)', 6),
    ('671', 'Intérêts et charges assimilées', 6),
    # Classe 7 — Produits
    ('701', 'Ventes de marchandises', 7),
    ('706', 'Prestations de services', 7),
    ('764', 'Revenus des placements et assimilés', 7),
]

# ── Journaux par entité ────────────────────────────────────────────────────

JOURNAL_TYPES = [
    ('AC', 'Journal des Achats',             'AC'),
    ('VE', 'Journal des Ventes',             'VE'),
    ('BQ', 'Journal de Banque',              'BQ'),
    ('CA', 'Journal de Caisse',              'CA'),
    ('OD', 'Journal des Opérations Diverses','OD'),
    ('PA', 'Journal de Paie',                'PA'),
]

# ── Tiers ──────────────────────────────────────────────────────────────────

TIERS_DATA = [
    # (type, code, nom, partage, entite_code_or_None, statut)
    ('fournisseur', 'FOURN-GRP-001', 'Orange CI Télécom',        'groupe', None,  'actif'),
    ('fournisseur', 'FOURN-GRP-002', 'Total Énergies Afrique',   'groupe', None,  'actif'),
    ('fournisseur', 'FOURN-BLK-001', 'Construction Rapide SARL', 'groupe', None,  'bloque'),
    ('client',      'CLI-IC-001',    'BNP Paribas CI',            'entite', 'IC',  'actif'),
    ('client',      'CLI-IC-002',    'Société Générale CI',       'entite', 'IC',  'actif'),
    ('client',      'CLI-SW-001',    'Resort Azur',               'entite', 'SW',  'actif'),
    ('client',      'CLI-SW-002',    'Hôtel le Plateau',          'entite', 'SW',  'actif'),
    ('client',      'CLI-TC-001',    'Scierie du Nord',           'entite', 'TC',  'actif'),
    ('client',      'CLI-TC-002',    'Bois & Matériaux SA',       'entite', 'TC',  'actif'),
    ('client',      'CLI-AC-001',    'Immobilière du Golfe',      'entite', 'AC',  'actif'),
    ('fournisseur', 'FOURN-IC-001',  'Cabinet Audit & Conseil',   'entite', 'IC',  'agree'),
    ('fournisseur', 'FOURN-IC-002',  'Logiciels Finance Pro',     'entite', 'IC',  'en_attente'),
    ('fournisseur', 'FOURN-SW-001',  'Fournitures Hôtelières SA', 'entite', 'SW',  'actif'),
    ('fournisseur', 'FOURN-TC-001',  'Scies et Outils Pro',       'entite', 'TC',  'actif'),
    ('fournisseur', 'FOURN-AC-001',  'Ciment Ivoire SA',          'entite', 'AC',  'actif'),
    ('fournisseur', 'FOURN-AC-002',  'Ferronnerie Industrielle',  'entite', 'AC',  'suspendu'),
]


def _add_ecriture(entite, journal, dt, libelle, ref, lignes_data, compte_map):
    """Ajoute une écriture équilibrée avec ses lignes."""
    e = Ecriture(
        entite_id  = entite.id,
        journal_id = journal.id,
        date       = dt,
        libelle    = libelle,
        reference  = ref,
        source     = 'seed',
        statut     = 'validee',
        cree_par   = 'Seed',
        valide_par = 'Admin',
    )
    db.session.add(e)
    db.session.flush()
    for (num, debit, credit) in lignes_data:
        db.session.add(LigneEcriture(
            ecriture_id = e.id,
            compte_id   = compte_map[num].id,
            libelle     = libelle,
            debit       = debit,
            credit      = credit,
        ))
    return e


# ── Main ───────────────────────────────────────────────────────────────────

app = create_app()

with app.app_context():
    print('🗑️  Réinitialisation…')
    db.drop_all()
    db.create_all()

    # Entités
    entite_map: dict[str, Entite] = {}
    for code, nom, type_, devise in ENTITES:
        e = Entite(code=code, nom=nom, type=type_, devise=devise)
        db.session.add(e); db.session.flush()
        entite_map[code] = e
        print(f'   Entité  {code}  {nom}')

    # Utilisateurs
    for nom, role, code in UTILISATEURS:
        db.session.add(Utilisateur(nom=nom, role=role, entite_id=entite_map[code].id))

    # Plan comptable
    compte_map: dict[str, Compte] = {}
    for numero, libelle, classe in COMPTES:
        c = Compte(numero=numero, libelle=libelle, classe=classe)
        db.session.add(c); db.session.flush()
        compte_map[numero] = c
    print(f'   {len(COMPTES)} comptes SYSCOHADA créés')

    # Journaux (par entité filiale + MDP)
    journal_map: dict[tuple, Journal] = {}  # (code_entite, code_journal) → Journal
    for entite_code, entite_obj in entite_map.items():
        for jcode, jlib, jtype in JOURNAL_TYPES:
            j = Journal(entite_id=entite_obj.id, code=jcode, libelle=jlib, type=jtype)
            db.session.add(j); db.session.flush()
            journal_map[(entite_code, jcode)] = j
    print(f'   {len(JOURNAL_TYPES) * len(ENTITES)} journaux créés')

    # Tiers
    for ttype, tcode, tnom, tpartage, tentite_code, tstatut in TIERS_DATA:
        eid = entite_map[tentite_code].id if tentite_code else None
        db.session.add(Tiers(type=ttype, code=tcode, nom=tnom,
                             partage=tpartage, entite_id=eid, statut=tstatut))
    print(f'   {len(TIERS_DATA)} tiers créés')

    db.session.flush()

    # ── Écritures de démo ─────────────────────────────────────────────────

    # ISF Conseil (IC) — services financiers
    ic = entite_map['IC']
    _add_ecriture(ic, journal_map[('IC','VE')], date(2026,1,15),
                  'Facture conseil BNP Paribas CI', 'VE-IC-001',
                  [('411',5_000_000,0),('706',0,5_000_000)], compte_map)
    _add_ecriture(ic, journal_map[('IC','BQ')], date(2026,1,20),
                  'Encaissement BNP Paribas CI', 'BQ-IC-001',
                  [('521',5_000_000,0),('411',0,5_000_000)], compte_map)
    _add_ecriture(ic, journal_map[('IC','AC')], date(2026,2,1),
                  'Facture loyer bureaux', 'AC-IC-001',
                  [('612',1_800_000,0),('401',0,1_800_000)], compte_map)
    _add_ecriture(ic, journal_map[('IC','BQ')], date(2026,2,5),
                  'Règlement loyer bureaux', 'BQ-IC-002',
                  [('401',1_800_000,0),('521',0,1_800_000)], compte_map)
    _add_ecriture(ic, journal_map[('IC','PA')], date(2026,2,28),
                  'Paie février 2026 — IC', 'PA-IC-001',
                  [('661',3_200_000,0),('421',0,2_720_000),('447',0,480_000)], compte_map)

    # Synergy Wellness (SW) — hôtellerie
    sw = entite_map['SW']
    _add_ecriture(sw, journal_map[('SW','VE')], date(2026,1,10),
                  'Facture séjour Resort Azur', 'VE-SW-001',
                  [('411',8_500_000,0),('701',0,8_500_000)], compte_map)
    _add_ecriture(sw, journal_map[('SW','BQ')], date(2026,1,18),
                  'Encaissement Resort Azur', 'BQ-SW-001',
                  [('521',8_500_000,0),('411',0,8_500_000)], compte_map)
    _add_ecriture(sw, journal_map[('SW','AC')], date(2026,2,3),
                  'Achats fournitures hôtelières', 'AC-SW-001',
                  [('601',2_400_000,0),('401',0,2_400_000)], compte_map)
    _add_ecriture(sw, journal_map[('SW','PA')], date(2026,2,28),
                  'Paie février 2026 — SW', 'PA-SW-001',
                  [('661',4_100_000,0),('421',0,3_485_000),('447',0,615_000)], compte_map)

    # Trenchaine Bois (TC) — industrie
    tc = entite_map['TC']
    _add_ecriture(tc, journal_map[('TC','VE')], date(2026,1,8),
                  'Vente bois — Scierie du Nord', 'VE-TC-001',
                  [('411',12_000_000,0),('701',0,12_000_000)], compte_map)
    _add_ecriture(tc, journal_map[('TC','BQ')], date(2026,1,22),
                  'Encaissement Scierie du Nord', 'BQ-TC-001',
                  [('521',12_000_000,0),('411',0,12_000_000)], compte_map)
    _add_ecriture(tc, journal_map[('TC','AC')], date(2026,2,2),
                  'Achats matières premières (bois brut)', 'AC-TC-001',
                  [('604',5_600_000,0),('401',0,5_600_000)], compte_map)
    _add_ecriture(tc, journal_map[('TC','PA')], date(2026,2,28),
                  'Paie février 2026 — TC', 'PA-TC-001',
                  [('661',6_300_000,0),('664',945_000,0),
                   ('421',0,5_355_000),('431',0,945_000)], compte_map)

    # AIC (AC) — immobilier/construction
    ac = entite_map['AC']
    _add_ecriture(ac, journal_map[('AC','VE')], date(2026,1,5),
                  "Vente logement T4 — Programme Cocody", 'VE-AC-001',
                  [('411',50_000_000,0),('706',0,50_000_000)], compte_map)
    _add_ecriture(ac, journal_map[('AC','BQ')], date(2026,1,25),
                  "Acompte 60 % — Programme Cocody", 'BQ-AC-001',
                  [('521',30_000_000,0),('411',0,30_000_000)], compte_map)
    _add_ecriture(ac, journal_map[('AC','AC')], date(2026,2,4),
                  'Achats ciment — Ciment Ivoire SA', 'AC-AC-001',
                  [('601',8_200_000,0),('401',0,8_200_000)], compte_map)
    _add_ecriture(ac, journal_map[('AC','PA')], date(2026,2,28),
                  'Paie février 2026 — AC', 'PA-AC-001',
                  [('661',7_800_000,0),('664',1_170_000,0),
                   ('421',0,6_630_000),('431',0,1_170_000)], compte_map)

    # MD Participations (MDP) — holding
    mdp = entite_map['MDP']
    _add_ecriture(mdp, journal_map[('MDP','BQ')], date(2026,1,31),
                  'Dividendes reçus — filiales', 'BQ-MDP-001',
                  [('521',10_000_000,0),('764',0,10_000_000)], compte_map)
    _add_ecriture(mdp, journal_map[('MDP','OD')], date(2026,2,28),
                  'Honoraires de gestion groupe', 'OD-MDP-001',
                  [('706',0,3_500_000),('411',3_500_000,0)], compte_map)

    db.session.commit()

    total_ecritures_lot1 = Ecriture.query.count()
    print(f'   {total_ecritures_lot1} écritures créées (toutes validées)')

    # ── Lot 2 — Achats ────────────────────────────────────────────────────────

    tiers_map = {t.code: t for t in Tiers.query.all()}

    # ConfigAchat — seuil de validation par entité
    SEUILS = [('MDP',20_000_000),('IC',5_000_000),('SW',10_000_000),('TC',3_000_000),('AC',8_000_000)]
    for code, seuil in SEUILS:
        db.session.add(ConfigAchat(entite_id=entite_map[code].id, seuil_validation=seuil))
    db.session.flush()
    print(f'   5 configs achat (seuils) créées')

    # ── Scénario IC : parcours complet DA → BC → réception partielle → facture comptabilisée

    ic  = entite_map['IC']
    c601 = compte_map['601']
    c604 = compte_map['604']

    da_ic = DemandeAchat(
        entite_id=ic.id, numero='DA-IC-2026-0001',
        date=date(2026,3,1), objet='Achat licences logiciels financiers',
        montant_estime=3_540_000, statut='validee',
        cree_par='Camille Saisie', valide_par='Jordan Valideur',
    )
    db.session.add(da_ic); db.session.flush()
    lda1 = LigneDA(da_id=da_ic.id, designation='Licence Bloomberg Terminal',
                   quantite=2, prix_unitaire_estime=1_200_000, compte_charge_id=c601.id)
    lda2 = LigneDA(da_id=da_ic.id, designation='Maintenance annuelle',
                   quantite=1, prix_unitaire_estime=1_140_000, compte_charge_id=c604.id)
    db.session.add_all([lda1, lda2]); db.session.flush()

    fourn_ic = tiers_map['FOURN-IC-001']
    bc_ic = BonCommande(
        entite_id=ic.id, numero='BC-IC-2026-0001',
        fournisseur_id=fourn_ic.id, da_id=da_ic.id,
        date=date(2026,3,3), statut='recu_partiel',
        cree_par='Jordan Valideur', valide_par='Jordan Valideur',
    )
    da_ic.statut = 'transformee'
    db.session.add(bc_ic); db.session.flush()
    lbc1 = LigneBC(bc_id=bc_ic.id, designation='Licence Bloomberg Terminal',
                   quantite=2, prix_unitaire=1_200_000,
                   compte_charge_id=c601.id, quantite_recue=1)
    lbc2 = LigneBC(bc_id=bc_ic.id, designation='Maintenance annuelle',
                   quantite=1, prix_unitaire=1_140_000,
                   compte_charge_id=c604.id, quantite_recue=1)
    db.session.add_all([lbc1, lbc2]); db.session.flush()

    rec_ic = Reception(
        entite_id=ic.id, numero='REC-IC-2026-0001',
        bc_id=bc_ic.id, date=date(2026,3,10),
        type='partielle', recu_par='Camille Saisie',
    )
    db.session.add(rec_ic); db.session.flush()
    db.session.add(LigneReception(reception_id=rec_ic.id, ligne_bc_id=lbc1.id, quantite_recue=1))
    db.session.add(LigneReception(reception_id=rec_ic.id, ligne_bc_id=lbc2.id, quantite_recue=1))

    # Facture (montant reçu partiel : 1 licence + 1 maintenance = 1 200 000 + 1 140 000 = 2 340 000 HT)
    # TVA 18 % → comptabilisée
    fact_ic = FactureFournisseur(
        entite_id=ic.id, numero='FACT-IC-2026-0001',
        fournisseur_id=fourn_ic.id, bc_id=bc_ic.id,
        date=date(2026,3,12), date_echeance=date(2026,4,12),
        montant_ht=2_340_000, taux_tva=18,
        montant_tva=421_200, montant_ttc=2_761_200,
        statut='comptabilisee', ecart_rapprochement=False,
    )
    db.session.add(fact_ic); db.session.flush()

    journal_ac_ic = journal_map[('IC','AC')]
    c401 = compte_map['401']; c445 = compte_map['445']
    ecriture_fact = Ecriture(
        entite_id=ic.id, journal_id=journal_ac_ic.id,
        date=date(2026,3,12),
        libelle=f'Facture {fact_ic.numero} — {fourn_ic.nom}',
        reference=fact_ic.numero, source='achats', statut='validee',
        cree_par='Alex Comptable', valide_par='Alex Comptable',
    )
    db.session.add(ecriture_fact); db.session.flush()
    db.session.add(LigneEcriture(ecriture_id=ecriture_fact.id, compte_id=c601.id,
                                  libelle='Licence Bloomberg Terminal', debit=1_200_000, credit=0))
    db.session.add(LigneEcriture(ecriture_id=ecriture_fact.id, compte_id=c604.id,
                                  libelle='Maintenance annuelle', debit=1_140_000, credit=0))
    db.session.add(LigneEcriture(ecriture_id=ecriture_fact.id, compte_id=c445.id,
                                  libelle='TVA déductible 18%', debit=421_200, credit=0))
    db.session.add(LigneEcriture(ecriture_id=ecriture_fact.id, compte_id=c401.id,
                                  libelle=f'{fourn_ic.nom} — {fact_ic.numero}',
                                  debit=0, credit=2_761_200))
    fact_ic.ecriture_id = ecriture_fact.id
    bc_ic.statut = 'facture'

    # ── Scénario SW : DA AU-DESSUS DU SEUIL (10 M) → validation Direction requise

    sw = entite_map['SW']
    da_sw_seuil = DemandeAchat(
        entite_id=sw.id, numero='DA-SW-2026-0001',
        date=date(2026,3,5),
        objet='Rénovation spa & équipements bien-être (lot 2)',
        montant_estime=14_500_000, statut='soumise',
        cree_par='Léa Saisie', valide_par=None,
    )
    db.session.add(da_sw_seuil); db.session.flush()
    db.session.add(LigneDA(da_id=da_sw_seuil.id, designation='Équipements jacuzzi premium',
                            quantite=3, prix_unitaire_estime=3_500_000, compte_charge_id=c601.id))
    db.session.add(LigneDA(da_id=da_sw_seuil.id, designation='Installation & pose',
                            quantite=1, prix_unitaire_estime=4_000_000, compte_charge_id=c604.id))

    # ── Scénario IC : DA en brouillon sur fournisseur bloqué (à montrer refusée en BC)
    # (la DA est pour le groupe, le refus intervient à la création du BC)
    fourn_blk = tiers_map['FOURN-BLK-001']
    da_ic_blk = DemandeAchat(
        entite_id=ic.id, numero='DA-IC-2026-0002',
        date=date(2026,3,14), objet='Travaux aménagement bureaux IC',
        montant_estime=2_800_000, statut='validee',
        cree_par='Camille Saisie', valide_par='Jordan Valideur',
    )
    db.session.add(da_ic_blk); db.session.flush()
    db.session.add(LigneDA(da_id=da_ic_blk.id, designation='Aménagement open space',
                            quantite=1, prix_unitaire_estime=2_800_000, compte_charge_id=c601.id))

    db.session.commit()

    total_ecritures_lot2 = Ecriture.query.count()
    print(f'   Lot 2 : 1 DA+BC+REC+Facture comptabilisée (IC) · 1 DA au-dessus seuil (SW) · 1 DA validée sur fourn. bloqué (IC)')

    # ── Modules métier — données de démo ──────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────────────
    # MODULE AC — Immobilier / VEFA
    # ──────────────────────────────────────────────────────────────────────────
    ac = entite_map['AC']
    tiers_ac_client = tiers_map['CLI-AC-001']  # Immobilière du Golfe

    # Prospect
    db.session.add(Prospect(
        entite_id=ac.id, nom='Kouassi Emmanuel', email='k.emmanuel@mail.ci',
        telephone='+225 07 00 11 22', statut='en_cours',
        projet_interet='T3 — Programme Cocody Gardens',
    ))

    # Projet
    projet_ac = ProjetImmobilier(
        entite_id=ac.id, code='PRJ-AC-001',
        nom='Résidence Cocody Gardens',
        axe_analytique='PRJ-001', budget=1_500_000_000, statut='en_cours',
    )
    db.session.add(projet_ac); db.session.flush()

    # Programme VEFA (nb_lots = nombre de logements)
    prog = ProgrammeVEFA(
        entite_id=ac.id, projet_id=projet_ac.id,
        nom='Tour A — Cocody Gardens', nb_lots=24,
    )
    db.session.add(prog); db.session.flush()

    # Tranches VEFA (pct_avancement = % que représente cette tranche)
    t1 = TrancheVEFA(programme_id=prog.id, libelle='Fondations',
                     pct_avancement=25, statut='en_cours')
    t2 = TrancheVEFA(programme_id=prog.id, libelle='Gros œuvre',
                     pct_avancement=50, statut='en_attente')
    t3 = TrancheVEFA(programme_id=prog.id, libelle='Second œuvre',
                     pct_avancement=25, statut='en_attente')
    db.session.add_all([t1, t2, t3]); db.session.flush()

    # GFA
    db.session.add(GFA(
        entite_id=ac.id, programme_id=prog.id,
        montant=800_000_000, organisme='SGBCI', statut='valide',
    ))

    # Acquéreurs
    acq1 = Acquereur(entite_id=ac.id, nom='Diallo Mariama',
                     email='m.diallo@corp.ci', telephone='+225 05 12 34 56')
    acq2 = Acquereur(entite_id=ac.id, nom='SCI Plateau Invest',
                     email='contact@plateau-invest.ci', telephone='+225 27 20 00 11')
    db.session.add_all([acq1, acq2]); db.session.flush()

    # Souscriptions (client_id → Tiers existant, projet_id → projet)
    db.session.add(Souscription(
        entite_id=ac.id, client_id=tiers_ac_client.id,
        projet_id=projet_ac.id, montant=35_000_000, statut='active',
    ))

    # Appel de fonds — tranche fondations (acquereur_id requis)
    af1 = AppelFonds(
        entite_id=ac.id, tranche_id=t1.id, acquereur_id=acq1.id,
        montant=200_000_000, statut='encaisse',
    )
    db.session.add(af1); db.session.flush()

    # Écriture encaissement : 521 / 4191
    c4191 = compte_map.get('4191')
    if c4191:
        ecr_af = _add_ecriture(ac, journal_map[('AC','BQ')], date(2025,10,15),
                               'Encaissement appel de fonds AF-AC-001', 'AF-AC-001',
                               [('521',200_000_000,0),('4191',0,200_000_000)], compte_map)
        af1.ecriture_id = ecr_af.id

    # Échéancier (acquereur_id + programme_id + echeance)
    db.session.add(EcheancierAcquereur(
        acquereur_id=acq1.id, programme_id=prog.id,
        echeance=date(2025,10,1), montant=8_750_000, statut='paye',
    ))
    db.session.add(EcheancierAcquereur(
        acquereur_id=acq1.id, programme_id=prog.id,
        echeance=date(2026,4,1), montant=8_750_000, statut='en_attente',
    ))

    db.session.flush()
    print(f'   Module AC : 1 projet · 1 programme VEFA · 3 tranches · 2 acquéreurs · 1 appel encaissé')

    # ──────────────────────────────────────────────────────────────────────────
    # MODULE TC — Production bois
    # ──────────────────────────────────────────────────────────────────────────
    tc = entite_map['TC']

    # Familles (pas de champ categorie ni libelle, seulement code+nom)
    fam_mp = FamilleArticle(entite_id=tc.id, code='MP', nom='Matières premières')
    fam_pf = FamilleArticle(entite_id=tc.id, code='PF', nom='Produits finis')
    fam_en = FamilleArticle(entite_id=tc.id, code='EN', nom='Encours de production')
    fam_sp = FamilleArticle(entite_id=tc.id, code='SP', nom='Sous-produits')
    db.session.add_all([fam_mp, fam_pf, fam_en, fam_sp]); db.session.flush()

    # Articles (champs réels : code, nom, unite, categorie, methode_valo, stock_qty, valeur_stock)
    art_bois_brut = Article(
        entite_id=tc.id, famille_id=fam_mp.id,
        code='MP-BOIS-001', nom="Grume d'iroko brut",
        unite='m3', categorie='MP', methode_valo='CUMP',
        stock_qty=70, valeur_stock=70*45_000,  # déjà consommé 50 en OP
    )
    art_planche = Article(
        entite_id=tc.id, famille_id=fam_pf.id,
        code='PF-PLA-001', nom='Planche iroko séchée 20mm',
        unite='m2', categorie='produit_fini', methode_valo='CUMP',
        stock_qty=445, valeur_stock=445*18_000,  # 350 initial + 95 produits
    )
    art_encours = Article(
        entite_id=tc.id, famille_id=fam_en.id,
        code='EN-001', nom='Bois en séchage (encours)',
        unite='m3', categorie='encours', methode_valo='CUMP',
        stock_qty=30, valeur_stock=30*52_000,
    )
    art_sciure = Article(
        entite_id=tc.id, famille_id=fam_sp.id,
        code='SP-SCI-001', nom='Sciure et copeaux',
        unite='tonne', categorie='sous_produit', methode_valo='CUMP',
        stock_qty=8, valeur_stock=8*5_000,
    )
    db.session.add_all([art_bois_brut, art_planche, art_encours, art_sciure])
    db.session.flush()

    # Ordre de production — terminé (article_fini_id, quantite, cout_total, date_debut, date_fin)
    cout_op1 = 2_000_000 + 500_000 + 800_000 + 200_000 + 1_200_000 + 300_000 + 600_000 + 150_000 + 50*45_000
    op1 = OrdreProduction(
        entite_id=tc.id, article_fini_id=art_planche.id,
        quantite=95, statut='termine', cout_total=cout_op1,
        date_debut=date(2026,1,10), date_fin=date(2026,2,9),
    )
    db.session.add(op1); db.session.flush()

    # Étapes (type, cout_matiere, cout_mo, cout_frais, quantite_encours, statut)
    for t_type, c_mo, c_fg in [
        ('sciage',   2_000_000, 500_000),
        ('sechage',    800_000, 200_000),
        ('rabotage', 1_200_000, 300_000),
        ('usinage',    600_000, 150_000),
    ]:
        db.session.add(EtapeProduction(
            ordre_id=op1.id, type=t_type,
            cout_matiere=0, cout_mo=c_mo, cout_frais=c_fg,
            quantite_encours=0, statut='termine',
        ))

    # Mouvements stock (type=entree|sortie, pas de ordre_id ni motif)
    db.session.add(MouvementStock(
        entite_id=tc.id, article_id=art_bois_brut.id,
        type='sortie', quantite=50, valeur=50*45_000,
        date=date(2026,1,10), reference='OP-001-SORTIE',
    ))
    db.session.add(MouvementStock(
        entite_id=tc.id, article_id=art_planche.id,
        type='entree', quantite=95, valeur=cout_op1,
        date=date(2026,2,9), reference='OP-001-ENTREE',
    ))

    # Ordre en cours
    op2 = OrdreProduction(
        entite_id=tc.id, article_fini_id=art_planche.id,
        quantite=60, statut='en_cours', cout_total=0,
        date_debut=date(2026,3,1), date_fin=None,
    )
    db.session.add(op2); db.session.flush()
    db.session.add(EtapeProduction(
        ordre_id=op2.id, type='sciage',
        cout_matiere=0, cout_mo=0, cout_frais=0,
        quantite_encours=60, statut='en_cours',
    ))

    db.session.flush()
    print(f'   Module TC : 4 familles · 4 articles · 1 OP terminé (4 étapes) · 1 OP en cours')

    # ──────────────────────────────────────────────────────────────────────────
    # MODULE SW — Hôtellerie / USALI
    # ──────────────────────────────────────────────────────────────────────────
    sw = entite_map['SW']

    # Import PMS 1 — déjà comptabilisé
    imp1 = ImportPMS(
        entite_id=sw.id, date=date(2026,1,31),
        source='PMS', nom_fichier='pms_janvier_2026.csv', statut='comptabilise',
    )
    db.session.add(imp1); db.session.flush()

    lignes_jan = [
        ('hebergement', 'Chambres standard — janvier',    5_200_000, 936_000),
        ('hebergement', 'Chambres suite — janvier',       2_800_000, 504_000),
        ('restauration', 'Restaurant Le Jardin — midi',   1_500_000, 270_000),
        ('restauration', 'Bar piscine — janvier',           800_000, 144_000),
        ('wellness',    'Soins spa — janvier',            1_800_000, 324_000),
        ('wellness',    'Fitness & yoga — janvier',         700_000, 126_000),
    ]
    for dept, lib, ht, tva in lignes_jan:
        db.session.add(LigneVenteSW(import_id=imp1.id, departement=dept,
                                     libelle=lib, montant_ht=ht, tva=tva))

    # Pré-écritures (compte_debit, compte_credit, montant, libelle, statut)
    dept_totaux: dict = {}
    for dept, lib, ht, tva in lignes_jan:
        d_ht, d_tva = dept_totaux.get(dept, (0, 0))
        dept_totaux[dept] = (d_ht + ht, d_tva + tva)

    DEPT_COMPTES_SEED = {'hebergement': '701', 'restauration': '701', 'wellness': '706'}
    for dept, (ht_tot, tva_tot) in dept_totaux.items():
        cpt = DEPT_COMPTES_SEED[dept]
        db.session.add(PreEcritureSW(
            import_id=imp1.id,
            compte_debit='411', compte_credit=cpt,
            montant=ht_tot,
            libelle=f'CA {dept} — {imp1.nom_fichier}',
            statut='valide',
        ))

    # Écriture comptabilisation import 1
    total_ht_jan = sum(h for h, t in dept_totaux.values())
    total_tva_jan = sum(t for h, t in dept_totaux.values())
    ecr_sw = _add_ecriture(sw, journal_map[('SW', 'VE')], date(2026, 1, 31),
                           "Chiffre d'affaires PMS — janvier 2026", 'VE-SW-PMS-001',
                           [('411', total_ht_jan + total_tva_jan, 0),
                            ('701', 0, total_ht_jan),
                            ('443', 0, total_tva_jan)], compte_map)
    imp1.ecriture_id = ecr_sw.id
    db.session.flush()

    # Import PMS 2 — importé (à traiter)
    imp2 = ImportPMS(
        entite_id=sw.id, date=date(2026,2,28),
        source='PMS', nom_fichier='pms_fevrier_2026.csv', statut='importe',
    )
    db.session.add(imp2); db.session.flush()

    lignes_fev = [
        ('hebergement', 'Chambres — février',           4_800_000, 864_000),
        ('restauration', 'Restaurant — février',        2_100_000, 378_000),
        ('wellness',    'Spa — février',                1_900_000, 342_000),
        ('wellness',    'Activités fitness — février',    800_000, 144_000),
    ]
    for dept, lib, ht, tva in lignes_fev:
        db.session.add(LigneVenteSW(import_id=imp2.id, departement=dept,
                                     libelle=lib, montant_ht=ht, tva=tva))

    db.session.flush()
    print(f'   Module SW : 2 imports PMS (1 comptabilisé + 1 à traiter) · {len(lignes_jan)+len(lignes_fev)} lignes')

    # ──────────────────────────────────────────────────────────────────────────
    # MODULE IC — Conseil / Pipeline / KYC
    # ──────────────────────────────────────────────────────────────────────────
    ic = entite_map['IC']

    # Apporteurs (champs réels : nom, telephone, email, statut_kyc, date_kyc)
    apporteur1 = Apporteur(
        entite_id=ic.id, nom='Koffi Fernand',
        email='koffi.f@conseil.ci', telephone='+225 01 23 45 67',
        statut_kyc='valide', date_kyc=date(2025,11,15),
    )
    apporteur2 = Apporteur(
        entite_id=ic.id, nom='Investica Partners SARL',
        email='contact@investica.ci', telephone='+225 27 22 33 44',
        statut_kyc='en_attente', date_kyc=None,
    )
    db.session.add_all([apporteur1, apporteur2]); db.session.flush()

    # Contrat de commission (champs réels : entite_id, apporteur_id, description)
    contrat1 = ContratCommission(
        entite_id=ic.id, apporteur_id=apporteur1.id,
        description='Contrat placement financier — Koffi Fernand',
    )
    db.session.add(contrat1); db.session.flush()

    niv1 = NiveauCommission(contrat_id=contrat1.id, niveau=1,
                            taux=1.5, description='Commission apporteur N1')
    niv2 = NiveauCommission(contrat_id=contrat1.id, niveau=2,
                            taux=0.5, description='Surcommission direction')
    db.session.add_all([niv1, niv2]); db.session.flush()

    # Dossiers (champs réels : investisseur, statut, montant, intervenant, date_creation)
    d1 = Dossier(entite_id=ic.id, investisseur='BNP Paribas CI',
                 montant=250_000_000, statut='valide',
                 intervenant='Koffi Fernand', date_creation=date(2026,1,5))
    d2 = Dossier(entite_id=ic.id, investisseur='Société Générale CI',
                 montant=180_000_000, statut='en_cours',
                 intervenant='Koffi Fernand', date_creation=date(2026,2,10))
    d3 = Dossier(entite_id=ic.id, investisseur="Côte d'Ivoire Holding",
                 montant=500_000_000, statut='en_cours',
                 intervenant='Investica Partners', date_creation=date(2026,3,1))
    d4 = Dossier(entite_id=ic.id, investisseur='Résidence Liberté SA',
                 montant=80_000_000, statut='prospect',
                 intervenant=None, date_creation=date(2026,3,15))
    db.session.add_all([d1, d2, d3, d4]); db.session.flush()

    # Étapes (libelle, date, intervenant, commentaire)
    db.session.add(EtapeDossier(dossier_id=d1.id, libelle='Qualification prospect',
                                date=date(2026,1,10), intervenant='Camille Saisie',
                                commentaire='Accord préliminaire obtenu'))
    db.session.add(EtapeDossier(dossier_id=d1.id, libelle='Validation dossier',
                                date=date(2026,2,1), intervenant='Jordan Valideur',
                                commentaire='KYC validé — dossier approuvé'))

    # Commissions (champs réels : entite_id, dossier_id, apporteur_id, niveau, taux, montant, statut)
    db.session.add(Commission(
        entite_id=ic.id, dossier_id=d1.id, apporteur_id=apporteur1.id,
        niveau=1, taux=1.5, montant=250_000_000*0.015, statut='versee',
    ))
    db.session.add(Commission(
        entite_id=ic.id, dossier_id=d1.id, apporteur_id=apporteur1.id,
        niveau=2, taux=0.5, montant=250_000_000*0.005, statut='calculee',
    ))

    # Pièces dossier (champs réels : dossier_id, nom_fichier, type, date_upload)
    db.session.add(PieceDossier(
        dossier_id=d1.id, nom_fichier='contrat_bnp_2026.pdf',
        type='contrat', date_upload=date(2026,1,15),
    ))
    db.session.add(PieceDossier(
        dossier_id=d3.id, nom_fichier='kyc_investica_2026.pdf',
        type='kyc', date_upload=date(2026,3,5),
    ))

    db.session.flush()
    db.session.commit()

    total_ecritures = Ecriture.query.count()
    print(f'   Module IC : 2 apporteurs (1 KYC✓ + 1 en attente) · 4 dossiers · 1 contrat commission · 2 commissions')
    print()
    print('✅ Base initialisée :')
    print(f'   {len(ENTITES)} entités  ·  {len(UTILISATEURS)} utilisateurs')
    print(f'   {len(COMPTES)+1} comptes SYSCOHADA  ·  {len(JOURNAL_TYPES)*len(ENTITES)} journaux')
    print(f'   {len(TIERS_DATA)} tiers  ·  {total_ecritures} écritures (Lot1 + compta achats + modules)')
    print()
    print('Scénario démo Lot 2 :')
    print('  1. IC  — BC-IC-2026-0001  envoye → réception partielle → FACT-IC-2026-0001 comptabilisée ✓')
    print('  2. SW  — DA-SW-2026-0001  soumise (14,5 M > seuil 10 M) → exige Direction pour valider')
    print('  3. IC  — DA-IC-2026-0002  validée sur Construction Rapide (bloqué) → BC refusé à la création')
    print()
    print('Scénario démo Modules métier :')
    print('  AC  — Résidence Cocody Gardens : 1 programme VEFA, 3 tranches, 2 acquéreurs, 1 appel encaissé')
    print('  TC  — OP-TC-2026-001 : 4 étapes sciage→séchage→rabotage→usinage, terminé. OP-002 en cours')
    print('  SW  — PMS janvier comptabilisé (CA 12,8 M FCFA). PMS février à valider/comptabiliser')
    print('  IC  — 4 dossiers (1 validé, 2 en cours, 1 prospect). KYC bloqué sur ISF-2026-003 (Investica)')
    print()
    print('Lancez : python3 run.py  →  http://localhost:5001')
