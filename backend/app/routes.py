from flask import Blueprint, request, jsonify, current_app
from flask_cors import CORS
from .models import db, User, Movie, Review, Rating, TVShow, TVReview, TVRating, user_movie, user_tvshow
from .tmdb_service import tmdb_service
from datetime import datetime, timedelta
import jwt
from functools import wraps
import logging

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)
CORS(api_bp)

# Configuración JWT
SECRET_KEY = 'clave-secreta-super-segura-cambiar-en-produccion'

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'message': 'Token de autenticación faltante'}), 401
        
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'message': 'Usuario no encontrado'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token inválido'}), 401
            
        return f(current_user, *args, **kwargs)
    return decorated

# --- Endpoints de Autenticación ---

@api_bp.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Faltan datos: username, email y password son requeridos'}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'El nombre de usuario ya existe'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'El email ya está registrado'}), 400
    
    new_user = User(username=data['username'], email=data['email'], password=data['password'])
    db.session.add(new_user)
    db.session.commit()
    
    token = jwt.encode({
        'user_id': new_user.id,
        'exp': datetime.utcnow() + timedelta(days=7)
    }, SECRET_KEY, algorithm='HS256')
    
    return jsonify({
        'message': 'Usuario creado exitosamente',
        'token': token,
        'user': new_user.to_dict(include_email=True)
    }), 201

@api_bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Email y password son requeridos'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({'message': 'Credenciales inválidas'}), 401
    
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(days=7)
    }, SECRET_KEY, algorithm='HS256')
    
    return jsonify({
        'message': 'Login exitoso',
        'token': token,
        'user': user.to_dict(include_email=True)
    }), 200

@api_bp.route('/auth/demo', methods=['POST'])
def get_demo_user():
    demo_user = User.query.filter_by(is_demo=True).first()
    if not demo_user:
        demo_user = User(username='usuario_demo', email='demo@moviematcher.com', password='demo123', is_demo=True)
        db.session.add(demo_user)
        db.session.commit()
    
    token = jwt.encode({
        'user_id': demo_user.id,
        'exp': datetime.utcnow() + timedelta(days=1)
    }, SECRET_KEY, algorithm='HS256')
    
    return jsonify({
        'message': 'Modo demo activado',
        'token': token,
        'user': demo_user.to_dict()
    }), 200

@api_bp.route('/auth/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    return jsonify(current_user.to_dict(include_email=True)), 200

# --- Endpoints de Búsqueda y Descubrimiento ---

@api_bp.route('/discover/movies', methods=['GET'])
def discover_movies():
    args = request.args
    tmdb_params = {'page': args.get('page', 1, type=int)}
    
    if args.get('genre'):
        tmdb_params['with_genres'] = args.get('genre')
    if args.get('year'):
        tmdb_params['primary_release_year'] = args.get('year')

    # CORREGIDO: Cambiar 'min_rating' por 'vote_average.gte'
    if args.get('vote_average.gte'):
        tmdb_params['vote_average.gte'] = args.get('vote_average.gte', type=float)
        print(f"📌 Rating mínimo recibido: {args.get('vote_average.gte')}")

    if args.get('watch_region'):
        tmdb_params['watch_region'] = args.get('watch_region')
    
    # === NUEVO: Agregar soporte para proveedor ===
    if args.get('with_watch_providers'):
        tmdb_params['with_watch_providers'] = args.get('with_watch_providers')
        print(f"🔍 Proveedor filtro: {args.get('with_watch_providers')}")  # Debug

    sort_map = {
        'popular': 'popularity.desc',
        'rating': 'vote_average.desc',
        'date': 'primary_release_date.desc',
        'title': 'original_title.asc'
    }
    sort_by = args.get('sort_by', 'popular')
    tmdb_params['sort_by'] = sort_map.get(sort_by, 'popularity.desc')
    
    mood = args.get('mood')
    if mood:
        mood_config = {
            'happy': {'with_genres': '35', 'sort_by': 'popularity.desc'},
            'sad': {'with_genres': '18', 'sort_by': 'vote_average.desc'},
            'excited': {'with_genres': '28,12,878', 'sort_by': 'popularity.desc'},
            'relaxed': {'with_genres': '16,10751', 'sort_by': 'vote_average.desc'},
            'thoughtful': {'with_genres': '99,9648', 'sort_by': 'vote_average.desc'},
            'romantic': {'with_genres': '10749', 'sort_by': 'popularity.desc'},
            'scared': {'with_genres': '27,53', 'sort_by': 'popularity.desc'},
        }
        if mood in mood_config:
            tmdb_params.update(mood_config[mood])
    
    try:
        results = tmdb_service.discover_movies(**tmdb_params)
        if results:
            return jsonify(results)
        return jsonify({'error': 'No se pudieron obtener resultados de TMDb'}), 500
    except Exception as e:
        logger.error(f"Error en discover_movies: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@api_bp.route('/discover/tv', methods=['GET'])
def discover_tv():
    args = request.args
    tmdb_params = {'page': args.get('page', 1, type=int)}
    
    if args.get('genre'):
        tmdb_params['with_genres'] = args.get('genre')
    if args.get('year'):
        tmdb_params['first_air_date_year'] = args.get('year')
    if args.get('min_rating'):
        tmdb_params['vote_average.gte'] = args.get('min_rating', type=float)

    # === NUEVO: Agregar soporte para proveedor en series ===
    if args.get('with_watch_providers'):
        tmdb_params['with_watch_providers'] = args.get('with_watch_providers')
        print(f"🔍 Proveedor filtro (TV): {args.get('with_watch_providers')}")
    
    sort_map = {
        'popular': 'popularity.desc',
        'rating': 'vote_average.desc',
        'date': 'first_air_date.desc',
        'name': 'name.asc'
    }
    sort_by = args.get('sort_by', 'popular')
    tmdb_params['sort_by'] = sort_map.get(sort_by, 'popularity.desc')
    
    try:
        results = tmdb_service.discover_tv(**tmdb_params)
        if results:
            return jsonify(results)
        return jsonify({'error': 'No se pudieron obtener resultados de TMDb'}), 500
    except Exception as e:
        logger.error(f"Error en discover_tv: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@api_bp.route('/search', methods=['GET'])
def search_all():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    
    if not query:
        return jsonify({'results': []}), 200
    
    results = tmdb_service.search_multi(query, page)
    if results:
        return jsonify(results)
    return jsonify({'error': 'Error en búsqueda'}), 500

@api_bp.route('/search/movies', methods=['GET'])
def search_movies():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    
    if not query:
        return jsonify({'results': []}), 200
    
    results = tmdb_service.search_movies(query, page)
    if results:
        return jsonify(results)
    return jsonify({'error': 'Error en búsqueda'}), 500

@api_bp.route('/search/tv', methods=['GET'])
def search_tv():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    
    if not query:
        return jsonify({'results': []}), 200
    
    results = tmdb_service.search_tv(query, page)
    if results:
        return jsonify(results)
    return jsonify({'error': 'Error en búsqueda'}), 500

# --- Endpoints para Detalles ---

@api_bp.route('/movie/<int:movie_id>', methods=['GET'])
def get_movie(movie_id):
    movie_data = tmdb_service.get_movie_details(movie_id)
    if not movie_data:
        return jsonify({'error': 'Película no encontrada'}), 404
    
    providers = tmdb_service.get_movie_watch_providers(movie_id)
    
    movie = Movie.query.filter_by(tmdb_id=movie_id).first()
    reviews = []
    ratings = []
    user_rating = None
    avg_rating = None
    
    if movie:
        reviews = [r.to_dict() for r in movie.reviews.order_by(Review.created_at.desc()).all()]
        ratings = [r.to_dict() for r in movie.ratings.all()]
        if ratings:
            avg_rating = sum(r.score for r in movie.ratings) / len(ratings)
    
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            user = User.query.get(data['user_id'])
            if user and movie:
                user_rating_obj = Rating.query.filter_by(user_id=user.id, movie_id=movie.id).first()
                if user_rating_obj:
                    user_rating = user_rating_obj.score
        except:
            pass
    
    return jsonify({
        'movie': movie_data,
        'providers': providers,
        'community': {
            'reviews': reviews,
            'average_rating': avg_rating,
            'total_ratings': len(ratings),
            'user_rating': user_rating
        }
    })

@api_bp.route('/tv/<int:tv_id>', methods=['GET'])
def get_tv_show(tv_id):
    tv_data = tmdb_service.get_tv_details(tv_id)
    if not tv_data:
        return jsonify({'error': 'Serie no encontrada'}), 404
    
    providers = tmdb_service.get_tv_watch_providers(tv_id)
    
    tv_show = TVShow.query.filter_by(tmdb_id=tv_id).first()
    reviews = []
    ratings = []
    user_rating = None
    avg_rating = None
    
    if tv_show:
        reviews = [r.to_dict() for r in tv_show.reviews.order_by(TVReview.created_at.desc()).all()]
        ratings = [r.to_dict() for r in tv_show.ratings.all()]
        if ratings:
            avg_rating = sum(r.score for r in tv_show.ratings) / len(ratings)
    
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            user = User.query.get(data['user_id'])
            if user and tv_show:
                user_rating_obj = TVRating.query.filter_by(user_id=user.id, tv_show_id=tv_show.id).first()
                if user_rating_obj:
                    user_rating = user_rating_obj.score
        except:
            pass
    
    return jsonify({
        'tv': tv_data,
        'providers': providers,
        'community': {
            'reviews': reviews,
            'average_rating': avg_rating,
            'total_ratings': len(ratings),
            'user_rating': user_rating
        }
    })

# --- Endpoints de Utilidad ---

@api_bp.route('/regions', methods=['GET'])
def get_regions():
    regions = tmdb_service.get_available_regions()
    return jsonify(regions)

@api_bp.route('/genres/movie', methods=['GET'])
def get_movie_genres():
    genres = tmdb_service.get_movie_genres()
    return jsonify(genres)

@api_bp.route('/genres/tv', methods=['GET'])
def get_tv_genres():
    genres = tmdb_service.get_tv_genres()
    return jsonify(genres)

# --- Endpoints de Interacción ---

@api_bp.route('/movie/<int:movie_id>/review', methods=['POST'])
@token_required
def add_movie_review(current_user, movie_id):
    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({'message': 'El contenido de la reseña es requerido'}), 400
    
    movie = Movie.query.filter_by(tmdb_id=movie_id).first()
    if not movie:
        movie_data = tmdb_service.get_movie_details(movie_id)
        if not movie_data:
            return jsonify({'error': 'Película no encontrada en TMDb'}), 404
        movie = Movie(
            tmdb_id=movie_id,
            title=movie_data.get('title'),
            overview=movie_data.get('overview'),
            poster_path=movie_data.get('poster_path'),
            release_date=movie_data.get('release_date'),
            genres=','.join([str(g['id']) for g in movie_data.get('genres', [])])
        )
        db.session.add(movie)
        db.session.commit()
    
    new_review = Review(content=data['content'], user_id=current_user.id, movie_id=movie.id)
    db.session.add(new_review)
    db.session.commit()
    
    return jsonify({'message': 'Reseña agregada', 'review': new_review.to_dict()}), 201

@api_bp.route('/tv/<int:tv_id>/review', methods=['POST'])
@token_required
def add_tv_review(current_user, tv_id):
    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({'message': 'El contenido de la reseña es requerido'}), 400
    
    tv_show = TVShow.query.filter_by(tmdb_id=tv_id).first()
    if not tv_show:
        tv_data = tmdb_service.get_tv_details(tv_id)
        if not tv_data:
            return jsonify({'error': 'Serie no encontrada en TMDb'}), 404
        tv_show = TVShow(
            tmdb_id=tv_id,
            name=tv_data.get('name'),
            overview=tv_data.get('overview'),
            poster_path=tv_data.get('poster_path'),
            first_air_date=tv_data.get('first_air_date'),
            genres=','.join([str(g['id']) for g in tv_data.get('genres', [])])
        )
        db.session.add(tv_show)
        db.session.commit()
    
    new_review = TVReview(content=data['content'], user_id=current_user.id, tv_show_id=tv_show.id)
    db.session.add(new_review)
    db.session.commit()
    
    return jsonify({'message': 'Reseña agregada', 'review': new_review.to_dict()}), 201

@api_bp.route('/movie/<int:movie_id>/rating', methods=['POST', 'PUT'])
@token_required
def rate_movie(current_user, movie_id):
    data = request.get_json()
    if not data or not data.get('score'):
        return jsonify({'message': 'La puntuación es requerida'}), 400
    
    score = int(data['score'])
    if score < 1 or score > 5:
        return jsonify({'message': 'La puntuación debe ser entre 1 y 5'}), 400
    
    movie = Movie.query.filter_by(tmdb_id=movie_id).first()
    if not movie:
        movie_data = tmdb_service.get_movie_details(movie_id)
        if not movie_data:
            return jsonify({'error': 'Película no encontrada en TMDb'}), 404
        movie = Movie(
            tmdb_id=movie_id,
            title=movie_data.get('title'),
            overview=movie_data.get('overview'),
            poster_path=movie_data.get('poster_path'),
            release_date=movie_data.get('release_date')
        )
        db.session.add(movie)
        db.session.commit()
    
    rating = Rating.query.filter_by(user_id=current_user.id, movie_id=movie.id).first()
    if rating:
        rating.score = score
        rating.created_at = datetime.utcnow()
        message = 'Puntuación actualizada'
    else:
        rating = Rating(score=score, user_id=current_user.id, movie_id=movie.id)
        db.session.add(rating)
        message = 'Puntuación agregada'
    
    db.session.commit()
    return jsonify({'message': message, 'rating': rating.to_dict()}), 200

@api_bp.route('/tv/<int:tv_id>/rating', methods=['POST', 'PUT'])
@token_required
def rate_tv(current_user, tv_id):
    data = request.get_json()
    if not data or not data.get('score'):
        return jsonify({'message': 'La puntuación es requerida'}), 400
    
    score = int(data['score'])
    if score < 1 or score > 5:
        return jsonify({'message': 'La puntuación debe ser entre 1 y 5'}), 400
    
    tv_show = TVShow.query.filter_by(tmdb_id=tv_id).first()
    if not tv_show:
        tv_data = tmdb_service.get_tv_details(tv_id)
        if not tv_data:
            return jsonify({'error': 'Serie no encontrada en TMDb'}), 404
        tv_show = TVShow(
            tmdb_id=tv_id,
            name=tv_data.get('name'),
            overview=tv_data.get('overview'),
            poster_path=tv_data.get('poster_path'),
            first_air_date=tv_data.get('first_air_date')
        )
        db.session.add(tv_show)
        db.session.commit()
    
    rating = TVRating.query.filter_by(user_id=current_user.id, tv_show_id=tv_show.id).first()
    if rating:
        rating.score = score
        rating.created_at = datetime.utcnow()
        message = 'Puntuación actualizada'
    else:
        rating = TVRating(score=score, user_id=current_user.id, tv_show_id=tv_show.id)
        db.session.add(rating)
        message = 'Puntuación agregada'
    
    db.session.commit()
    return jsonify({'message': message, 'rating': rating.to_dict()}), 200

# --- Endpoints para Watchlist ---

@api_bp.route('/user/watchlist/movies', methods=['GET'])
@token_required
def get_watchlist_movies(current_user):
    movies = current_user.watchlist_movies
    movie_list = [m.to_dict() for m in movies]
    return jsonify(movie_list)

@api_bp.route('/user/watchlist/movies/<int:movie_id>', methods=['POST'])
@token_required
def add_to_watchlist_movies(current_user, movie_id):
    movie = Movie.query.filter_by(tmdb_id=movie_id).first()
    if not movie:
        movie_data = tmdb_service.get_movie_details(movie_id)
        if not movie_data:
            return jsonify({'error': 'Película no encontrada'}), 404
        movie = Movie(
            tmdb_id=movie_id,
            title=movie_data.get('title'),
            overview=movie_data.get('overview'),
            poster_path=movie_data.get('poster_path'),
            release_date=movie_data.get('release_date')
        )
        db.session.add(movie)
        db.session.commit()
    
    if movie in current_user.watchlist_movies:
        return jsonify({'message': 'La película ya está en tu watchlist'}), 200
    
    current_user.watchlist_movies.append(movie)
    db.session.commit()
    return jsonify({'message': 'Añadida a watchlist'}), 200

@api_bp.route('/user/watchlist/movies/<int:movie_id>', methods=['DELETE'])
@token_required
def remove_from_watchlist_movies(current_user, movie_id):
    movie = Movie.query.filter_by(tmdb_id=movie_id).first()
    if not movie:
        return jsonify({'error': 'Película no encontrada'}), 404
    
    if movie in current_user.watchlist_movies:
        current_user.watchlist_movies.remove(movie)
        db.session.commit()
        return jsonify({'message': 'Eliminada de watchlist'}), 200
    else:
        return jsonify({'message': 'La película no estaba en la watchlist'}), 200

@api_bp.route('/user/watchlist/tv', methods=['GET'])
@token_required
def get_watchlist_tv(current_user):
    tv_shows = current_user.watchlist_tvshows
    tv_list = [t.to_dict() for t in tv_shows]
    return jsonify(tv_list)

@api_bp.route('/user/watchlist/tv/<int:tv_id>', methods=['POST'])
@token_required
def add_to_watchlist_tv(current_user, tv_id):
    tv_show = TVShow.query.filter_by(tmdb_id=tv_id).first()
    if not tv_show:
        tv_data = tmdb_service.get_tv_details(tv_id)
        if not tv_data:
            return jsonify({'error': 'Serie no encontrada'}), 404
        tv_show = TVShow(
            tmdb_id=tv_id,
            name=tv_data.get('name'),
            overview=tv_data.get('overview'),
            poster_path=tv_data.get('poster_path'),
            first_air_date=tv_data.get('first_air_date')
        )
        db.session.add(tv_show)
        db.session.commit()
    
    if tv_show in current_user.watchlist_tvshows:
        return jsonify({'message': 'La serie ya está en tu watchlist'}), 200
    
    current_user.watchlist_tvshows.append(tv_show)
    db.session.commit()
    return jsonify({'message': 'Añadida a watchlist'}), 200

@api_bp.route('/user/watchlist/tv/<int:tv_id>', methods=['DELETE'])
@token_required
def remove_from_watchlist_tv(current_user, tv_id):
    tv_show = TVShow.query.filter_by(tmdb_id=tv_id).first()
    if not tv_show:
        return jsonify({'error': 'Serie no encontrada'}), 404
    
    if tv_show in current_user.watchlist_tvshows:
        current_user.watchlist_tvshows.remove(tv_show)
        db.session.commit()
        return jsonify({'message': 'Eliminada de watchlist'}), 200
    else:
        return jsonify({'message': 'La serie no estaba en la watchlist'}), 200

# --- Health Check (solo UNA vez) ---
@api_bp.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'MovieMatcher API'})

# --- Watch Providers (solo UNA vez) ---
@api_bp.route('/watch/providers', methods=['GET'])
def get_watch_providers():
    """Obtiene la lista de proveedores de streaming"""
    try:
        # Lista manual de proveedores populares
        providers = [
            {"provider_id": 8, "provider_name": "Netflix"},
            {"provider_id": 9, "provider_name": "Amazon Prime Video"},
            {"provider_id": 337, "provider_name": "Disney Plus"},
            {"provider_id": 384, "provider_name": "HBO Max"},
            {"provider_id": 2, "provider_name": "Apple TV Plus"},
            {"provider_id": 10, "provider_name": "Paramount Plus"},
            {"provider_id": 15, "provider_name": "Hulu"},
            {"provider_id": 3, "provider_name": "Google Play Movies"},
        ]
        return jsonify(providers)
    except Exception as e:
        logger.error(f"Error getting watch providers: {e}")
        return jsonify([]), 200

@api_bp.route('/movie/<int:movie_id>/videos', methods=['GET'])
def get_movie_videos(movie_id):
    """Obtiene los trailers de una película"""
    try:
        videos = tmdb_service.get_movie_videos(movie_id)
        return jsonify(videos)
    except Exception as e:
        logger.error(f"Error getting movie videos: {e}")
        return jsonify({'error': 'Error al obtener videos'}), 500

@api_bp.route('/tv/<int:tv_id>/videos', methods=['GET'])
def get_tv_videos(tv_id):
    """Obtiene los trailers de una serie"""
    try:
        videos = tmdb_service.get_tv_videos(tv_id)
        return jsonify(videos)
    except Exception as e:
        logger.error(f"Error getting tv videos: {e}")
        return jsonify({'error': 'Error al obtener videos'}), 500