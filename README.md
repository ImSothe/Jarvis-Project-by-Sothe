# Jarvis Project by Sothe

Asistente de IA personal con voz para **Windows**, que controla el PC, la música y las redes, y funciona **gratis con una sola clave de IA**.

> **English, in short:** a voice-driven personal assistant for Windows built on top of the open-source [OpenJarvis](https://github.com/open-jarvis/OpenJarvis) framework (Apache 2.0). I added a Windows desktop app, hands-free voice with a local wake-word filter, PC / Spotify / OBS control, social-media analytics and a token-saving tool router. Everything runs on the free tier: the only thing you need is one free Gemini API key.

---

## Índice

1. [Qué es Jarvis](#qué-es-jarvis)
2. [Gratis: una sola clave de IA](#gratis-una-sola-clave-de-ia)
3. [Origen del proyecto y créditos](#origen-del-proyecto-y-créditos)
4. [Lo que ya venía hecho (OpenJarvis)](#lo-que-ya-venía-hecho-openjarvis)
5. [Lo que hemos añadido](#lo-que-hemos-añadido)
6. [Instalación](#instalación)
7. [Configuración](#configuración)
8. [Uso](#uso)
9. [Seguridad y privacidad](#seguridad-y-privacidad)
10. [Limitaciones](#limitaciones)
11. [Estructura del código](#estructura-del-código)
12. [Licencia](#licencia)

---

## Qué es Jarvis

Es un asistente al que le hablas y te contesta con voz, como el Jarvis de las películas. Dices *"Jarvis, pon Quevedo"* y abre Spotify y reproduce, sin tocar nada. También puede subir el volumen, abrir apps, mirar tu calendario o tu correo, instalar programas o analizar vídeos virales.

Por dentro es un **agente con herramientas**: un modelo de lenguaje (Gemini) que decide qué herramienta usar según lo que pides, la ejecuta en tu PC y te cuenta el resultado.

## Gratis: una sola clave de IA

Este Jarvis se ha hecho y probado con la **versión gratuita** de todo. Donde el proyecto original usaba servicios de pago o infraestructura propia, lo hemos sustituido por una alternativa gratuita, de modo que **solo necesitas una clave de una IA** (una [clave gratuita de Gemini](https://aistudio.google.com/apikey)) para que funcione lo esencial.

| Pieza | Alternativa de pago | Lo que usa Jarvis (gratis) |
|---|---|---|
| Modelo de lenguaje | OpenAI, Anthropic... | **Gemini** (capa gratuita) |
| Reconocimiento de voz | Servicios de pago por minuto | Gemini, y **Whisper local** (`faster-whisper`) para filtrar |
| Voz de Jarvis | TTS de pago | Gemini TTS, **Edge TTS** o **Kokoro** (local) |
| Búsqueda web | Tavily, You.com, Serply | **DuckDuckGo**, sin clave |
| Análisis de vídeo | Servicios de vídeo de pago | `yt-dlp` + la misma clave de Gemini |
| Estadísticas de X (Twitter) | API de X (de pago) | **Archivos que exportas tú**, sin API |
| Instagram y YouTube | — | APIs oficiales gratuitas (claves opcionales) |
| Gmail y Calendar | — | OAuth de Google, gratis |

Y para que la capa gratuita no se agote enseguida, se redujo el consumo de tokens (ver [ahorro de tokens](#ahorro-de-tokens)).

Dos matices para ser honestos:
- La capa gratuita de Gemini tiene **límites de uso**. Si los superas, la IA deja de responder hasta que se reinicia el cupo. Revisa las condiciones de Google sobre el uso de datos en esa capa.
- Para controlar la reproducción de **Spotify** con su API, la cuenta tiene que ser **Premium** (es un requisito de Spotify, no del proyecto).

## Origen del proyecto y créditos

Este repositorio es el resultado de tres capas de trabajo, y es importante decir quién hizo cada una:

1. **[OpenJarvis](https://github.com/open-jarvis/OpenJarvis)** (Stanford y colaboradores, Apache 2.0): el framework. Es la base y la inmensa mayoría del código y del historial de commits. **No es obra mía.**
2. **[@TenMM2](https://github.com/TenMM2)**: adaptación para un Proyecto de Fin de Grado, con Gemini como motor, las herramientas de Gmail y Calendar (con enlace de Google Meet), la interfaz del núcleo brillante, el modo llamada manos libres con detección de silencios, la palabra de activación y la pantalla de voz a pantalla completa con interrupción por voz.
3. **Sothe** ([@ImSothe](https://github.com/ImSothe)): la capa de asistente personal para Windows que describo en [Lo que hemos añadido](#lo-que-hemos-añadido).

El historial de git está conservado completo para mantener la autoría de cada persona.

## Lo que ya venía hecho (OpenJarvis)

OpenJarvis es un framework modular para asistentes de IA personales, de código abierto. Según la estructura del código, trae:

- **Agentes**: orquestador con herramientas, ReAct, investigación profunda, agente proactivo, resumen matutino, agentes programables y más.
- **Más de 50 herramientas**: ejecutar código y comandos, leer y escribir archivos, git, base de datos, navegador, búsqueda web, calculadora, PDF, imágenes, memoria y base de conocimiento.
- **Conectores**: Gmail, Google Calendar, Drive, Contactos y Tareas, Notion, Obsidian, Slack, Outlook, Strava, Oura, Spotify (lectura), noticias RSS y otros.
- **Más de 30 canales** para hablar con el asistente: Telegram, Discord, WhatsApp, Slack, Signal, Matrix, correo, SMS, webchat...
- **Motores de modelo**: Ollama, nube, LiteLLM, NVIDIA NIM y modelos locales.
- **Voz**: reconocimiento y síntesis con varios proveedores (Whisper local, Kokoro, Deepgram, Cartesia, OpenAI...).
- **Y además**: planificador de tareas, servidor MCP, sistema de seguridad y permisos de herramientas, telemetría, evaluaciones, aplicación de escritorio y frontend en React.

## Lo que hemos añadido

### Aplicación de escritorio para Windows
- Jarvis se abre como **una app con su propia ventana** (WebView2), con icono, instancia única y pantalla de arranque, no como una pestaña del navegador.
- No se congela cuando la ventana queda tapada o minimizada.
- Se **conecta solo** al abrirla, sin pulsar ningún botón, y el micrófono se libera al cerrar la ventana.
- Arranque con acceso directo, en segundo plano o desde terminal.

### Voz manos libres
- **Palabra de activación tolerante**: reconoce "Jarvis" aunque el reconocedor lo transcriba como *yarvis*, *jarbis* o *harvis*.
- **Filtro local de privacidad y coste**: antes de mandar un audio a la nube, un Whisper local comprueba si la frase empieza por "Jarvis". Si no (la tele, un vídeo, otra persona), el audio **no sale del PC**. Funciona en dos pasadas (un modelo rápido y otro más preciso de respaldo) y, si falla, no bloquea nada.
- **Vocabulario musical**: aprende los artistas que escuchas (de tus canciones con "me gusta" y tu historial reciente) para transcribir bien nombres como *Quevedo* y corregir errores antes de buscar.
- Si dices solo "Jarvis" y haces una pausa, espera la orden en vez de ignorarla.

### Ahorro de tokens
- **Enrutador de herramientas**: antes se enviaban las ~67 definiciones de herramientas en cada petición (unos 13.000 tokens). Ahora se envía un núcleo pequeño más las herramientas del tema de la petición, y el modelo puede pedir más con `more_tools`. Una orden como *"pon Quevedo"* baja de ~13.400 a ~1.800 tokens de herramientas. Se desactiva con `JARVIS_ROUTE_TOOLS=0`.
- Las tareas automáticas que gastaban cuota (análisis diario de vídeos) quedaron **fuera de este repositorio**; el análisis de vídeos sigue disponible cuando se lo pides.

### Control del PC y apps
- **Spotify** (`spotify_play`, `spotify_control`): reproduce artistas, canciones, álbumes y listas por búsqueda con **coincidencia por similitud**; pausa, volumen, aleatorio, "me gusta" y qué suena ahora. Arranca Spotify **minimizado y sin robar el foco**, para no sacarte de un juego, y **pausa el vídeo de YouTube** que esté sonando en el navegador.
- **Abrir apps** (`open_app`) desde una lista blanca que tú defines.
- **Control de medios** (`media_control`) con las teclas multimedia de Windows.
- **Control del PC** (`pc_control`): volumen, silenciar y más; suspender, apagar o reiniciar solo con confirmación explícita.
- **OBS** (`obs_control`): abrir, ver estado, empezar y parar grabación.
- **Instalar programas** (`install_app`) con `winget`, siempre preguntando antes.
- **Comprobación de tiendas** (`site_trust`): señales gratuitas de fiabilidad de una web antes de comprar.

### Contenido y redes sociales
- **Instagram**: resumen de la cuenta, últimas publicaciones y métricas de cada una.
- **X (Twitter)**: análisis de tus publicaciones a partir de archivos que exportas, sin pagar la API.
- **Vídeos virales** (`find_viral_videos`, `analyze_video`): busca en YouTube y analiza la estructura de un vídeo (gancho, ritmo, texto en pantalla).
- **Biblioteca de contenido** (`content_memory`): guarda ideas y guiones.
- **Conocimiento de producto** (`optimizer_info`): lee los datos reales de un proyecto propio para responder sin inventar.

### Calidad
- Pruebas automáticas nuevas para el enrutador de herramientas, el filtro de voz, el vocabulario musical, `site_trust` y `x_analytics`.

## Instalación

Pensado para **Windows 10/11**.

Necesitas:
- [Python 3.10–3.13](https://www.python.org/) y [uv](https://docs.astral.sh/uv/) (`winget install astral-sh.uv`).
- [Node.js 18+](https://nodejs.org/) para la interfaz.
- Una **clave gratuita de Gemini**: <https://aistudio.google.com/apikey>.

```powershell
git clone https://github.com/ImSothe/Jarvis-Project-by-Sothe.git
cd Jarvis-Project-by-Sothe

# Backend
uv pip install -e .

# Interfaz
cd frontend
npm install
cd ..
```

La primera vez que se usa la voz se descargan los modelos de Whisper (unos 150 MB el rápido y unos 460 MB el preciso).

## Configuración

1. Copia la plantilla y pon tu clave. **Es lo único obligatorio.**

   ```powershell
   copy .env.example .env
   ```

   ```
   GEMINI_API_KEY=tu_clave_aqui
   ```

   El archivo `.env` está en `.gitignore` y nunca se sube al repositorio.

2. Opcional, según lo que quieras usar:

   | Variable | Para qué |
   |---|---|
   | `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID` | Estadísticas de Instagram (cuenta profesional) |
   | `YOUTUBE_API_KEY` | Buscar vídeos virales (clave gratuita de YouTube Data API) |
   | `OPENJARVIS_SPOTIFY_CLIENT_ID`, `OPENJARVIS_SPOTIFY_CLIENT_SECRET` | Controlar Spotify (app gratuita en el panel de Spotify for Developers) |
   | `SOTHE_OPTIMIZER_DIR` | Carpeta del proyecto que consulta `optimizer_info` |

3. Para Gmail, Calendar o Spotify, autoriza la cuenta una vez:

   ```powershell
   .\jarvis-terminal.ps1 connect gmail
   .\jarvis-terminal.ps1 connect spotify
   ```

4. Las instrucciones y herramientas están escritas para **un único usuario** (el autor). Si lo usas tú, personaliza los textos de `src/openjarvis/tools/` y tu lista de apps (`~/.openjarvis/apps.json`).

## Uso

```powershell
.\start-jarvis.ps1          # arranca el servidor y la interfaz
.\make-jarvis-shortcut.ps1  # crea el acceso directo "Jarvis" en el escritorio y en Inicio
```

Abre la app y di, por ejemplo:

- *"Jarvis, pon Quevedo."*
- *"Jarvis, sube el volumen al 40."*
- *"Jarvis, abre Discord."*
- *"Jarvis, ¿qué tengo hoy en el calendario?"*
- *"Jarvis, analiza este reel."*

Las frases que **no** empiezan por "Jarvis" se ignoran.

## Seguridad y privacidad

- Las claves van en `.env` (ignorado por git). Los tokens de Google y Spotify se guardan en tu carpeta de usuario (`~/.openjarvis/connectors`), fuera del repositorio.
- Las acciones delicadas (apagar, reiniciar, instalar programas, enviar correos) **exigen confirmación explícita**.
- Solo se pueden abrir las apps de la **lista blanca**.
- El micrófono solo está abierto mientras la ventana de Jarvis está abierta.
- El filtro local evita enviar a la nube el audio que no va dirigido a Jarvis.
- Antes de publicar este repositorio se revisó el árbol de trabajo y todo el historial de git en busca de claves y datos personales.

## Limitaciones

- Las herramientas de PC, Spotify, OBS y `winget` son **solo para Windows**.
- La voz usa servicios de Gemini en la nube; con la capa gratuita hay límites de uso.
- El enrutador de herramientas se basa en palabras clave: si falla, el modelo puede cargar más herramientas con `more_tools`, a costa de un turno extra.
- El filtro local puede ignorar un "Jarvis" si hay mucho ruido o estás lejos del micrófono.
- Parte de la suite de pruebas heredada de OpenJarvis falla en Windows por motivos ajenos a este proyecto.

## Estructura del código

| Ruta | Contenido |
|---|---|
| `jarvis_app.pyw` | App de escritorio (ventana WebView2) |
| `start-jarvis.ps1`, `make-jarvis-shortcut.ps1` | Arranque y accesos directos |
| `src/openjarvis/tools/` | Herramientas (`spotify_control`, `open_app`, `pc_control`, `obs_control`, `install_app`, `instagram`, `x_analytics`, `site_trust`, `music_vocab`...) |
| `src/openjarvis/agents/tool_router.py` | Enrutador de herramientas |
| `src/openjarvis/speech/name_gate.py` | Filtro local de la palabra "Jarvis" |
| `frontend/` | Interfaz web (React) |
| `tests/` | Pruebas |

## Licencia

Distribuido bajo licencia **Apache 2.0** (ver [LICENSE](LICENSE)), la misma que OpenJarvis. Se conservan los avisos de copyright y de autoría del proyecto original y de sus colaboradores.
