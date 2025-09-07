import os
import json
import random
from flask import Flask, request, redirect, session, url_for, render_template_string
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# --- Configuración de la aplicación ---
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Clave secreta para la sesión de Flask

# Variables de entorno para las credenciales de Spotify
CLIENT_ID =os.environ.get('SPOTIPY_CLIENT_ID')
CLIENT_SECRET = os.environ.get('SPOTIPY_CLIENT_SECRET')
REDIRECT_URI =os.environ.get('SPOTIPY_REDIRECT_URI','http://127.0.0.1:8000/callback')
SCOPES = 'user-top-read user-read-private user-read-email playlist-modify-private user-library-read playlist-read-private'
sp_oauth = SpotifyOAuth (  
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPES,
    cache_path=None
    )
# Almacenamiento temporal en memoria para los datos de sesión
session_data = {}
song_tags = {}

# --- Funciones auxiliares ---

def get_spotify_oauth():
    """Configura el objeto SpotifyOAuth."""
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPES,
        cache_path=None
    )

def get_spotify_client():
    """Obtiene un cliente de Spotify autenticado para el usuario actual."""
    token_info = session_data.get(session.get('user_id'))
    if not token_info:
        return None

    auth_manager = get_spotify_oauth()
    # Spotipy >=2.22: get_access_token devuelve directamente dict con 'access_token'
    sp = spotipy.Spotify(auth_manager=auth_manager)
    return sp

# --- Rutas de la aplicación ---
@app.route('/')
def index():
    if 'user_id' in session and session.get('user_id') in session_data:
        return redirect(url_for('dashboard'))
    return render_template_string(HTML_TEMPLATE)

@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)


@app.route('/callback')
def callback():
    # La URL completa que Spotify redirige, incluyendo ?code=
    code = request.args.get('code')
    if not code:
        return "No se recibió código de autenticación. Revisa que redirect_uri coincida.", 400

    # Intercambia el código por token
    token_info = sp_oauth.get_access_token(code, as_dict=True)
    access_token = token_info['access_token']

    sp = spotipy.Spotify(auth=access_token)
    user_id = sp.me()['id']
    session['user_id'] = user_id
    session_data[user_id] = token_info

    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    sp = get_spotify_client()
    if not sp:
        return redirect(url_for('index'))

    try:
        top_artists = sp.current_user_top_artists(limit=10, time_range='medium_term')['items']
        genres = [genre for artist in top_artists for genre in artist['genres']]
        genre_counts = {}
        for genre in genres:
            genre_counts[genre.capitalize()] = genre_counts.get(genre.capitalize(), 0) + 1
        labels = list(genre_counts.keys())
        data = list(genre_counts.values())
    except spotipy.SpotifyException as e:
        print(f"Error al obtener datos de Spotify: {e}")
        top_artists, labels, data = [], [], []

    user_tags = song_tags.get(session.get('user_id'), {})

    return render_template_string(HTML_TEMPLATE, 
                                 page_title="Dashboard",
                                 top_artists=top_artists,
                                 genres_labels=labels,
                                 genres_data=data,
                                 user_tags=user_tags)

@app.route('/playlist', methods=['GET'])
def generate_playlist():
    sp = get_spotify_client()
    if not sp:
        return redirect(url_for('index'))

    mood_param = request.args.get('mood', 'energetic').lower()
    moods = {
        'calm': {'target_valence': 0.2, 'target_energy': 0.2, 'target_tempo': 80},
        'energetic': {'target_valence': 0.8, 'target_energy': 0.9, 'target_tempo': 150},
        'happy': {'target_valence': 0.9, 'target_energy': 0.7},
        'sad': {'target_valence': 0.1, 'target_energy': 0.2},
        'melancholic': {'target_valence': 0.3, 'target_energy': 0.3},
        'going to conquer the world': {'target_valence': 0.8, 'target_energy': 0.9, 'target_danceability': 0.8},
        'random': {'target_valence': random.uniform(0, 1), 'target_energy': random.uniform(0, 1)}
    }
    
    target_features = moods.get(mood_param, moods['random'])

    try:
        top_tracks = sp.current_user_top_tracks(limit=5, time_range='medium_term')['items']
        seed_tracks = [track['id'] for track in top_tracks]
        recommendations = sp.recommendations(seed_tracks=seed_tracks, limit=20, **target_features)['tracks']
    except spotipy.SpotifyException as e:
        print(f"Error al generar playlist: {e}")
        recommendations = []

    return render_template_string(HTML_TEMPLATE, 
                                 page_title=f"Playlist {mood_param.capitalize()}",
                                 mood_playlist=recommendations,
                                 selected_mood=mood_param)

@app.route('/search', methods=['POST'])
def search():
    sp = get_spotify_client()
    if not sp:
        return redirect(url_for('index'))

    query = request.form.get('query')
    search_type = request.form.get('type')
    try:
        results = sp.search(q=query, type=search_type, limit=15)
        if search_type == 'artist':
            artists = results['artists']['items']
            tracks = []
        else:
            tracks = results['tracks']['items']
            artists = []
    except spotipy.SpotifyException as e:
        print(f"Error en la búsqueda: {e}")
        artists, tracks = [], []

    return render_template_string(HTML_TEMPLATE,
                                 page_title="Búsqueda",
                                 search_artists=artists,
                                 search_tracks=tracks,
                                 search_query=query)

@app.route('/tag_song', methods=['POST'])
def tag_song():
    user_id = session.get('user_id')
    song_id = request.form.get('song_id')
    song_name = request.form.get('song_name')
    tag = request.form.get('tag')

    if user_id and song_id and tag:
        if user_id not in song_tags:
            song_tags[user_id] = {}
        song_tags[user_id][song_id] = {'name': song_name, 'tag': tag}
        return redirect(url_for('dashboard'))
    
    return "Error al etiquetar la canción.", 400

# --- Código HTML de la UI con TailwindCSS (dentro de una string multilínea) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ page_title if page_title else 'PiMusic MVP' }}</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .container-section { @apply bg-white p-6 rounded-lg shadow-lg mb-8; }
        .btn-primary { @apply bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded-full transition-colors duration-200; }
        .input-field { @apply shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline; }
        .card { @apply bg-gray-100 p-4 rounded-lg shadow-sm mb-4; }
    </style>
</head>
<body class="bg-gray-50 font-sans text-gray-800">
    <div class="container mx-auto px-4 py-10">
        <header class="text-center mb-10">
            <h1 class="text-4xl md:text-5xl font-extrabold text-gray-900 mb-2">PiMusic</h1>
            <p class="text-lg md:text-xl text-gray-600">Tu compañero musical para el día a día.</p>
        </header>

        {% if not session.get('user_id') %}
            <div class="container-section text-center max-w-lg mx-auto">
                <h2 class="text-2xl font-semibold mb-4">Bienvenido a PiMusic</h2>
                <p class="mb-6 text-gray-600">Por favor, inicia sesión con tu cuenta de Spotify para empezar.</p>
                <a href="{{ url_for('login') }}" class="btn-primary inline-block">Iniciar sesión con Spotify</a>
            </div>
        {% else %}
            <nav class="flex justify-between items-center mb-8 bg-white p-4 rounded-lg shadow-sm">
                <a href="{{ url_for('dashboard') }}" class="text-blue-500 hover:underline">Dashboard</a>
                <a href="{{ url_for('logout') }}" class="text-red-500 hover:underline">Cerrar sesión</a>
            </nav>

            <div class="container-section">
                <h2 class="text-2xl font-semibold mb-4 text-green-700">Tus Hábitos Musicales 🎶</h2>
                <p class="mb-4 text-gray-600">Un vistazo a los artistas y géneros que más escuchas.</p>
                {% if top_artists %}
                    <div class="grid md:grid-cols-2 gap-8">
                        <div>
                            <h3 class="font-semibold mb-2 text-lg">Top 10 Artistas</h3>
                            <ul class="list-disc list-inside space-y-1">
                                {% for artist in top_artists %}
                                    <li>{{ artist.name }}</li>
                                {% endfor %}
                            </ul>
                        </div>
                        <div>
                            <h3 class="font-semibold mb-2 text-lg">Géneros Predominantes</h3>
                            <canvas id="genreChart" class="max-w-xs mx-auto"></canvas>
                        </div>
                    </div>
                {% else %}
                    <p class="text-gray-500">No se encontraron datos de tus artistas más escuchados.</p>
                {% endif %}
            </div>

            <div class="container-section">
                <h2 class="text-2xl font-semibold mb-4 text-green-700">Playlist Inteligente ✨</h2>
                <p class="mb-4 text-gray-600">Genera una playlist basada en tu estado de ánimo.</p>
                <div class="flex flex-wrap gap-2 mb-6">
                    <a href="{{ url_for('generate_playlist', mood='energetic') }}" class="btn-primary">Energética</a>
                    <a href="{{ url_for('generate_playlist', mood='calm') }}" class="btn-primary">Relajada</a>
                    <a href="{{ url_for('generate_playlist', mood='happy') }}" class="btn-primary">Feliz</a>
                    <a href="{{ url_for('generate_playlist', mood='melancholic') }}" class="btn-primary">Melancólica</a>
                    <a href="{{ url_for('generate_playlist', mood='going to conquer the world') }}" class="btn-primary">Conquistar el mundo</a>
                </div>
                
                {% if mood_playlist %}
                    <h3 class="text-lg font-semibold mb-2">Playlist {{ selected_mood.capitalize() }}</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {% for track in mood_playlist %}
                            <div class="card">
                                <p class="font-bold">{{ track.name }}</p>
                                <p class="text-sm text-gray-500">{{ track.artists[0].name }}</p>
                                <form action="{{ url_for('tag_song') }}" method="post" class="mt-2">
                                    <input type="hidden" name="song_id" value="{{ track.id }}">
                                    <input type="hidden" name="song_name" value="{{ track.name }}">
                                    <input type="text" name="tag" placeholder="Etiqueta: 'arrecho', 'eutimia'..." class="input-field text-xs">
                                    <button type="submit" class="bg-blue-500 hover:bg-blue-700 text-white text-xs font-bold py-1 px-2 rounded-full mt-2">Etiquetar</button>
                                </form>
                            </div>
                        {% endfor %}
                    </div>
                {% endif %}
            </div>

            <div class="container-section">
                <h2 class="text-2xl font-semibold mb-4 text-green-700">Descubrimiento Musical 🔍</h2>
                <form action="{{ url_for('search') }}" method="post" class="flex flex-col md:flex-row gap-4 mb-6">
                    <input type="text" name="query" placeholder="Buscar artista o género..." class="input-field flex-grow">
                    <select name="type" class="input-field">
                        <option value="artist">Artista</option>
                        <option value="track">Canción</option>
                    </select>
                    <button type="submit" class="btn-primary">Buscar</button>
                </form>
                {% if search_artists %}
                    <h3 class="text-lg font-semibold mb-2">Resultados para '{{ search_query }}' (Artistas)</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {% for artist in search_artists %}
                            <div class="card">
                                <p class="font-bold">{{ artist.name }}</p>
                                <p class="text-sm text-gray-500">Géneros: {{ ', '.join(artist.genres) if artist.genres else 'N/A' }}</p>
                            </div>
                        {% endfor %}
                    </div>
                {% elif search_tracks %}
                    <h3 class="text-lg font-semibold mb-2">Resultados para '{{ search_query }}' (Canciones)</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {% for track in search_tracks %}
                            <div class="card">
                                <p class="font-bold">{{ track.name }}</p>
                                <p class="text-sm text-gray-500">Artista: {{ track.artists[0].name }}</p>
                            </div>
                        {% endfor %}
                    </div>
                {% endif %}
            </div>
            
            <div class="container-section">
                <h2 class="text-2xl font-semibold mb-4 text-green-700">Tus Canciones Etiquetadas 🏷️</h2>
                {% if user_tags %}
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {% for song_id, tag_data in user_tags.items() %}
                            <div class="card">
                                <p class="font-bold">{{ tag_data.name }}</p>
                                <p class="text-sm text-gray-500">Etiqueta: <span class="font-semibold text-blue-600">{{ tag_data.tag }}</span></p>
                            </div>
                        {% endfor %}
                    </div>
                {% else %}
                    <p class="text-gray-500">No has etiquetado ninguna canción aún.</p>
                {% endif %}
            </div>

        {% endif %}
    </div>

    <script>
        {% if genres_labels and genres_data %}
            const ctx = document.getElementById('genreChart');
            const genreLabels = JSON.parse('{{ genres_labels | tojson }}');
            const genreData = JSON.parse('{{ genres_data | tojson }}');
            
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: genreLabels,
                    datasets: [{
                        data: genreData,
                        backgroundColor: [
                            'rgba(255, 99, 132, 0.8)',
                            'rgba(54, 162, 235, 0.8)',
                            'rgba(255, 206, 86, 0.8)',
                            'rgba(75, 192, 192, 0.8)',
                            'rgba(153, 102, 255, 0.8)',
                            'rgba(255, 159, 64, 0.8)'
                        ],
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { position: 'bottom' },
                        tooltip: { callbacks: { label: (context) => context.label + ': ' + context.raw } }
                    }
                }
            });
        {% endif %}
    </script>
</body>
</html>
"""


if __name__ == '__main__':
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        print("Error: Las variables de entorno SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET y SPOTIPY_REDIRECT_URI no están configuradas.")
        print("Asegúrate de exportarlas o configurarlas en tu sistema antes de correr la aplicación.")
    else:
        app.run( host='0.0.0.0' ,port=8000)
