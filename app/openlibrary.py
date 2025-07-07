# app/openlibrary.py

import requests

# Tabla de mapeo de categorías (puedes moverla a un archivo config.py si quieres reutilizarla)
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
    Consulta la API de OpenLibrary para un ISBN y devuelve un dict con metadatos mapeados.
    """

    base_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"

    try:
        resp = requests.get(base_url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"[OpenLibrary] Error en bibkeys: {e}")
        return None

    libro = data.get(f"ISBN:{isbn}")
    if not libro:
        return None

    # Campos principales
    titulo = libro.get('title', '')
    autores = ', '.join(a['name'] for a in libro.get('authors', [])) if libro.get('authors') else ''
    editorial = ', '.join(p['name'] for p in libro.get('publishers', [])) if libro.get('publishers') else ''
    fecha = libro.get('publish_date', '')

    # Descripción
    descripcion = ''
    desc_raw = libro.get('description')
    if isinstance(desc_raw, dict):
        descripcion = desc_raw.get('value', '')
    elif isinstance(desc_raw, str):
        descripcion = desc_raw

    # Portada con fallback
    portada_url = None
    if 'cover' in libro:
        portada_url = libro['cover'].get('large') or libro['cover'].get('medium')
    if not portada_url:
        # Prueba fallback covers.openlibrary.org
        fallback_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"
        try:
            head_resp = requests.head(fallback_url, timeout=5)
            if head_resp.ok:
                portada_url = fallback_url
        except:
            portada_url = None

    # Extraer subjects para categorizar
    categoria = "otros"
    edition_key = libro.get('key')
    subjects = []

    if edition_key:
        olid = edition_key.split('/')[-1]
        ed_url = f"https://openlibrary.org/books/{olid}.json"
        try:
            ed_resp = requests.get(ed_url, timeout=5)
            ed_resp.raise_for_status()
            ed_data = ed_resp.json()

            # Descripción alternativa si no vino
            if not descripcion:
                desc_ed = ed_data.get('description')
                if isinstance(desc_ed, dict):
                    descripcion = desc_ed.get('value', '')
                elif isinstance(desc_ed, str):
                    descripcion = desc_ed

            subjects = ed_data.get('subjects', [])
        except requests.exceptions.RequestException:
            pass

    for s in subjects:
        s_lower = s.lower().strip()
        if s_lower in MAPEO_CATEGORIAS:
            categoria = MAPEO_CATEGORIAS[s_lower]
            break

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
