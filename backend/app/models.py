from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime
import json

db = SQLAlchemy()
bcrypt = Bcrypt()

# Tabla de asociación para la watchlist de películas (muchos a muchos)
user_movie = db.Table('user_movie',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('movie_id', db.Integer, db.ForeignKey('movie.id'), primary_key=True),
    db.Column('added_at', db.DateTime, default=datetime.utcnow)
)

# Tabla de asociación para la watchlist de series
user_tvshow = db.Table('user_tvshow',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('tvshow_id', db.Integer, db.ForeignKey('tv_show.id'), primary_key=True),
    db.Column('added_at', db.DateTime, default=datetime.utcnow)
)

# Modelo de Usuario
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_demo = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    reviews = db.relationship('Review', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    tv_reviews = db.relationship('TVReview', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    ratings = db.relationship('Rating', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    tv_ratings = db.relationship('TVRating', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    # Watchlist de películas
    watchlist_movies = db.relationship('Movie', secondary=user_movie, lazy='subquery',
                                       backref=db.backref('users_watchlist', lazy=True))
    # Watchlist de series
    watchlist_tvshows = db.relationship('TVShow', secondary=user_tvshow, lazy='subquery',
                                        backref=db.backref('users_watchlist', lazy=True))

    def __init__(self, username, email, password, is_demo=False):
        self.username = username
        self.email = email
        self.is_demo = is_demo
        self.set_password(password)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def to_dict(self, include_email=False):
        data = {
            'id': self.id,
            'username': self.username,
            'is_demo': self.is_demo,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_email:
            data['email'] = self.email
        return data

# Modelo de Película
class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tmdb_id = db.Column(db.Integer, unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    overview = db.Column(db.Text)
    poster_path = db.Column(db.String(200))
    release_date = db.Column(db.String(20))
    vote_average = db.Column(db.Float, default=0)
    vote_count = db.Column(db.Integer, default=0)
    genres = db.Column(db.String(200))
    
    # Relaciones
    reviews = db.relationship('Review', backref='movie', lazy='dynamic', cascade='all, delete-orphan')
    ratings = db.relationship('Rating', backref='movie', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.tmdb_id,
            'title': self.title,
            'overview': self.overview,
            'poster_path': self.poster_path,
            'release_date': self.release_date,
            'vote_average': self.vote_average,
            'vote_count': self.vote_count,
            'genres': self.genres.split(',') if self.genres else []
        }

# Reseña de Película
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'created_at': self.created_at.isoformat() + 'Z',
            'user': self.author.username,
            'user_id': self.user_id,
            'is_demo': self.author.is_demo
        }

# Puntuación de Película
class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, nullable=False)  # 1-5
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'movie_id', name='unique_user_movie_rating'),)

    def to_dict(self):
        return {
            'id': self.id,
            'score': self.score,
            'user_id': self.user_id,
            'movie_id': self.movie_id
        }

# --- Modelos para Series de TV ---

class TVShow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tmdb_id = db.Column(db.Integer, unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    overview = db.Column(db.Text)
    poster_path = db.Column(db.String(200))
    first_air_date = db.Column(db.String(20))
    vote_average = db.Column(db.Float, default=0)
    vote_count = db.Column(db.Integer, default=0)
    genres = db.Column(db.String(200))
    
    reviews = db.relationship('TVReview', backref='tv_show', lazy='dynamic', cascade='all, delete-orphan')
    ratings = db.relationship('TVRating', backref='tv_show', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.tmdb_id,
            'name': self.name,
            'overview': self.overview,
            'poster_path': self.poster_path,
            'first_air_date': self.first_air_date,
            'vote_average': self.vote_average,
            'vote_count': self.vote_count,
            'genres': self.genres.split(',') if self.genres else []
        }

class TVReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tv_show_id = db.Column(db.Integer, db.ForeignKey('tv_show.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'created_at': self.created_at.isoformat() + 'Z',
            'user': self.author.username,
            'user_id': self.user_id,
            'is_demo': self.author.is_demo
        }

class TVRating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tv_show_id = db.Column(db.Integer, db.ForeignKey('tv_show.id'), nullable=False)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'tv_show_id', name='unique_user_tv_rating'),)

    def to_dict(self):
        return {
            'id': self.id,
            'score': self.score,
            'user_id': self.user_id,
            'tv_show_id': self.tv_show_id
        }