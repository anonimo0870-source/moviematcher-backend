import requests
from flask import current_app
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TMDbService:
    BASE_URL = "https://api.themoviedb.org/3"
    
    def __init__(self, api_key=None):
        # No intentamos acceder a current_app aquí
        self.api_key = api_key
        if not self.api_key:
            logger.warning("TMDB API Key no proporcionada en la inicialización")
    
    def _get_api_key(self):
        """Obtiene la API key, primero de la instancia, luego de la app context"""
        if self.api_key:
            return self.api_key
        
        # Intentar obtener de current_app si estamos en contexto
        try:
            return current_app.config.get('TMDB_API_KEY')
        except RuntimeError:
            # Estamos fuera de contexto de aplicación
            logger.error("No se pudo obtener TMDB_API_KEY: fuera de contexto de aplicación")
            return None
    
    def _make_request(self, endpoint, params=None):
        """Método genérico para hacer requests a la API de TMDb"""
        api_key = self._get_api_key()
        if not api_key:
            logger.error("TMDB API Key no configurada")
            return None
            
        if params is None:
            params = {}
        params['api_key'] = api_key
        params['language'] = 'es-ES'
        
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error en request a TMDb ({endpoint}): {e}")
            return None
    
    # --- Búsquedas ---
    def search_multi(self, query, page=1):
        """Búsqueda combinada de películas y personas"""
        params = {'query': query, 'page': page, 'include_adult': False}
        return self._make_request('search/multi', params)
    
    def search_movies(self, query, page=1):
        params = {'query': query, 'page': page, 'include_adult': False}
        return self._make_request('search/movie', params)
    
    def search_tv(self, query, page=1):
        params = {'query': query, 'page': page, 'include_adult': False}
        return self._make_request('search/tv', params)
    
    # --- Descubrimiento (para moods y filtros) ---
    def discover_movies(self, **kwargs):
        """
        Descubre películas con múltiples filtros.
        Parámetros comunes:
        - with_genres: IDs de géneros separados por coma
        - primary_release_year: Año
        - vote_average.gte: Puntuación mínima
        - with_people: IDs de actores/crew separados por coma
        - sort_by: popularidad.desc, vote_average.desc, etc.
        - page: Número de página
        """
        params = {
            'include_adult': False,
            'include_video': False,
            'language': 'es-ES',
            'page': kwargs.get('page', 1)
        }
        # Añadir filtros dinámicamente
        if 'with_genres' in kwargs:
            params['with_genres'] = kwargs['with_genres']
        if 'primary_release_year' in kwargs:
            params['primary_release_year'] = kwargs['primary_release_year']
        if 'vote_average.gte' in kwargs:
            params['vote_average.gte'] = kwargs['vote_average.gte']
        if 'with_people' in kwargs:
            params['with_people'] = kwargs['with_people']
        if 'sort_by' in kwargs:
            params['sort_by'] = kwargs['sort_by']
        if 'with_watch_providers' in kwargs:
            params['with_watch_providers'] = kwargs['with_watch_providers']
        if 'watch_region' in kwargs:
            params['watch_region'] = kwargs['watch_region']
            
        return self._make_request('discover/movie', params)
    
    def discover_tv(self, **kwargs):
        """Descubre series con filtros"""
        params = {
            'include_adult': False,
            'language': 'es-ES',
            'page': kwargs.get('page', 1)
        }
        if 'with_genres' in kwargs:
            params['with_genres'] = kwargs['with_genres']
        if 'first_air_date_year' in kwargs:
            params['first_air_date_year'] = kwargs['first_air_date_year']
        if 'vote_average.gte' in kwargs:
            params['vote_average.gte'] = kwargs['vote_average.gte']
        if 'with_people' in kwargs:
            params['with_people'] = kwargs['with_people']
        if 'sort_by' in kwargs:
            params['sort_by'] = kwargs['sort_by']
            
        return self._make_request('discover/tv', params)
    
    # --- Detalles ---
    def get_movie_details(self, movie_id):
        """Obtiene detalles completos de una película"""
        return self._make_request(f'movie/{movie_id}')
    
    def get_tv_details(self, tv_id):
        """Obtiene detalles completos de una serie"""
        return self._make_request(f'tv/{tv_id}')
    
    # --- Providers (Watch) ---
    def get_movie_watch_providers(self, movie_id):
        """Obtiene los proveedores de streaming para una película"""
        data = self._make_request(f'movie/{movie_id}/watch/providers')
        return data.get('results', {}) if data else {}
    
    def get_tv_watch_providers(self, tv_id):
        """Obtiene los proveedores de streaming para una serie"""
        data = self._make_request(f'tv/{tv_id}/watch/providers')
        return data.get('results', {}) if data else {}
    
    def get_available_regions(self):
        """Obtiene la lista de regiones disponibles para watch providers"""
        data = self._make_request('watch/providers/regions')
        return data.get('results', []) if data else []
    
    # --- Géneros ---
    def get_movie_genres(self):
        data = self._make_request('genre/movie/list')
        return data.get('genres', []) if data else []
    
    def get_tv_genres(self):
        data = self._make_request('genre/tv/list')
        return data.get('genres', []) if data else []
    
    def get_watch_providers(self, media_type='movie'):
        """Obtiene la lista de proveedores de streaming disponibles"""
        try:
            data = self._make_request(f'watch/providers/{media_type}')
            if data and 'results' in data:
                return data['results']
            return []
        except Exception as e:
            logger.error(f"Error getting watch providers: {e}")
            return []
        
    # --- Personas (para filtro de actor) ---
    def search_person(self, query):
        data = self._make_request('search/person', {'query': query})
        return data.get('results', []) if data else []
    
    def get_person_movie_credits(self, person_id):
        data = self._make_request(f'person/{person_id}/movie_credits')
        return data if data else None

    def get_movie_videos(self, movie_id):
        """Obtiene los videos (trailers, teasers, etc.) de una película"""
        try:
            data = self._make_request(f'movie/{movie_id}/videos')
            if data and 'results' in data:
                # Filtrar solo trailers y teasers en YouTube
                videos = data['results']
                trailers = [v for v in videos if v['site'] == 'YouTube' and v['type'] in ['Trailer', 'Teaser']]
                return trailers
            return []
        except Exception as e:
            logger.error(f"Error getting movie videos: {e}")
            return []

    def get_tv_videos(self, tv_id):
        """Obtiene los videos (trailers, teasers, etc.) de una serie"""
        try:
            data = self._make_request(f'tv/{tv_id}/videos')
            if data and 'results' in data:
                videos = data['results']
                trailers = [v for v in videos if v['site'] == 'YouTube' and v['type'] in ['Trailer', 'Teaser']]
                return trailers
            return []
        except Exception as e:
            logger.error(f"Error getting tv videos: {e}")
            return []
    
# Creamos la instancia sin API key, se configurará después
tmdb_service = TMDbService()
