# app/openlibrary.py
import requests
import logging

# Configura logger para registrar mensajes en lugar de usar print()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ======================================================
# Tabla de mapeo de categorías de OpenLibrary a internas
# ======================================================
# Si OpenLibrary devuelve un subject que coincida con una key aquí,
# se usará la categoría interna como valor de nuestro sistema.
MAPEO_CATEGORIAS = {
    "fiction": "novela",
    "novel": "novela",
    "detective and mystery stories": "novela",
    "police procedural": "thriller",
    "science fiction": "ciencia_ficcion",
    "fantasy": "fantasía",
    "thrillers": "thriller",
    "horror": "terror",
    "romance": "romance",
    "historical fiction": "novela_historica",
    "history": "historia",
    "biography": "biografia",
    "short stories": "cuento",
    "poetry": "poesia",
    "drama": "teatro",
    "comedies": "comedia",
    "juvenile fiction": "juvenil",
    "young adult fiction": "juvenil",
    "graphic novels": "historieta",
    "comics": "historieta",
    "philosophy": "filosofia",
    "essays": "ensayo",
    "true crime": "ficcion_criminal",
    "crime fiction": "ficcion_criminal",
    "political satire": "sátira",
    "satire": "sátira",
    "classic fiction": "clasico",
    "classic literature": "clasico",
    "magical realism": "realismo_magico"
}


def obtener_datos_libro(isbn: str) -> dict | None:
    """
    Consulta la API de OpenLibrary usando un ISBN
    y devuelve un diccionario con metadatos mapeados a nuestro sistema.
    """
    # Construir URL base de bibkeys
    base_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"

    try:
        # Hacer la petición principal
        resp = requests.get(base_url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"[OpenLibrary] Error en bibkeys: {e}")
        return {"success": False, "error": str(e)}

    libro = data.get(f"ISBN:{isbn}")
    if not libro:
        # Si no se encuentra información
        return {"success": False, "error": "Libro no encontrado"}

    # Extraer campos principales: título, autores, editorial, fecha
    titulo = libro.get('title', '')
    
    autores = ', '.join(
        a['name'] for a in libro.get('authors', [])
    ) if libro.get('authors') else ''

    editorial = ', '.join(
        p['name'] for p in libro.get('publishers', [])
    ) if libro.get('publishers') else ''

    fecha = libro.get('publish_date', '')
    
    # Extraer descripción, si existe
    # Puede venir como string o dict
    descripcion = ''
    desc_raw = libro.get('description')
    if isinstance(desc_raw, dict):
        descripcion = desc_raw.get('value', '')
    elif isinstance(desc_raw, str):
        descripcion = desc_raw

    # Intentar obtener URL de portada
    # Si no viene, usar covers.openlibrary.org fallback
    portada_url = None
    if 'cover' in libro:
        portada_url = libro['cover'].get('large') or libro['cover'].get('medium')

    if not portada_url:
        fallback_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"
        try:
            # Usamos HEAD para verificar si existe sin descargar todo
            head_resp = requests.head(fallback_url, timeout=5)
            if head_resp.ok:
                portada_url = fallback_url
        except requests.exceptions.RequestException as e:
            logger.warning(f"[OpenLibrary] Fallback cover error: {e}")
            portada_url = None
            
    # Extraer subject para categorizar con fallback
    categoria = "otros"
    edition_key = libro.get('key')
    subjects = []

    if edition_key:
        # Si existe edition key, hacemos segunda consulta
        olid = edition_key.split('/')[-1]
        ed_url = f"https://openlibrary.org/books/{olid}.json"
        try:
            ed_resp = requests.get(ed_url, timeout=5)
            ed_resp.raise_for_status()
            ed_data = ed_resp.json()

            # Si la descripción no vino en la primera llamada, usar esta
            if not descripcion:
                desc_ed = ed_data.get('description')
                if isinstance(desc_ed, dict):
                    descripcion = desc_ed.get('value', '')
                elif isinstance(desc_ed, str):
                    descripcion = desc_ed

            # Extraer subjects
            subjects = ed_data.get('subjects', [])
        except requests.exceptions.RequestException as e:
            logger.warning(f"[OpenLibrary] Subjects fallback error: {e}")

    # Mapear categoría si encontramos coincidencia
    for s in subjects:
        s_lower = s.lower().strip()
        if s_lower in MAPEO_CATEGORIAS:
            categoria = MAPEO_CATEGORIAS[s_lower]
            break

    # Retornar estructura de respuesta
    return {
        "success": True,
        "isbn": isbn,
        "titulo": titulo,
        "autor": autores,
        "editorial": editorial,
        "fecha_publicacion": fecha,
        "descripcion": descripcion or '',
        "portada_url": portada_url or '',
        "categoria": categoria
    }
