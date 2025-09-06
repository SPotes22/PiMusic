Este es el MVP de PiMusic, una aplicación web simple para explorar tus hábitos musicales y descubrir nueva música a través de la API de Spotify.

Requisitos
Python 3.6 o superior.

Una cuenta de desarrollador de Spotify.

Registrar una aplicación en el Spotify Developer Dashboard.

Configurar el Redirect URI de la aplicación a `http://localhost:8888/callback.`

Instalación y Configuración

Clonar este archivo o copiar su contenido a un archivo llamado app.py.

Instalar las dependencias de Python:

```
Bash

pip install flask requests spotipy
```

Configurar las variables de entorno con tus credenciales de Spotify. Esto es crucial para la autenticación. Reemplaza los valores con tus propios CLIENT_ID y CLIENT_SECRET.

En Linux/macOS:

```
Bash

export SPOTIPY_CLIENT_ID='TU_CLIENT_ID'
export SPOTIPY_CLIENT_SECRET='TU_CLIENT_SECRET'
export SPOTIPY_REDIRECT_URI='http://localhost:8888/callback'
```

En Windows:

```
Bash

set SPOTIPY_CLIENT_ID='TU_CLIENT_ID'
set SPOTIPY_CLIENT_SECRET='TU_CLIENT_SECRET'
set SPOTIPY_REDIRECT_URI='http://localhost:8888/callback'
```

Ejecutar la aplicación:

```
Bash

python app.py
```

Abrir tu navegador y navegar a http://localhost:8888.
