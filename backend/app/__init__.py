from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from .models import db, bcrypt
from .tmdb_service import tmdb_service
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Configuración desde variables de entorno
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave-secreta-desarrollo')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///moviematcher.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TMDB_API_KEY'] = os.environ.get('TMDB_API_KEY')
    
    # Verificar que la API key esté configurada
    if not app.config['TMDB_API_KEY']:
        print("ADVERTENCIA: TMDB_API_KEY no está configurada en el archivo .env")
    
    # Inicializar extensiones
    db.init_app(app)
    bcrypt.init_app(app)
    CORS(app)
    
    # Configurar API key para el servicio de TMDb (ahora que tenemos contexto)
    with app.app_context():
        tmdb_service.api_key = app.config['TMDB_API_KEY']
        print(f"TMDB API Key configurada: {app.config['TMDB_API_KEY'][:10]}...")  # Muestra solo los primeros 10 caracteres
    
    # Registrar blueprints
    from .routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Crear tablas
    with app.app_context():
        db.create_all()
        print("Base de datos inicializada")
    
    return app