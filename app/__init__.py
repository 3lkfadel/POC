import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    app = Flask(
        __name__,
        static_folder=os.path.join(base_dir, 'static'),
        static_url_path='/static',
    )

    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f'sqlite:///{os.path.join(base_dir, "mdp_demo.db")}'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'dev-secret-mdp-2025'

    db.init_app(app)

    from app.blueprints.api import api_bp
    from app.blueprints.pages import pages_bp
    from app.blueprints.compta import compta_bp
    from app.blueprints.tiers_bp import tiers_bp
    from app.blueprints.achats import achats_bp
    from app.blueprints.immobilier import immobilier_bp
    from app.blueprints.production import production_bp
    from app.blueprints.hotellerie import hotellerie_bp
    from app.blueprints.conseil import conseil_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(compta_bp)
    app.register_blueprint(tiers_bp)
    app.register_blueprint(achats_bp)
    app.register_blueprint(immobilier_bp)
    app.register_blueprint(production_bp)
    app.register_blueprint(hotellerie_bp)
    app.register_blueprint(conseil_bp)

    with app.app_context():
        db.create_all()

    return app
