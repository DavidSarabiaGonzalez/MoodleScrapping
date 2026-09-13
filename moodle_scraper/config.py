"""Config central. Sin secretos: el login es siempre manual en el navegador."""
from __future__ import annotations

BASE_URL = "https://aulavirtual.murciaeduca.es"
OUTPUT_DIR = "./salida"
FIXTURES_DIR = "./fixtures_html"
ALIASES_PATH = "./aliases.json"
ALIASES_LOCAL_PATH = "./aliases.local.json"  # solo local (ignorado por git): tus nombres cortos

# Red / robustez (petición del usuario: pausas + 2-3 reintentos + seguir)
REQUEST_DELAY_MIN = 1.0
REQUEST_DELAY_MAX = 2.5
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0
MAX_FILENAME_LEN = 150  # sin extensión; válido Windows+Linux

# Etiquetas Moodle en español (tu Aula Virtual está en español)
LABEL_GRADE = "Calificación"
LABEL_FILES_SENT = "Archivos enviados"
LABEL_FEEDBACK = "Comentarios de retroalimentación"
LABEL_SUBMISSION_COMMENTS = "Comentarios de la entrega"
LABEL_NO_GRADE = "Sin nota"
