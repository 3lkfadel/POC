from app import db


# ── Lot 0 ─────────────────────────────────────────────────────────────────

class Entite(db.Model):
    __tablename__ = 'entite'
    id     = db.Column(db.Integer, primary_key=True)
    code   = db.Column(db.String(10), unique=True, nullable=False)
    nom    = db.Column(db.String(100), nullable=False)
    type   = db.Column(db.String(20), nullable=False)   # holding | filiale
    devise = db.Column(db.String(5), default='XOF')

    def to_dict(self):
        return {'id': self.id, 'code': self.code, 'nom': self.nom,
                'type': self.type, 'devise': self.devise}


class Utilisateur(db.Model):
    __tablename__ = 'utilisateur'
    id        = db.Column(db.Integer, primary_key=True)
    nom       = db.Column(db.String(100), nullable=False)
    role      = db.Column(db.String(30), nullable=False)
    entite_id = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=True)
    entite    = db.relationship('Entite', backref='utilisateurs')

    def to_dict(self):
        return {'id': self.id, 'nom': self.nom, 'role': self.role,
                'entite_id': self.entite_id,
                'entite_code': self.entite.code if self.entite else None}


# ── Lot 1 — Comptabilité SYSCOHADA + Tiers ────────────────────────────────

class Compte(db.Model):
    """Plan comptable SYSCOHADA — commun au groupe (aucun entite_id)."""
    __tablename__ = 'compte'
    id      = db.Column(db.Integer, primary_key=True)
    numero  = db.Column(db.String(10), unique=True, nullable=False)
    libelle = db.Column(db.String(200), nullable=False)
    classe  = db.Column(db.Integer, nullable=False)   # 1..7

    def to_dict(self):
        return {'id': self.id, 'numero': self.numero,
                'libelle': self.libelle, 'classe': self.classe}


class Journal(db.Model):
    """Journal comptable — par entité."""
    __tablename__ = 'journal'
    id        = db.Column(db.Integer, primary_key=True)
    entite_id = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    code      = db.Column(db.String(10), nullable=False)
    libelle   = db.Column(db.String(100), nullable=False)
    type      = db.Column(db.String(5), nullable=False)  # AC|VE|BQ|CA|OD|PA
    entite    = db.relationship('Entite', backref='journaux')

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id,
                'entite_code': self.entite.code if self.entite else None,
                'code': self.code, 'libelle': self.libelle, 'type': self.type}


class Ecriture(db.Model):
    """En-tête d'écriture comptable."""
    __tablename__ = 'ecriture'
    id         = db.Column(db.Integer, primary_key=True)
    entite_id  = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    journal_id = db.Column(db.Integer, db.ForeignKey('journal.id'), nullable=False)
    date       = db.Column(db.Date, nullable=False)
    libelle    = db.Column(db.String(200), nullable=False)
    reference  = db.Column(db.String(50))
    source     = db.Column(db.String(20), default='manuel')   # manuel|...
    statut     = db.Column(db.String(15), default='brouillon')  # brouillon|validee
    cree_par   = db.Column(db.String(100))
    valide_par = db.Column(db.String(100), nullable=True)

    entite  = db.relationship('Entite', backref='ecritures')
    journal = db.relationship('Journal', backref='ecritures')
    lignes  = db.relationship('LigneEcriture', backref='ecriture',
                              cascade='all, delete-orphan', lazy='joined')

    def to_dict(self):
        return {
            'id':           self.id,
            'entite_id':    self.entite_id,
            'entite_code':  self.entite.code if self.entite else None,
            'journal_id':   self.journal_id,
            'journal_code': self.journal.code if self.journal else None,
            'journal_lib':  self.journal.libelle if self.journal else None,
            'date':         self.date.isoformat() if self.date else None,
            'libelle':      self.libelle,
            'reference':    self.reference,
            'source':       self.source,
            'statut':       self.statut,
            'cree_par':     self.cree_par,
            'valide_par':   self.valide_par,
            'lignes':       [l.to_dict() for l in self.lignes],
            'total_debit':  float(sum(l.debit  for l in self.lignes)),
            'total_credit': float(sum(l.credit for l in self.lignes)),
        }


class LigneEcriture(db.Model):
    """Ligne d'imputation comptable."""
    __tablename__ = 'ligne_ecriture'
    id             = db.Column(db.Integer, primary_key=True)
    ecriture_id    = db.Column(db.Integer, db.ForeignKey('ecriture.id'), nullable=False)
    compte_id      = db.Column(db.Integer, db.ForeignKey('compte.id'), nullable=False)
    libelle        = db.Column(db.String(200))
    debit          = db.Column(db.Numeric(15, 2), default=0)
    credit         = db.Column(db.Numeric(15, 2), default=0)
    axe_analytique = db.Column(db.String(50), nullable=True)
    compte         = db.relationship('Compte', backref='lignes')

    def to_dict(self):
        return {
            'id':             self.id,
            'ecriture_id':    self.ecriture_id,
            'compte_id':      self.compte_id,
            'compte_numero':  self.compte.numero  if self.compte else None,
            'compte_libelle': self.compte.libelle if self.compte else None,
            'libelle':        self.libelle,
            'debit':          float(self.debit),
            'credit':         float(self.credit),
            'axe_analytique': self.axe_analytique,
        }


class Tiers(db.Model):
    """Client ou fournisseur."""
    __tablename__ = 'tiers'
    id        = db.Column(db.Integer, primary_key=True)
    type      = db.Column(db.String(15), nullable=False)    # client|fournisseur
    code      = db.Column(db.String(20), unique=True, nullable=False)
    nom       = db.Column(db.String(200), nullable=False)
    partage   = db.Column(db.String(10), default='entite')  # groupe|entite
    entite_id = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=True)
    statut    = db.Column(db.String(15), nullable=True)     # en_attente|agree|actif|suspendu|bloque
    entite    = db.relationship('Entite', backref='tiers')

    def to_dict(self):
        return {
            'id':          self.id,
            'type':        self.type,
            'code':        self.code,
            'nom':         self.nom,
            'partage':     self.partage,
            'entite_id':   self.entite_id,
            'entite_code': self.entite.code if self.entite else None,
            'statut':      self.statut,
        }


# ── Lot 2 — Achats ───────────────────────────────────────────────────────────

class ConfigAchat(db.Model):
    __tablename__ = 'config_achat'
    id                = db.Column(db.Integer, primary_key=True)
    entite_id         = db.Column(db.Integer, db.ForeignKey('entite.id'), unique=True, nullable=False)
    seuil_validation  = db.Column(db.Numeric(15, 2), nullable=False)
    entite            = db.relationship('Entite', backref='config_achat', uselist=False)

    def to_dict(self):
        return {'entite_id': self.entite_id, 'seuil_validation': float(self.seuil_validation)}


class DemandeAchat(db.Model):
    __tablename__ = 'demande_achat'
    id             = db.Column(db.Integer, primary_key=True)
    entite_id      = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    numero         = db.Column(db.String(20), unique=True, nullable=False)
    date           = db.Column(db.Date, nullable=False)
    objet          = db.Column(db.String(200), nullable=False)
    montant_estime = db.Column(db.Numeric(15, 2), nullable=False)
    statut         = db.Column(db.String(20), default='brouillon')  # brouillon|soumise|validee|refusee|transformee
    cree_par       = db.Column(db.String(100))
    valide_par     = db.Column(db.String(100), nullable=True)
    motif_refus    = db.Column(db.Text, nullable=True)
    entite         = db.relationship('Entite', backref='demandes_achat')
    lignes         = db.relationship('LigneDA', backref='da', cascade='all, delete-orphan', lazy='joined')

    def to_dict(self):
        return {
            'id': self.id, 'entite_id': self.entite_id,
            'entite_code': self.entite.code if self.entite else None,
            'numero': self.numero, 'date': self.date.isoformat() if self.date else None,
            'objet': self.objet, 'montant_estime': float(self.montant_estime),
            'statut': self.statut, 'cree_par': self.cree_par,
            'valide_par': self.valide_par, 'motif_refus': self.motif_refus,
            'lignes': [l.to_dict() for l in self.lignes],
        }


class LigneDA(db.Model):
    __tablename__ = 'ligne_da'
    id                    = db.Column(db.Integer, primary_key=True)
    da_id                 = db.Column(db.Integer, db.ForeignKey('demande_achat.id'), nullable=False)
    designation           = db.Column(db.String(200), nullable=False)
    quantite              = db.Column(db.Numeric(10, 2), nullable=False)
    prix_unitaire_estime  = db.Column(db.Numeric(15, 2), nullable=False)
    compte_charge_id      = db.Column(db.Integer, db.ForeignKey('compte.id'), nullable=True)
    compte_charge         = db.relationship('Compte')

    def to_dict(self):
        return {
            'id': self.id, 'da_id': self.da_id,
            'designation': self.designation,
            'quantite': float(self.quantite),
            'prix_unitaire_estime': float(self.prix_unitaire_estime),
            'montant': float(self.quantite) * float(self.prix_unitaire_estime),
            'compte_charge_id': self.compte_charge_id,
            'compte_charge_numero': self.compte_charge.numero if self.compte_charge else None,
            'compte_charge_libelle': self.compte_charge.libelle if self.compte_charge else None,
        }


class BonCommande(db.Model):
    __tablename__ = 'bon_commande'
    id             = db.Column(db.Integer, primary_key=True)
    entite_id      = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    numero         = db.Column(db.String(20), unique=True, nullable=False)
    fournisseur_id = db.Column(db.Integer, db.ForeignKey('tiers.id'), nullable=False)
    da_id          = db.Column(db.Integer, db.ForeignKey('demande_achat.id'), nullable=True)
    date           = db.Column(db.Date, nullable=False)
    statut         = db.Column(db.String(20), default='brouillon')  # brouillon|envoye|recu_partiel|recu_total|facture|clos
    cree_par       = db.Column(db.String(100))
    valide_par     = db.Column(db.String(100), nullable=True)
    entite         = db.relationship('Entite', backref='bons_commande')
    fournisseur    = db.relationship('Tiers', backref='bons_commande')
    da             = db.relationship('DemandeAchat', backref='bc', uselist=False)
    lignes         = db.relationship('LigneBC', backref='bc', cascade='all, delete-orphan', lazy='joined')

    @property
    def montant_total_ht(self):
        return sum(float(l.quantite) * float(l.prix_unitaire) for l in self.lignes)

    def to_dict(self):
        lignes_d = [l.to_dict() for l in self.lignes]
        return {
            'id': self.id, 'entite_id': self.entite_id,
            'entite_code': self.entite.code if self.entite else None,
            'numero': self.numero,
            'fournisseur_id': self.fournisseur_id,
            'fournisseur_nom': self.fournisseur.nom if self.fournisseur else None,
            'fournisseur_statut': self.fournisseur.statut if self.fournisseur else None,
            'da_id': self.da_id, 'da_numero': self.da.numero if self.da else None,
            'date': self.date.isoformat() if self.date else None,
            'statut': self.statut, 'cree_par': self.cree_par, 'valide_par': self.valide_par,
            'lignes': lignes_d,
            'montant_total_ht': self.montant_total_ht,
        }


class LigneBC(db.Model):
    __tablename__ = 'ligne_bc'
    id               = db.Column(db.Integer, primary_key=True)
    bc_id            = db.Column(db.Integer, db.ForeignKey('bon_commande.id'), nullable=False)
    designation      = db.Column(db.String(200), nullable=False)
    quantite         = db.Column(db.Numeric(10, 2), nullable=False)
    prix_unitaire    = db.Column(db.Numeric(15, 2), nullable=False)
    compte_charge_id = db.Column(db.Integer, db.ForeignKey('compte.id'), nullable=False)
    quantite_recue   = db.Column(db.Numeric(10, 2), default=0)
    compte_charge    = db.relationship('Compte')

    def to_dict(self):
        qte = float(self.quantite)
        pu  = float(self.prix_unitaire)
        qr  = float(self.quantite_recue)
        return {
            'id': self.id, 'bc_id': self.bc_id,
            'designation': self.designation,
            'quantite': qte, 'prix_unitaire': pu, 'montant': qte * pu,
            'compte_charge_id': self.compte_charge_id,
            'compte_charge_numero': self.compte_charge.numero if self.compte_charge else None,
            'compte_charge_libelle': self.compte_charge.libelle if self.compte_charge else None,
            'quantite_recue': qr,
            'quantite_restante': qte - qr,
        }


class Reception(db.Model):
    __tablename__ = 'reception'
    id        = db.Column(db.Integer, primary_key=True)
    entite_id = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    numero    = db.Column(db.String(20), unique=True, nullable=False)
    bc_id     = db.Column(db.Integer, db.ForeignKey('bon_commande.id'), nullable=False)
    date      = db.Column(db.Date, nullable=False)
    type      = db.Column(db.String(10), nullable=False)   # partielle|totale
    recu_par  = db.Column(db.String(100))
    entite    = db.relationship('Entite', backref='receptions')
    bc        = db.relationship('BonCommande', backref='receptions')
    lignes    = db.relationship('LigneReception', backref='reception', cascade='all, delete-orphan', lazy='joined')

    def to_dict(self):
        return {
            'id': self.id, 'entite_id': self.entite_id,
            'entite_code': self.entite.code if self.entite else None,
            'numero': self.numero, 'bc_id': self.bc_id,
            'bc_numero': self.bc.numero if self.bc else None,
            'date': self.date.isoformat() if self.date else None,
            'type': self.type, 'recu_par': self.recu_par,
            'lignes': [l.to_dict() for l in self.lignes],
        }


class LigneReception(db.Model):
    __tablename__ = 'ligne_reception'
    id              = db.Column(db.Integer, primary_key=True)
    reception_id    = db.Column(db.Integer, db.ForeignKey('reception.id'), nullable=False)
    ligne_bc_id     = db.Column(db.Integer, db.ForeignKey('ligne_bc.id'), nullable=False)
    quantite_recue  = db.Column(db.Numeric(10, 2), nullable=False)
    ligne_bc        = db.relationship('LigneBC', backref='lignes_reception')

    def to_dict(self):
        lbc = self.ligne_bc
        return {
            'id': self.id, 'ligne_bc_id': self.ligne_bc_id,
            'designation': lbc.designation if lbc else None,
            'quantite_commandee': float(lbc.quantite) if lbc else None,
            'quantite_recue': float(self.quantite_recue),
        }


class FactureFournisseur(db.Model):
    __tablename__ = 'facture_fournisseur'
    id                    = db.Column(db.Integer, primary_key=True)
    entite_id             = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    numero                = db.Column(db.String(30), unique=True, nullable=False)
    fournisseur_id        = db.Column(db.Integer, db.ForeignKey('tiers.id'), nullable=False)
    bc_id                 = db.Column(db.Integer, db.ForeignKey('bon_commande.id'), nullable=True)
    date                  = db.Column(db.Date, nullable=False)
    date_echeance         = db.Column(db.Date, nullable=True)
    montant_ht            = db.Column(db.Numeric(15, 2), nullable=False)
    taux_tva              = db.Column(db.Numeric(5, 2), default=18)
    montant_tva           = db.Column(db.Numeric(15, 2), nullable=False)
    montant_ttc           = db.Column(db.Numeric(15, 2), nullable=False)
    statut                = db.Column(db.String(20), default='a_payer')  # a_payer|comptabilisee|payee
    ecriture_id           = db.Column(db.Integer, db.ForeignKey('ecriture.id'), nullable=True)
    ecart_rapprochement   = db.Column(db.Boolean, default=False)
    entite                = db.relationship('Entite', backref='factures_fournisseur')
    fournisseur           = db.relationship('Tiers', backref='factures')
    bc                    = db.relationship('BonCommande', backref='factures')
    ecriture              = db.relationship('Ecriture', backref='factures_fournisseur')

    def to_dict(self):
        return {
            'id': self.id, 'entite_id': self.entite_id,
            'entite_code': self.entite.code if self.entite else None,
            'numero': self.numero,
            'fournisseur_id': self.fournisseur_id,
            'fournisseur_nom': self.fournisseur.nom if self.fournisseur else None,
            'bc_id': self.bc_id, 'bc_numero': self.bc.numero if self.bc else None,
            'date': self.date.isoformat() if self.date else None,
            'date_echeance': self.date_echeance.isoformat() if self.date_echeance else None,
            'montant_ht': float(self.montant_ht),
            'taux_tva': float(self.taux_tva),
            'montant_tva': float(self.montant_tva),
            'montant_ttc': float(self.montant_ttc),
            'statut': self.statut,
            'ecriture_id': self.ecriture_id,
            'ecart_rapprochement': self.ecart_rapprochement,
        }


# ── Module AC — Immobilier / VEFA ────────────────────────────────────────────

class Prospect(db.Model):
    __tablename__ = 'prospect'
    id             = db.Column(db.Integer, primary_key=True)
    entite_id      = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    nom            = db.Column(db.String(200), nullable=False)
    telephone      = db.Column(db.String(30))
    email          = db.Column(db.String(200))
    projet_interet = db.Column(db.String(200))
    statut         = db.Column(db.String(20), default='en_cours')  # en_cours|converti|perdu
    entite         = db.relationship('Entite', backref='prospects')

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id, 'nom': self.nom,
                'telephone': self.telephone, 'email': self.email,
                'projet_interet': self.projet_interet, 'statut': self.statut}


class ProjetImmobilier(db.Model):
    __tablename__ = 'projet_immobilier'
    id             = db.Column(db.Integer, primary_key=True)
    entite_id      = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    code           = db.Column(db.String(20), unique=True, nullable=False)
    nom            = db.Column(db.String(200), nullable=False)
    axe_analytique = db.Column(db.String(50))
    budget         = db.Column(db.Numeric(15, 2), default=0)
    statut         = db.Column(db.String(20), default='en_cours')  # en_cours|livre|annule
    entite         = db.relationship('Entite', backref='projets_immobilier')

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id, 'code': self.code,
                'nom': self.nom, 'axe_analytique': self.axe_analytique,
                'budget': float(self.budget or 0), 'statut': self.statut}


class Souscription(db.Model):
    __tablename__ = 'souscription'
    id        = db.Column(db.Integer, primary_key=True)
    entite_id = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('tiers.id'), nullable=False)
    projet_id = db.Column(db.Integer, db.ForeignKey('projet_immobilier.id'), nullable=False)
    montant   = db.Column(db.Numeric(15, 2), nullable=False)
    statut    = db.Column(db.String(20), default='active')  # active|annulee
    entite    = db.relationship('Entite', backref='souscriptions')
    client    = db.relationship('Tiers', backref='souscriptions')
    projet    = db.relationship('ProjetImmobilier', backref='souscriptions')

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id,
                'client_id': self.client_id, 'client_nom': self.client.nom if self.client else None,
                'projet_id': self.projet_id, 'projet_nom': self.projet.nom if self.projet else None,
                'montant': float(self.montant), 'statut': self.statut}


class Acquereur(db.Model):
    __tablename__ = 'acquereur'
    id        = db.Column(db.Integer, primary_key=True)
    entite_id = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    nom       = db.Column(db.String(200), nullable=False)
    telephone = db.Column(db.String(30))
    email     = db.Column(db.String(200))
    entite    = db.relationship('Entite', backref='acquereurs')

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id,
                'nom': self.nom, 'telephone': self.telephone, 'email': self.email}


class ProgrammeVEFA(db.Model):
    __tablename__ = 'programme_vefa'
    id        = db.Column(db.Integer, primary_key=True)
    entite_id = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    projet_id = db.Column(db.Integer, db.ForeignKey('projet_immobilier.id'), nullable=False)
    nom       = db.Column(db.String(200), nullable=False)
    nb_lots   = db.Column(db.Integer, default=0)
    entite    = db.relationship('Entite', backref='programmes_vefa')
    projet    = db.relationship('ProjetImmobilier', backref='programmes')
    tranches  = db.relationship('TrancheVEFA', backref='programme', cascade='all, delete-orphan', lazy='joined')
    gfas      = db.relationship('GFA', backref='programme', cascade='all, delete-orphan', lazy='joined')

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id,
                'projet_id': self.projet_id, 'projet_nom': self.projet.nom if self.projet else None,
                'nom': self.nom, 'nb_lots': self.nb_lots,
                'tranches': [t.to_dict() for t in self.tranches],
                'gfas': [g.to_dict() for g in self.gfas]}


class TrancheVEFA(db.Model):
    __tablename__ = 'tranche_vefa'
    id             = db.Column(db.Integer, primary_key=True)
    programme_id   = db.Column(db.Integer, db.ForeignKey('programme_vefa.id'), nullable=False)
    libelle        = db.Column(db.String(200), nullable=False)
    pct_avancement = db.Column(db.Numeric(5, 2), nullable=False)
    statut         = db.Column(db.String(20), default='en_attente')  # en_attente|en_cours|livre
    appels_fonds   = db.relationship('AppelFonds', backref='tranche', cascade='all, delete-orphan', lazy='joined')

    def to_dict(self):
        return {'id': self.id, 'programme_id': self.programme_id,
                'libelle': self.libelle, 'pct_avancement': float(self.pct_avancement),
                'statut': self.statut}


class AppelFonds(db.Model):
    __tablename__ = 'appel_fonds'
    id           = db.Column(db.Integer, primary_key=True)
    entite_id    = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    tranche_id   = db.Column(db.Integer, db.ForeignKey('tranche_vefa.id'), nullable=False)
    acquereur_id = db.Column(db.Integer, db.ForeignKey('acquereur.id'), nullable=False)
    montant      = db.Column(db.Numeric(15, 2), nullable=False)
    statut       = db.Column(db.String(20), default='emis')  # emis|encaisse
    ecriture_id  = db.Column(db.Integer, db.ForeignKey('ecriture.id'), nullable=True)
    entite       = db.relationship('Entite', backref='appels_fonds')
    acquereur    = db.relationship('Acquereur', backref='appels_fonds')
    ecriture     = db.relationship('Ecriture', backref='appels_fonds')

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id,
                'tranche_id': self.tranche_id,
                'tranche_libelle': self.tranche.libelle if self.tranche else None,
                'acquereur_id': self.acquereur_id,
                'acquereur_nom': self.acquereur.nom if self.acquereur else None,
                'montant': float(self.montant), 'statut': self.statut,
                'ecriture_id': self.ecriture_id}


class GFA(db.Model):
    __tablename__ = 'gfa'
    id           = db.Column(db.Integer, primary_key=True)
    entite_id    = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    programme_id = db.Column(db.Integer, db.ForeignKey('programme_vefa.id'), nullable=False)
    montant      = db.Column(db.Numeric(15, 2), nullable=False)
    organisme    = db.Column(db.String(200))
    statut       = db.Column(db.String(20), default='en_attente')  # valide|expire|en_attente
    entite       = db.relationship('Entite', backref='gfas')

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id,
                'programme_id': self.programme_id,
                'montant': float(self.montant), 'organisme': self.organisme,
                'statut': self.statut}


class EcheancierAcquereur(db.Model):
    __tablename__ = 'echeancier_acquereur'
    id           = db.Column(db.Integer, primary_key=True)
    acquereur_id = db.Column(db.Integer, db.ForeignKey('acquereur.id'), nullable=False)
    programme_id = db.Column(db.Integer, db.ForeignKey('programme_vefa.id'), nullable=False)
    echeance     = db.Column(db.Date, nullable=False)
    montant      = db.Column(db.Numeric(15, 2), nullable=False)
    statut       = db.Column(db.String(20), default='en_attente')  # en_attente|paye
    acquereur    = db.relationship('Acquereur', backref='echeances')
    programme    = db.relationship('ProgrammeVEFA', backref='echeances')

    def to_dict(self):
        return {'id': self.id,
                'acquereur_id': self.acquereur_id,
                'acquereur_nom': self.acquereur.nom if self.acquereur else None,
                'programme_id': self.programme_id,
                'programme_nom': self.programme.nom if self.programme else None,
                'echeance': self.echeance.isoformat() if self.echeance else None,
                'montant': float(self.montant), 'statut': self.statut}


# ── Module TC — Production bois ──────────────────────────────────────────────

class FamilleArticle(db.Model):
    __tablename__ = 'famille_article'
    id        = db.Column(db.Integer, primary_key=True)
    entite_id = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    code      = db.Column(db.String(20), nullable=False)
    nom       = db.Column(db.String(200), nullable=False)
    entite    = db.relationship('Entite', backref='familles_article')

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id,
                'code': self.code, 'nom': self.nom}


class Article(db.Model):
    __tablename__ = 'article'
    id           = db.Column(db.Integer, primary_key=True)
    entite_id    = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    famille_id   = db.Column(db.Integer, db.ForeignKey('famille_article.id'), nullable=True)
    code         = db.Column(db.String(30), unique=True, nullable=False)
    nom          = db.Column(db.String(200), nullable=False)
    unite        = db.Column(db.String(20), default='m³')
    categorie    = db.Column(db.String(20), nullable=False)  # MP|marchandise|encours|PF|sous_produit
    methode_valo = db.Column(db.String(10), default='CUMP')  # CUMP|FIFO
    stock_qty    = db.Column(db.Numeric(12, 4), default=0)
    valeur_stock = db.Column(db.Numeric(15, 2), default=0)
    entite       = db.relationship('Entite', backref='articles')
    famille      = db.relationship('FamilleArticle', backref='articles')

    @property
    def cump(self):
        qty = float(self.stock_qty or 0)
        return float(self.valeur_stock or 0) / qty if qty > 0 else 0

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id,
                'famille_id': self.famille_id,
                'famille_nom': self.famille.nom if self.famille else None,
                'code': self.code, 'nom': self.nom, 'unite': self.unite,
                'categorie': self.categorie, 'methode_valo': self.methode_valo,
                'stock_qty': float(self.stock_qty or 0),
                'valeur_stock': float(self.valeur_stock or 0),
                'cump': self.cump}


class OrdreProduction(db.Model):
    __tablename__ = 'ordre_production'
    id              = db.Column(db.Integer, primary_key=True)
    entite_id       = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    article_fini_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=False)
    quantite        = db.Column(db.Numeric(12, 4), nullable=False)
    statut          = db.Column(db.String(20), default='ouvert')  # ouvert|en_cours|termine
    cout_total      = db.Column(db.Numeric(15, 2), default=0)
    date_debut      = db.Column(db.Date, nullable=True)
    date_fin        = db.Column(db.Date, nullable=True)
    entite          = db.relationship('Entite', backref='ordres_production')
    article_fini    = db.relationship('Article', foreign_keys=[article_fini_id], backref='ordres')
    etapes          = db.relationship('EtapeProduction', backref='ordre',
                                      cascade='all, delete-orphan', lazy='joined')

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id,
                'article_fini_id': self.article_fini_id,
                'article_fini_nom': self.article_fini.nom if self.article_fini else None,
                'quantite': float(self.quantite), 'statut': self.statut,
                'cout_total': float(self.cout_total or 0),
                'date_debut': self.date_debut.isoformat() if self.date_debut else None,
                'date_fin': self.date_fin.isoformat() if self.date_fin else None,
                'etapes': [e.to_dict() for e in self.etapes]}


class EtapeProduction(db.Model):
    __tablename__ = 'etape_production'
    id               = db.Column(db.Integer, primary_key=True)
    ordre_id         = db.Column(db.Integer, db.ForeignKey('ordre_production.id'), nullable=False)
    type             = db.Column(db.String(20), nullable=False)  # sciage|sechage|rabotage|usinage
    cout_matiere     = db.Column(db.Numeric(15, 2), default=0)
    cout_mo          = db.Column(db.Numeric(15, 2), default=0)
    cout_frais       = db.Column(db.Numeric(15, 2), default=0)
    quantite_encours = db.Column(db.Numeric(12, 4), default=0)
    statut           = db.Column(db.String(20), default='en_cours')  # en_cours|termine

    @property
    def cout_etape(self):
        return float(self.cout_matiere or 0) + float(self.cout_mo or 0) + float(self.cout_frais or 0)

    def to_dict(self):
        return {'id': self.id, 'ordre_id': self.ordre_id, 'type': self.type,
                'cout_matiere': float(self.cout_matiere or 0),
                'cout_mo': float(self.cout_mo or 0),
                'cout_frais': float(self.cout_frais or 0),
                'cout_etape': self.cout_etape,
                'quantite_encours': float(self.quantite_encours or 0),
                'statut': self.statut}


class MouvementStock(db.Model):
    __tablename__ = 'mouvement_stock'
    id         = db.Column(db.Integer, primary_key=True)
    entite_id  = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=False)
    type       = db.Column(db.String(10), nullable=False)  # entree|sortie
    quantite   = db.Column(db.Numeric(12, 4), nullable=False)
    valeur     = db.Column(db.Numeric(15, 2), nullable=False)
    date       = db.Column(db.Date, nullable=False)
    reference  = db.Column(db.String(50))
    entite     = db.relationship('Entite', backref='mouvements_stock')
    article    = db.relationship('Article', backref='mouvements')

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id,
                'article_id': self.article_id,
                'article_nom': self.article.nom if self.article else None,
                'article_code': self.article.code if self.article else None,
                'type': self.type, 'quantite': float(self.quantite),
                'valeur': float(self.valeur),
                'date': self.date.isoformat() if self.date else None,
                'reference': self.reference}


# ── Module SW — Hôtellerie / USALI ───────────────────────────────────────────

class ImportPMS(db.Model):
    __tablename__ = 'import_pms'
    id          = db.Column(db.Integer, primary_key=True)
    entite_id   = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    date        = db.Column(db.Date, nullable=False)
    source      = db.Column(db.String(10), nullable=False)  # PMS|POS
    statut      = db.Column(db.String(20), default='importe')  # importe|controle|comptabilise
    nom_fichier = db.Column(db.String(200))
    ecriture_id = db.Column(db.Integer, db.ForeignKey('ecriture.id'), nullable=True)
    entite      = db.relationship('Entite', backref='imports_pms')
    ecriture    = db.relationship('Ecriture', backref='imports_pms')
    lignes      = db.relationship('LigneVenteSW', backref='import_pms_ref',
                                  cascade='all, delete-orphan', lazy='joined')
    pre_ecritures = db.relationship('PreEcritureSW', backref='import_pms_ref',
                                    cascade='all, delete-orphan', lazy='joined')

    def to_dict(self):
        total_ht = sum(float(l.montant_ht) for l in self.lignes)
        return {'id': self.id, 'entite_id': self.entite_id,
                'date': self.date.isoformat() if self.date else None,
                'source': self.source, 'statut': self.statut,
                'nom_fichier': self.nom_fichier, 'ecriture_id': self.ecriture_id,
                'nb_lignes': len(self.lignes), 'total_ht': total_ht,
                'lignes': [l.to_dict() for l in self.lignes]}


class LigneVenteSW(db.Model):
    __tablename__ = 'ligne_vente_sw'
    id          = db.Column(db.Integer, primary_key=True)
    import_id   = db.Column(db.Integer, db.ForeignKey('import_pms.id'), nullable=False)
    departement = db.Column(db.String(20), nullable=False)  # hebergement|restauration|wellness
    libelle     = db.Column(db.String(200))
    montant_ht  = db.Column(db.Numeric(15, 2), nullable=False)
    tva         = db.Column(db.Numeric(15, 2), default=0)

    def to_dict(self):
        return {'id': self.id, 'import_id': self.import_id,
                'departement': self.departement, 'libelle': self.libelle,
                'montant_ht': float(self.montant_ht), 'tva': float(self.tva or 0)}


class PreEcritureSW(db.Model):
    __tablename__ = 'pre_ecriture_sw'
    id            = db.Column(db.Integer, primary_key=True)
    import_id     = db.Column(db.Integer, db.ForeignKey('import_pms.id'), nullable=False)
    compte_debit  = db.Column(db.String(10))
    compte_credit = db.Column(db.String(10))
    montant       = db.Column(db.Numeric(15, 2))
    libelle       = db.Column(db.String(200))
    statut        = db.Column(db.String(20), default='a_valider')  # a_valider|valide

    def to_dict(self):
        return {'id': self.id, 'import_id': self.import_id,
                'compte_debit': self.compte_debit, 'compte_credit': self.compte_credit,
                'montant': float(self.montant or 0), 'libelle': self.libelle,
                'statut': self.statut}


# ── Module IC — Conseil / Pipeline / KYC ─────────────────────────────────────

class Dossier(db.Model):
    __tablename__ = 'dossier'
    id            = db.Column(db.Integer, primary_key=True)
    entite_id     = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    investisseur  = db.Column(db.String(200), nullable=False)
    statut        = db.Column(db.String(20), default='prospect')  # prospect|en_cours|valide|rejete
    montant       = db.Column(db.Numeric(15, 2))
    intervenant   = db.Column(db.String(100))
    date_creation = db.Column(db.Date, nullable=False)
    date_maj      = db.Column(db.Date, nullable=True)
    entite        = db.relationship('Entite', backref='dossiers')
    etapes        = db.relationship('EtapeDossier', backref='dossier',
                                    cascade='all, delete-orphan', lazy='joined')
    pieces        = db.relationship('PieceDossier', backref='dossier',
                                    cascade='all, delete-orphan', lazy='joined')

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id,
                'investisseur': self.investisseur, 'statut': self.statut,
                'montant': float(self.montant) if self.montant else None,
                'intervenant': self.intervenant,
                'date_creation': self.date_creation.isoformat() if self.date_creation else None,
                'date_maj': self.date_maj.isoformat() if self.date_maj else None,
                'nb_etapes': len(self.etapes),
                'etapes': [e.to_dict() for e in self.etapes]}


class EtapeDossier(db.Model):
    __tablename__ = 'etape_dossier'
    id          = db.Column(db.Integer, primary_key=True)
    dossier_id  = db.Column(db.Integer, db.ForeignKey('dossier.id'), nullable=False)
    libelle     = db.Column(db.String(200), nullable=False)
    date        = db.Column(db.Date, nullable=False)
    intervenant = db.Column(db.String(100))
    commentaire = db.Column(db.Text)

    def to_dict(self):
        return {'id': self.id, 'dossier_id': self.dossier_id,
                'libelle': self.libelle,
                'date': self.date.isoformat() if self.date else None,
                'intervenant': self.intervenant, 'commentaire': self.commentaire}


class Apporteur(db.Model):
    __tablename__ = 'apporteur'
    id         = db.Column(db.Integer, primary_key=True)
    entite_id  = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    nom        = db.Column(db.String(200), nullable=False)
    telephone  = db.Column(db.String(30))
    email      = db.Column(db.String(200))
    statut_kyc = db.Column(db.String(20), default='en_attente')  # en_attente|valide|rejete
    date_kyc   = db.Column(db.Date, nullable=True)
    entite     = db.relationship('Entite', backref='apporteurs')

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id,
                'nom': self.nom, 'telephone': self.telephone, 'email': self.email,
                'statut_kyc': self.statut_kyc,
                'date_kyc': self.date_kyc.isoformat() if self.date_kyc else None}


class ContratCommission(db.Model):
    __tablename__ = 'contrat_commission'
    id           = db.Column(db.Integer, primary_key=True)
    entite_id    = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    apporteur_id = db.Column(db.Integer, db.ForeignKey('apporteur.id'), nullable=False)
    description  = db.Column(db.Text)
    entite       = db.relationship('Entite', backref='contrats_commission')
    apporteur    = db.relationship('Apporteur', backref='contrats')
    niveaux      = db.relationship('NiveauCommission', backref='contrat',
                                   cascade='all, delete-orphan', lazy='joined')

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id,
                'apporteur_id': self.apporteur_id,
                'apporteur_nom': self.apporteur.nom if self.apporteur else None,
                'description': self.description,
                'niveaux': [n.to_dict() for n in self.niveaux]}


class NiveauCommission(db.Model):
    __tablename__ = 'niveau_commission'
    id          = db.Column(db.Integer, primary_key=True)
    contrat_id  = db.Column(db.Integer, db.ForeignKey('contrat_commission.id'), nullable=False)
    niveau      = db.Column(db.Integer, nullable=False)
    taux        = db.Column(db.Numeric(5, 2), nullable=False)
    description = db.Column(db.String(200))

    def to_dict(self):
        return {'id': self.id, 'contrat_id': self.contrat_id,
                'niveau': self.niveau, 'taux': float(self.taux),
                'description': self.description}


class Commission(db.Model):
    __tablename__ = 'commission'
    id           = db.Column(db.Integer, primary_key=True)
    entite_id    = db.Column(db.Integer, db.ForeignKey('entite.id'), nullable=False)
    dossier_id   = db.Column(db.Integer, db.ForeignKey('dossier.id'), nullable=False)
    apporteur_id = db.Column(db.Integer, db.ForeignKey('apporteur.id'), nullable=False)
    niveau       = db.Column(db.Integer)
    taux         = db.Column(db.Numeric(5, 2))
    montant      = db.Column(db.Numeric(15, 2))
    statut       = db.Column(db.String(20), default='calculee')  # calculee|versee
    entite       = db.relationship('Entite', backref='commissions')
    dossier      = db.relationship('Dossier', backref='commissions')
    apporteur    = db.relationship('Apporteur', backref='commissions')

    def to_dict(self):
        return {'id': self.id, 'entite_id': self.entite_id,
                'dossier_id': self.dossier_id,
                'investisseur': self.dossier.investisseur if self.dossier else None,
                'apporteur_id': self.apporteur_id,
                'apporteur_nom': self.apporteur.nom if self.apporteur else None,
                'niveau': self.niveau, 'taux': float(self.taux or 0),
                'montant': float(self.montant or 0), 'statut': self.statut}


class PieceDossier(db.Model):
    __tablename__ = 'piece_dossier'
    id          = db.Column(db.Integer, primary_key=True)
    dossier_id  = db.Column(db.Integer, db.ForeignKey('dossier.id'), nullable=False)
    nom_fichier = db.Column(db.String(200))
    type        = db.Column(db.String(20), default='autre')  # kyc|contrat|rapport|autre
    date_upload = db.Column(db.Date, nullable=False)

    def to_dict(self):
        return {'id': self.id, 'dossier_id': self.dossier_id,
                'nom_fichier': self.nom_fichier, 'type': self.type,
                'date_upload': self.date_upload.isoformat() if self.date_upload else None}
