# Librerías y extensiones principales
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, abort, jsonify, send_file, current_app,
    make_response, session
)
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message 
from functools import wraps
from datetime import datetime, timedelta, date
from werkzeug.utils import secure_filename
from sqlalchemy import extract, func, case
from time import time
import os
import requests

# Extensiones y modelos de la aplicación
from app.extensions import db, login_manager, mail
from app.models import Usuario, Libro, Prestamo, Reserva, Favorito, HistorialReporte
from app.openlibrary import obtener_datos_libro
from app.forms import (
    RegistroForm, LibroForm, EditarLibroForm, EditarReservaForm,
    NuevaReservaForm, PrestamoForm, ReservaLectorForm,
    AgregarLectorPresencialForm, EditarUsuarioForm
)
from app.utils import (
    verificar_token, generar_token, generar_reporte_con_plantilla,
    activar_siguiente_reserva
)

# Decorador para evitar cacheo de páginas
def nocache(view):
    @wraps(view)
    def no_cache(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return no_cache

# Definición del Blueprint principal
main = Blueprint('main', __name__)
login_manager.login_view = 'main.login'

# Decorador para restringir acceso por roles
def roles_requeridos(*roles):
    """
    Restringe acceso a usuarios autenticados con roles específicos.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.rol not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Acción antes de cada petición para actualizar reservas vencidas
@main.before_app_request
def actualizar_reservas_vencidas():
    """
    Marca reservas vencidas y libera los libros reservados.
    Solo aplica para administradores y bibliotecarios.
    """
    if not current_user.is_authenticated:
        return
    if current_user.rol not in ['administrador', 'bibliotecario']:
        return

    hoy = date.today()
    reservas_vencidas = Reserva.query.filter(
        Reserva.estado == 'activa',
        Reserva.fecha_expiracion < hoy
    ).all()

    for reserva in reservas_vencidas:
        reserva.estado = 'vencida'
        if reserva.libro:
            reserva.libro.cantidad_disponible += 1
            reserva.libro.actualizar_estado()
    if reservas_vencidas:
        db.session.commit()

# Acción antes de cada petición para marcar préstamos atrasados
@main.before_app_request
def marcar_prestamos_atrasados():
    """
    Cambia el estado de préstamos vencidos a 'atrasado'.
    """
    hoy = date.today()
    prestamos = Prestamo.query.filter(
        Prestamo.estado == 'activo',
        Prestamo.fecha_devolucion_esperada < hoy
    ).all()
    for prestamo in prestamos:
        prestamo.estado = 'atrasado'
    if prestamos:
        db.session.commit()

# Inyecta categorías de libros en el contexto de todas las plantillas
@main.context_processor
def inject_categorias():
    """
    Mapea categorías externas a internas y devuelve lista única.
    """
    mapeo_categorias = {
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
    categorias = sorted(set(mapeo_categorias.values()))
    return dict(categorias=categorias)

# Página principal del catálogo público
@main.route('/')
@nocache
def index():
    """
    Renderiza el catálogo público de libros.
    Si el usuario está autenticado, se pasa su rol.
    """
    page = request.args.get('page', 1, type=int)
    libros = Libro.query.filter(Libro.estado != 'eliminado').paginate(page=page, per_page=12)
    rol = current_user.rol if current_user.is_authenticated else None

    return render_template('index.html', libros=libros, rol=rol)

# Ruta para registro de nuevos usuarios
@main.route('/registro', methods=['GET', 'POST'])
def registro():
    """
    Registra un nuevo usuario lector.
    """
    form = RegistroForm()
    if form.validate_on_submit():
        # Extrae datos del formulario
        nombre = form.nombre.data
        apellido = form.apellido.data
        correo = form.correo.data
        documento = form.documento.data
        direccion = form.direccion.data
        telefono = form.telefono.data
        fecha_nacimiento = form.fecha_nacimiento.data
        password = form.password.data

        # Doble validación contra duplicados
        if Usuario.query.filter_by(correo=correo).first():
            flash('Correo no disponible.', 'danger')
            return redirect(url_for('main.registro'))
        if Usuario.query.filter_by(documento=documento).first():
            flash('Número de documento ya registrado.', 'danger')
            return redirect(url_for('main.registro'))

        # Crea usuario lector y genera llave de préstamo
        nuevo_usuario = Usuario(
            nombre=nombre,
            apellido=apellido,
            correo=correo,
            documento=documento,
            direccion=direccion,
            telefono=telefono,
            fecha_nacimiento=fecha_nacimiento,
            rol='lector',
            activo=True
        )
        nuevo_usuario.generar_llave_prestamo()
        nuevo_usuario.set_password(password)

        db.session.add(nuevo_usuario)
        db.session.commit()

        flash('Registro exitoso. Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('main.login'))

    return render_template('registro.html', form=form)

# Ruta de inicio de sesión
@main.route('/login', methods=['GET', 'POST'])
@nocache
def login():
    """
    Inicia sesión de usuario y redirige según el rol.
    """
    if current_user.is_authenticated:
        # Redirige a la ruta correspondiente según el rol
        if current_user.rol == 'administrador':
            return redirect(url_for('main.inicio'))
        elif current_user.rol == 'bibliotecario':
            return redirect(url_for('main.inicio'))
        elif current_user.rol == 'lector':
            return redirect(url_for('main.catalogo'))
        else:
            return redirect(url_for('main.index'))

    if request.method == 'POST':
        correo = request.form['correo']
        password = request.form['password']

        usuario = Usuario.query.filter_by(correo=correo, activo=True).first()

        if usuario and usuario.check_password(password):
            login_user(usuario)
            flash('Has iniciado sesión.', 'success')

            if usuario.rol == 'administrador':
                return redirect(url_for('main.inicio', status='in', rol=usuario.rol))
            elif usuario.rol == 'bibliotecario':
                return redirect(url_for('main.inicio', status='in', rol=usuario.rol))
            elif usuario.rol == 'lector':
                return redirect(url_for('main.catalogo', status='in', rol=usuario.rol))
            else:
                return redirect(url_for('main.index', status='in', rol=usuario.rol))

        flash('Correo o contraseña incorrectos', 'danger')
        return redirect(url_for('main.login'))

    return render_template('login.html')

# Cierra sesión de usuario
@main.route('/logout')
@login_required
def logout():
    """
    Cierra la sesión y limpia la sesión de usuario.
    """
    logout_user()
    session.clear()
    flash('Has cerrado sesión.', 'success')
    return redirect(url_for('main.index'))

# Lista de usuarios (solo admin o bibliotecario)
@main.route('/usuarios')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def lista_usuarios():
    """
    Muestra todos los usuarios registrados.
    """
    usuarios = Usuario.query.all()
    return render_template('usuarios.html', usuarios=usuarios)

# Activar/desactivar usuario
@main.route('/usuarios/<int:usuario_id>/toggle', methods=['POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def toggle_usuario(usuario_id):
    """
    Activa o desactiva un usuario.
    """
    usuario = Usuario.query.get_or_404(usuario_id)

    if usuario.nombre == 'admin':
        flash('No se puede desactivar al administrador principal.', 'error')
        return redirect(url_for('main.lista_usuarios'))

    if current_user.rol == 'bibliotecario' and usuario.rol == 'administrador':
        flash('No tienes permiso para modificar a un administrador.', 'error')
        return redirect(url_for('main.lista_usuarios'))

    usuario.activo = not usuario.activo
    db.session.commit()

    estado = 'activado' if usuario.activo else 'desactivado'
    flash(f"El usuario '{usuario.nombre}' ha sido {estado}.", 'success')
    return redirect(url_for('main.lista_usuarios'))

# Cambiar rol de usuario
@main.route('/usuarios/<int:usuario_id>/cambiar_rol', methods=['POST'])
@login_required
@roles_requeridos('administrador')
@nocache
def cambiar_rol(usuario_id):
    """
    Cambia el rol de un usuario existente.
    """
    usuario = Usuario.query.get_or_404(usuario_id)

    if usuario.nombre == 'admin':
        flash('No se puede cambiar el rol del administrador principal.', 'error')
        return redirect(url_for('main.lista_usuarios'))

    nuevo_rol = request.form.get('rol')

    if nuevo_rol not in ['lector', 'bibliotecario', 'administrador']:
        flash('Rol inválido.', 'error')
        return redirect(url_for('main.lista_usuarios'))

    usuario.rol = nuevo_rol
    db.session.commit()
    flash('Rol actualizado correctamente.', 'success')
    return redirect(url_for('main.lista_usuarios'))

# Vista principal del panel administrativo
@main.route('/admin/inicio', endpoint='inicio')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def admin_inicio():
    """
    Renderiza la plantilla base del panel de administración.
    """
    return render_template('admin.html', version=time())

# Vista parcial con datos resumidos para dashboard
@main.route('/admin/inicio-contenido')
@login_required
@roles_requeridos('administrador')
@nocache
def inicio_contenido():
    """
    Devuelve estadísticas generales para mostrar en el dashboard.
    """
    total_administradores = Usuario.query.filter_by(rol='administrador').count()
    total_lectores = Usuario.query.filter_by(rol='lector').count()
    total_libros = Libro.query.count()
    total_prestamos = Prestamo.query.count() if 'Prestamo' in globals() else 0
    total_reservas = Reserva.query.count() if 'Reserva' in globals() else 0

    return render_template(
        'inicio.html',
        total_administradores=total_administradores,
        total_lectores=total_lectores,
        total_libros=total_libros,
        total_prestamos=total_prestamos,
        total_reservas=total_reservas,
    )

# API para obtener metadatos de un libro por ISBN usando OpenLibrary
@main.route('/api/datos_libro/<isbn>')
def api_datos_libro(isbn):
    datos = obtener_datos_libro(isbn)
    if datos:
        return jsonify(datos)
    return jsonify({"success": False, "error": "Libro no encontrado"}), 404


# API para datos estadísticos del dashboard
@main.route('/api/dashboard_data')
@login_required
@roles_requeridos('administrador')
@nocache
def dashboard_data():
    """
    Devuelve totales para widgets de dashboard.
    """
    try:
        total_reportes = HistorialReporte.query.count()
    except Exception:
        total_reportes = 0

    data = {
        'total_administradores': Usuario.query.filter_by(rol='administrador').count(),
        'total_lectores': Usuario.query.filter_by(rol='lector').count(),
        'total_libros': Libro.query.count(),
        'total_prestamos': Prestamo.query.count() if 'Prestamo' in globals() else 0,
        'total_reservas': Reserva.query.count() if 'Reserva' in globals() else 0,
        'total_reportes': total_reportes,
    }
    return jsonify(data)

# Vista: mostrar lista de usuarios activos
@main.route('/admin/usuarios/mostrar')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def mostrar_usuarios():
    """
    Lista usuarios activos en el sistema.
    """
    usuarios = Usuario.query.filter(Usuario.activo != 0).all()
    return render_template('usuarios_mostrar.html', usuarios=usuarios)

# Formulario parcial para editar usuario
@main.route('/admin/usuarios/editar_formulario/<int:id>')
@login_required
@roles_requeridos('administrador')
@nocache
def editar_formulario_usuario(id):
    """
    Devuelve formulario de edición para un usuario.
    """
    usuario = Usuario.query.get_or_404(id)
    form = EditarUsuarioForm(
        nombre=usuario.nombre,
        correo=usuario.correo,
        direccion=usuario.direccion,
        rol=usuario.rol
    )
    return render_template(
        'partials/usuarios_editar.html',
        form=form,
        usuario=usuario
    )

# Guardar cambios de edición de usuario
@main.route('/admin/usuarios/editar/<int:id>', methods=['POST'])
@login_required
@roles_requeridos('administrador')
@nocache
def editar_usuario(id):
    """
    Actualiza datos del usuario tras validar formulario.
    """
    usuario = Usuario.query.get_or_404(id)
    form = EditarUsuarioForm()

    if form.validate_on_submit():
        usuario.nombre = form.nombre.data
        usuario.correo = form.correo.data
        usuario.direccion = form.direccion.data
        usuario.rol = form.rol.data

        db.session.commit()
        flash("Usuario actualizado correctamente.", "success")
        return redirect(url_for('main.mostrar_usuarios'))
    else:
        flash("Error al validar el formulario.", "danger")

    return redirect(url_for('main.mostrar_usuarios'))

# Ruta para eliminar un usuario
@main.route("/admin/usuarios/eliminar/<int:id>", methods=["POST"])
@login_required
@roles_requeridos('administrador')
@nocache
def eliminar_usuario(id):
    """
    Marca un usuario como inactivo. 
    Protege contra la eliminación del administrador principal.
    """
    usuario = Usuario.query.get_or_404(id)

    # Previene eliminar al superadmin
    if usuario.id == 1:
        return jsonify({"error": "No se puede eliminar el administrador principal"}), 403

    usuario.activo = False
    db.session.commit()
    return jsonify({"mensaje": "Usuario eliminado"})

# Ruta para agregar nuevo lector presencial (administrador o bibliotecario)
@main.route('/admin/usuarios/agregar', methods=['GET', 'POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def agregar_usuario():
    """
    Registra un lector presencial con clave por defecto y datos mínimos.
    """
    form = AgregarLectorPresencialForm()

    if form.validate_on_submit():
        nombre = form.nombre.data.strip()
        correo = form.correo.data.strip()
        documento = form.documento.data.strip()
        direccion = form.direccion.data.strip()

        nuevo_usuario = Usuario(
            nombre=nombre,
            apellido='-',
            correo=correo,
            documento=documento,
            direccion=direccion,
            telefono='-',
            fecha_nacimiento=date(2000, 1, 1),
            rol='lector*',
            activo=True
        )
        nuevo_usuario.generar_llave_prestamo()
        nuevo_usuario.set_password('000000')

        try:
            db.session.add(nuevo_usuario)
            db.session.commit()
            return jsonify({"success": True, "mensaje": "Lector presencial registrado correctamente."})
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "mensaje": "Error al registrar usuario.", "errores": str(e)})

    elif form.errors:
        print("ERRORES:", form.errors)
        return jsonify({"success": False, "mensaje": "Errores de validación.", "errores": form.errors})

    return render_template('registro_fragmento.html', form=form)

# Ruta para registrar un nuevo libro
@main.route('/admin/libros/nuevo', methods=['GET', 'POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def nuevo_libro():
    """
    Registra un nuevo libro.
    Puede autocompletar campos desde la API interna usando ISBN.
    Maneja portada local y fallback a portada por URL.
    """
    form = LibroForm()

    # Autocompleta datos si viene ISBN como parámetro GET
    isbn_param = request.args.get('isbn')
    if isbn_param and request.method == 'GET':
        try:
            api_response = requests.get(url_for('main.api_datos_libro', isbn=isbn_param, _external=True))
            api_response.raise_for_status()
            data = api_response.json()

            if data.get("success"):
                form.isbn.data = data.get('isbn', '')
                form.titulo.data = data.get('titulo', '')
                form.autor.data = data.get('autor', '')
                form.editorial.data = data.get('editorial', '')
                form.descripcion.data = data.get('descripcion', '')
                form.categoria.data = data.get('categoria', '')

                raw_date = data.get('fecha_publicacion', '')
                if raw_date:
                    try:
                        if len(raw_date) == 4 and raw_date.isdigit():
                            raw_date = f"{raw_date}-01-01"
                        elif len(raw_date) == 7:
                            raw_date = f"{raw_date}-01"
                        form.fecha_publicacion.data = datetime.strptime(raw_date, '%Y-%m-%d').date()
                    except ValueError:
                        form.fecha_publicacion.data = None
                else:
                    form.fecha_publicacion.data = None

                form.portada_url.data = data.get('portada_url')

            else:
                flash(f"No se pudieron obtener datos para ISBN {isbn_param}: {data.get('error', 'Error desconocido')}", 'warning')

        except requests.exceptions.RequestException as e:
            flash(f"Error de red al consultar la API interna: {e}", 'danger')
        except ValueError as e:
            flash(f"Error al procesar la respuesta de la API interna: {e}", 'danger')

    if form.validate_on_submit():
        isbn = form.isbn.data

        libro_existente = Libro.query.filter_by(isbn=isbn).first()
        if libro_existente:
            flash('Ya existe un libro con ese ISBN.', 'danger')
        else:
            cantidad_total = form.cantidad_total.data or 0

            portada_file = form.portada.data
            portada_url = form.portada_url.data or '/static/imagenes/portada_default.png'

            if portada_file:
                filename = secure_filename(portada_file.filename)
                carpeta_portadas = os.path.join(current_app.root_path, 'static', 'portadas')
                os.makedirs(carpeta_portadas, exist_ok=True)
                ruta_completa = os.path.join(carpeta_portadas, filename)
                portada_file.save(ruta_completa)
                portada_url = f'/static/portadas/{filename}'

            nuevo_libro = Libro(
                isbn=isbn,
                titulo=form.titulo.data,
                autor=form.autor.data,
                descripcion=form.descripcion.data,
                categoria=form.categoria.data,
                editorial=form.editorial.data,
                fecha_publicacion=form.fecha_publicacion.data,
                cantidad_total=cantidad_total,
                cantidad_disponible=cantidad_total,
                portada_url=portada_url
            )
            nuevo_libro.actualizar_estado()

            db.session.add(nuevo_libro)
            db.session.commit()

            flash('Libro creado exitosamente.', 'success')
            return redirect(url_for('main.mostrar_libros'))

    return render_template('nuevo_libro.html', form=form)

# Mostrar todos los libros no eliminados
@main.route('/admin/libros/mostrar')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def mostrar_libros():
    """
    Lista todos los libros activos o disponibles.
    """
    libros = Libro.query.filter(Libro.estado != 'eliminado').all()
    return render_template('libros_tabla.html', libros=libros)

# Ruta para eliminar libro (marca como eliminado)
@main.route('/admin/libros/eliminar/<int:libro_id>', methods=['POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def eliminar_libro(libro_id):
    """
    Marca un libro como eliminado si no tiene ejemplares prestados.
    """
    libro = Libro.query.get_or_404(libro_id)

    if libro.cantidad_disponible < libro.cantidad_total:
        flash('No se puede eliminar: hay ejemplares prestados.', 'danger')
        return redirect(url_for('main.admin_libros'))

    libro.marcar_como_eliminado()
    db.session.commit()
    flash('Libro marcado como eliminado.', 'success')
    return redirect(url_for('main.admin_libros'))

# Editar datos de un libro
@main.route('/admin/libros/editar/<int:libro_id>', methods=['GET', 'POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def editar_libro(libro_id):
    """
    Edita los datos de un libro.
    Permite actualizar portada y activa reservas si aumentan ejemplares.
    """
    libro = Libro.query.get_or_404(libro_id)
    form = EditarLibroForm(obj=libro)

    if form.validate_on_submit():
        nueva_cantidad_total = form.cantidad_total.data
        nueva_cantidad_disponible = form.cantidad_disponible.data

        if nueva_cantidad_disponible > nueva_cantidad_total:
            flash("La cantidad disponible no puede ser mayor que la cantidad total.", "danger")
            return redirect(url_for('main.editar_libro', libro_id=libro_id))

        cantidad_disponible_anterior = libro.cantidad_disponible

        libro.titulo = form.titulo.data
        libro.autor = form.autor.data
        libro.categoria = form.categoria.data
        libro.descripcion = form.descripcion.data
        libro.editorial = form.editorial.data
        libro.fecha_publicacion = form.fecha_publicacion.data
        libro.cantidad_total = nueva_cantidad_total
        libro.cantidad_disponible = nueva_cantidad_disponible
        libro.actualizar_estado()

        portada_file = form.portada.data
        if portada_file:
            filename = secure_filename(portada_file.filename)
            carpeta_portadas = os.path.join(current_app.root_path, 'static', 'portadas')
            os.makedirs(carpeta_portadas, exist_ok=True)
            ruta_completa = os.path.join(carpeta_portadas, filename)
            portada_file.save(ruta_completa)
            libro.portada_url = f'/static/portadas/{filename}'

        ejemplares_nuevos = nueva_cantidad_disponible - cantidad_disponible_anterior
        if ejemplares_nuevos > 0:
            while libro.cantidad_disponible > 0:
                activar_siguiente_reserva(libro)
                db.session.commit()

        db.session.commit()

        flash('Libro editado exitosamente y reservas activadas si aplica.', 'success')
        return redirect(url_for('main.mostrar_libros'))

    return render_template('editar_libro.html', form=form, libro=libro)
# Vista para escanear libros por ISBN o QR
@main.route('/admin/libros/scan', methods=['GET'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def escanear_libro():
    """
    Renderiza página para escanear código de barras o QR de un libro.
    """
    return render_template('escanear_libro.html')

# RUTAS DE RESERVAS
@main.route('/admin/reservas/nuevo', methods=['GET', 'POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def reservas_agregar():
    """
    Crea una nueva reserva desde el panel de administrador o bibliotecario.
    Si hay stock disponible, la activa y descuenta; si no, la deja en cola.
    """
    form = NuevaReservaForm()
    form.libro_id.choices = [(l.id, l.titulo) for l in Libro.query.all()]

    if request.method == 'GET':
        form.fecha_expiracion.data = date.today() + timedelta(days=7)

    if form.validate_on_submit():
        usuario = Usuario.query.filter_by(llave_prestamo=form.llave_prestamo.data).first()
        if not usuario:
            flash('Llave incorrecta.', 'danger')
            return redirect(url_for('main.reservas_tabla'))

        libro = Libro.query.get(form.libro_id.data)

        # Evita reservas duplicadas activas o pendientes
        reserva_existente = Reserva.query.filter_by(libro_id=libro.id, usuario_id=usuario.id)\
                                         .filter(Reserva.estado.in_(['pendiente', 'activa']))\
                                         .first()
        if reserva_existente:
            flash('El usuario ya tiene una reserva pendiente o activa para este libro.', 'warning')
            return redirect(url_for('main.reservas_tabla'))

        if libro.cantidad_disponible > 0:
            nueva_reserva = Reserva(
                usuario_id=usuario.id,
                libro_id=libro.id,
                fecha_expiracion=date.today() + timedelta(days=7),
                estado='activa'
            )
            libro.cantidad_disponible -= 1
            libro.actualizar_estado()
            msg = '✅ Reserva ACTIVADA: ejemplar bloqueado.'
        else:
            posicion = Reserva.query.filter_by(libro_id=libro.id, estado='pendiente').count() + 1
            nueva_reserva = Reserva(
                usuario_id=usuario.id,
                libro_id=libro.id,
                posicion=posicion,
                estado='pendiente'
            )
            msg = f'⏳ Reserva PENDIENTE registrada. Lugar en la cola: {posicion}.'

        db.session.add(nueva_reserva)
        db.session.commit()

        flash(msg, 'success')
        return redirect(url_for('main.reservas_tabla'))

    return render_template('reservas_agregar.html', form=form)

@main.route('/reservar/<int:libro_id>', methods=['GET', 'POST'])
@login_required
@roles_requeridos('lector')
@nocache
def reservar_libro_lector(libro_id):
    """
    Permite a un lector generar una reserva para un libro sin stock.
    Si hay stock, redirige a préstamo presencial.
    """
    libro = Libro.query.get_or_404(libro_id)
    form = ReservaLectorForm()

    if form.validate_on_submit():
        if current_user.llave_prestamo != form.llave_prestamo.data:
            flash('Llave incorrecta.', 'danger')
            return redirect(url_for('main.reservar_libro_lector', libro_id=libro.id))

        reserva_existente = Reserva.query.filter_by(libro_id=libro.id, usuario_id=current_user.id)\
                                         .filter(Reserva.estado.in_(['pendiente', 'activa']))\
                                         .first()
        if reserva_existente:
            flash('Ya tienes una reserva pendiente o activa para este libro.', 'warning')
            return redirect(url_for('main.catalogo'))

        if libro.cantidad_disponible > 0:
            flash('Hay ejemplares disponibles, solicita el préstamo directamente en biblioteca.', 'info')
            return redirect(url_for('main.catalogo'))

        posicion = Reserva.query.filter_by(libro_id=libro.id, estado='pendiente').count() + 1
        nueva_reserva = Reserva(
            usuario_id=current_user.id,
            libro_id=libro.id,
            posicion=posicion,
            estado='pendiente'
        )
        db.session.add(nueva_reserva)
        db.session.commit()

        # Envía correo de confirmación
        msg = Message(
            'Reserva registrada - Biblioteca',
            sender='noreply@biblioteca.com',
            recipients=[current_user.correo]
        )
        msg.body = f"""
Hola {current_user.nombre},

Tu reserva para "{libro.titulo}" ha sido registrada.
Lugar en la cola: {posicion}

Te notificaremos cuando esté disponible.

Gracias por usar Biblioteca Avocado 📚
"""
        mail.send(msg)

        flash(f'⏳ Reserva registrada. Estás en el puesto {posicion}.', 'success')
        return redirect(url_for('main.catalogo'))

    return render_template('reservar_libro.html', form=form, libro=libro)


@main.route('/reservas/<int:reserva_id>/cancelar', methods=['POST'])
@login_required
@roles_requeridos('lector')
@nocache
def cancelar_reserva_lector(reserva_id):
    """
    Permite a un lector cancelar su propia reserva.
    Reorganiza la cola y notifica por correo.
    """
    reserva = Reserva.query.get_or_404(reserva_id)

    if reserva.usuario_id != current_user.id:
        flash('No tienes permiso para cancelar esta reserva.', 'danger')
        return redirect(url_for('main.mis_libros'))

    libro = reserva.libro

    if reserva.estado == 'activa':
        libro.cantidad_disponible += 1
        libro.actualizar_estado()
        activar_siguiente_reserva(libro)

    reserva.estado = 'cancelada'
    reserva.posicion = None

    if reserva.estado == 'pendiente':
        reservas_pendientes = Reserva.query.filter_by(
            libro_id=libro.id,
            estado='pendiente'
        ).order_by(Reserva.fecha_reserva.asc()).all()

        for idx, r in enumerate(reservas_pendientes, start=1):
            r.posicion = idx

    db.session.commit()

    msg = Message(
        'Reserva Cancelada',
        sender='noreply@biblioteca.com',
        recipients=[current_user.correo]
    )
    msg.body = f"""
Hola {current_user.nombre},

Tu reserva para "{libro.titulo}" ha sido cancelada correctamente.
"""
    mail.send(msg)

    flash(f'Reserva del libro "{libro.titulo}" cancelada.', 'success')
    return redirect(url_for('main.mis_libros'))

@main.route('/admin/reservas/editar/<int:reserva_id>', methods=['GET', 'POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def editar_reserva(reserva_id):
    """
    Permite al admin/bibliotecario editar la reserva:
    cambiar libro o fecha de expiración.
    """
    reserva = Reserva.query.get_or_404(reserva_id)
    form = EditarReservaForm(obj=reserva)

    form.libro_id.choices = [(l.id, l.titulo) for l in Libro.query.order_by(Libro.titulo).all()]

    if request.method == 'GET':
        form.libro_id.data = reserva.libro_id
        form.fecha_expiracion.data = reserva.fecha_expiracion

    if form.validate_on_submit():
        if reserva.libro_id != form.libro_id.data:
            libro_anterior = Libro.query.get(reserva.libro_id)
            libro_nuevo = Libro.query.get(form.libro_id.data)

            if reserva.estado == 'activa':
                libro_anterior.cantidad_disponible += 1
                libro_nuevo.cantidad_disponible -= 1
                libro_anterior.actualizar_estado()
                libro_nuevo.actualizar_estado()

            reserva.libro_id = form.libro_id.data

        reserva.fecha_expiracion = form.fecha_expiracion.data

        db.session.commit()
        flash('✅ Reserva actualizada correctamente.', 'success')
        return redirect(url_for('main.reservas_tabla'))

    return render_template('editar_reserva.html', form=form, reserva=reserva)

@main.route('/admin/reservas/eliminar/<int:reserva_id>', methods=['POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def eliminar_reserva(reserva_id):
    """
    Marca una reserva como eliminada y reorganiza la cola.
    Si estaba activa, libera ejemplar.
    """
    reserva = Reserva.query.get_or_404(reserva_id)

    libro = reserva.libro

    if reserva.estado == 'activa':
        libro.cantidad_disponible += 1
        libro.actualizar_estado()
        activar_siguiente_reserva(libro)

    reserva.estado = 'eliminada'
    reserva.posicion = None

    if reserva.estado == 'pendiente':
        reservas_pendientes = Reserva.query.filter_by(
            libro_id=libro.id,
            estado='pendiente'
        ).order_by(Reserva.fecha_reserva.asc()).all()

        for idx, r in enumerate(reservas_pendientes, start=1):
            r.posicion = idx

    db.session.commit()
    flash(f'🗑️ Reserva #{reserva.id} eliminada correctamente.', 'success')
    return redirect(url_for('main.reservas_tabla'))

# RUTAS DE PRÉSTAMOS
@main.route('/admin/prestamos/nuevo', methods=['GET', 'POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario', 'lector')
@nocache
def nuevo_prestamo():
    """
    Registra un nuevo préstamo.
    Descuenta stock, crea registro y envía confirmación por correo.
    """
    form = PrestamoForm()
    form.libro_id.choices = [(l.id, l.titulo) for l in Libro.query.filter(Libro.cantidad_disponible > 0).all()]

    libro_id = request.args.get('libro_id', type=int)
    if libro_id and not form.libro_id.data:
        form.libro_id.data = libro_id

    if form.validate_on_submit():
        usuario = Usuario.query.filter_by(llave_prestamo=form.llave_prestamo.data).first()
        if not usuario:
            flash('Llave incorrecta.', 'danger')
            return redirect(url_for('main.nuevo_prestamo'))

        libro = Libro.query.get(form.libro_id.data)
        if libro and libro.cantidad_disponible > 0:
            nuevo_prestamo = Prestamo(
                usuario_id=usuario.id,
                libro_id=libro.id,
                fecha_prestamo=datetime.now().date(),
                fecha_devolucion_esperada=(datetime.now() + timedelta(days=7)).date(),
                estado='activo'
            )
            libro.cantidad_disponible -= 1
            db.session.add(nuevo_prestamo)
            db.session.commit()

            msg = Message(
                'Préstamo Registrado',
                sender='noreply@biblioteca.com',
                recipients=[usuario.correo]
            )
            msg.body = f"""
Hola {usuario.nombre},

Se ha registrado un préstamo para el libro "{libro.titulo}".

📅 Fecha de préstamo: {nuevo_prestamo.fecha_prestamo}
⏰ Fecha de devolución esperada: {nuevo_prestamo.fecha_devolucion_esperada}

Por favor, devuelve el libro a tiempo para evitar recargos.

Saludos,
El equipo de Biblioteca sbs
"""
            mail.send(msg)

            flash('Préstamo registrado correctamente.', 'success')
            return redirect(url_for('main.mostrar_prestamos'))
        else:
            flash('El libro no está disponible.', 'danger')

    return render_template('prestamos_agregar.html', form=form)

@main.route('/admin/prestamos/devolver/<int:prestamo_id>', methods=['POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def devolver_prestamo(prestamo_id):
    """
    Marca un préstamo como devuelto, devuelve ejemplar y activa siguiente reserva.
    """
    prestamo = Prestamo.query.get_or_404(prestamo_id)

    if prestamo.fecha_devolucion:
        flash('Este préstamo ya fue devuelto.', 'warning')
    else:
        prestamo.fecha_devolucion = datetime.now().date()
        prestamo.estado = 'devuelto'

        libro = prestamo.libro
        if libro:
            libro.cantidad_disponible += 1
            libro.actualizar_estado()
            activar_siguiente_reserva(libro)

        db.session.commit()
        flash('📚 Préstamo marcado como devuelto. Stock actualizado.', 'success')

    return redirect(url_for('main.mostrar_prestamos'))

@main.route('/admin/prestamos/mostrar')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def mostrar_prestamos():
    """
    Lista todos los préstamos registrados.
    """
    prestamos = Prestamo.query.all()
    return render_template('prestamos_tabla.html', prestamos=prestamos)

# RUTA: Prestar reserva
@main.route('/admin/reservas/prestar/<int:reserva_id>', methods=['POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def prestar_reserva(reserva_id):
    """
    Convierte una reserva activa en un préstamo.
    - Verifica duplicidad de préstamo.
    - Crea el préstamo.
    - Actualiza estado de reserva.
    - Actualiza stock del libro.
    - Activa la siguiente reserva si aplica.
    """
    reserva = Reserva.query.get_or_404(reserva_id)

    if reserva.estado != 'activa':
        flash('⚠️ Solo se pueden prestar reservas activas.', 'warning')
        return redirect(url_for('main.reservas_tabla'))

    libro = Libro.query.get(reserva.libro_id)
    if not libro:
        flash('❌ Libro no encontrado.', 'danger')
        return redirect(url_for('main.reservas_tabla'))

    # Evitar préstamo duplicado para el mismo usuario y libro
    prestamo_existente = Prestamo.query.filter_by(
        usuario_id=reserva.usuario_id,
        libro_id=reserva.libro_id,
        estado='activo'
    ).first()
    if prestamo_existente:
        flash('⚠️ Este usuario ya tiene un préstamo activo de este libro.', 'warning')
        return redirect(url_for('main.reservas_tabla'))

    # Crear préstamo
    nuevo_prestamo = Prestamo(
        usuario_id=reserva.usuario_id,
        libro_id=reserva.libro_id,
        fecha_prestamo=datetime.utcnow().date(),
        fecha_devolucion_esperada=(datetime.utcnow() + timedelta(days=7)).date(),
        estado='activo'
    )
    db.session.add(nuevo_prestamo)

    # Actualiza estado del libro (stock)
    libro.actualizar_estado()

    # Marca reserva como confirmada
    reserva.confirmar()

    # Activa siguiente reserva pendiente si corresponde
    activar_siguiente_reserva(libro)

    db.session.commit()

    flash(f'📚 Préstamo creado desde reserva #{reserva.id}.', 'success')
    return redirect(url_for('main.reservas_tabla'))

#  Vista general de reservas
@main.route('/admin/reservas/mostrar')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def reservas_tabla():
    """
    Muestra todas las reservas (excepto eliminadas) en tabla de administración.
    """
    reservas = Reserva.query.filter(Reserva.estado != 'eliminada').all()
    return render_template('reservas_tabla.html', reservas=reservas)

# Reportes
@main.route('/admin/reportes/historial')
@login_required
@roles_requeridos('administrador')
@nocache
def historial_reportes():
    """
    Lista de todos los reportes generados y guardados en historial.
    """
    historial = HistorialReporte.query.order_by(
        HistorialReporte.fecha_generacion.desc()
    ).all()
    return render_template('reportes/historial_reportes.html', historial=historial)

@main.route('/admin/reportes/atrasados')
@login_required
@roles_requeridos('administrador')
@nocache
def reporte_libros_atrasados():
    """
    Fragmento con todos los préstamos vencidos y aún no devueltos.
    """
    atrasados = Prestamo.query.filter(
        Prestamo.fecha_devolucion_esperada < date.today(),
        Prestamo.fecha_devolucion.is_(None)
    ).all()
    return render_template('reportes/fragmento_atrasados.html', atrasados=atrasados)

@main.route('/admin/reportes/descargar_reporte_atrasados')
@login_required
@roles_requeridos('administrador')
@nocache
def descargar_reporte_atrasados():
    """
    Genera y descarga un PDF con la lista de libros atrasados.
    Guarda historial de descarga.
    """
    atrasados = Prestamo.query.filter(
        Prestamo.fecha_devolucion_esperada < date.today(),
        Prestamo.fecha_devolucion.is_(None)
    ).all()

    datos = []
    for p in atrasados:
        datos.append([
            p.libro.titulo,
            p.usuario.correo,
            p.fecha_devolucion_esperada.strftime('%Y-%m-%d')
        ])

    columnas = ["#", "Libro", "Correo", "Fecha Vencida"]

    pdf = generar_reporte_con_plantilla(datos, columnas, "Reporte de Libros Atrasados")

    nombre_archivo = f"reporte_atrasados_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"
    ruta_carpeta = os.path.join(current_app.root_path, 'static', 'archivos')
    os.makedirs(ruta_carpeta, exist_ok=True)
    ruta_archivo = os.path.join(ruta_carpeta, nombre_archivo)

    with open(ruta_archivo, 'wb') as f:
        f.write(pdf)

    historial = HistorialReporte(
        nombre_reporte="Libros Atrasados",
        ruta_archivo=f'archivos/{nombre_archivo}',
        admin_id=current_user.id
    )
    db.session.add(historial)
    db.session.commit()

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename={nombre_archivo}'
    return response

@main.route('/admin/reportes/prestados')
@login_required
@roles_requeridos('administrador')
@nocache
def reporte_libros_prestamos():
    """
    Fragmento de tabla de todos los préstamos (devueltos y activos).
    """
    prestamos = Prestamo.query.all()
    return render_template('reportes/fragmento_prestados.html', prestamos=prestamos)

@main.route('/admin/reportes/descargar_reporte_prestados')
@login_required
@roles_requeridos('administrador')
@nocache
def descargar_reporte_prestados():
    """
    Genera y descarga PDF de préstamos con historial de devoluciones.
    Guarda historial.
    """
    prestamos = Prestamo.query.all()

    datos = []
    for p in prestamos:
        fecha_dev = p.fecha_devolucion.strftime('%Y-%m-%d') if p.fecha_devolucion else "No devuelto"
        datos.append([
            p.libro.titulo,
            p.usuario.correo,
            p.fecha_prestamo.strftime('%Y-%m-%d'),
            fecha_dev
        ])

    columnas = ["#", "Libro", "Correo", "Fecha Préstamo", "Fecha Devolución"]

    pdf = generar_reporte_con_plantilla(datos, columnas, "Reporte de Libros Prestados")

    nombre_archivo = f"reporte_prestados_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"
    ruta_carpeta = os.path.join(current_app.root_path, 'static', 'archivos')
    os.makedirs(ruta_carpeta, exist_ok=True)
    ruta_archivo = os.path.join(ruta_carpeta, nombre_archivo)

    with open(ruta_archivo, 'wb') as f:
        f.write(pdf)

    historial = HistorialReporte(
        nombre_reporte="Libros Prestados",
        ruta_archivo=f'archivos/{nombre_archivo}',
        admin_id=current_user.id
    )
    db.session.add(historial)
    db.session.commit()

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename={nombre_archivo}'
    return response

@main.route('/admin/reportes/populares')
@login_required
@roles_requeridos('administrador')
@nocache
def reporte_libros_populares():
    """
    Muestra top 5 libros más prestados y reservados.
    Combina préstamos y reservas pendientes.
    """
    prestamos_subq = db.session.query(
        Prestamo.libro_id,
        func.count(Prestamo.id).label('prestamos')
    ).group_by(Prestamo.libro_id).subquery()

    reservas_subq = db.session.query(
        Reserva.libro_id,
        func.count(Reserva.id).label('reservas')
    ).filter(Reserva.estado == 'pendiente').group_by(Reserva.libro_id).subquery()

    populares = db.session.query(
        Libro.id,
        Libro.titulo,
        Libro.autor,
        func.coalesce(prestamos_subq.c.prestamos, 0).label('prestamos'),
        func.coalesce(reservas_subq.c.reservas, 0).label('reservas'),
        (func.coalesce(prestamos_subq.c.prestamos, 0) + func.coalesce(reservas_subq.c.reservas, 0)).label('total')
    ).outerjoin(prestamos_subq, prestamos_subq.c.libro_id == Libro.id) \
     .outerjoin(reservas_subq, reservas_subq.c.libro_id == Libro.id) \
     .order_by(db.desc('total')) \
     .limit(5).all()

    return render_template('reportes/fragmento_populares.html', populares=populares)

@main.route('/admin/reportes/descargar_reporte_populares')
@login_required
@roles_requeridos('administrador')
@nocache
def descargar_reporte_populares():
    """
    Genera y descarga PDF con ranking top 5 libros más populares.
    Guarda historial.
    """
    prestamos_subq = db.session.query(
        Prestamo.libro_id,
        func.count(Prestamo.id).label('prestamos')
    ).group_by(Prestamo.libro_id).subquery()

    reservas_subq = db.session.query(
        Reserva.libro_id,
        func.count(Reserva.id).label('reservas')
    ).filter(Reserva.estado == 'pendiente').group_by(Reserva.libro_id).subquery()

    populares = db.session.query(
        Libro.titulo,
        Libro.autor,
        func.coalesce(prestamos_subq.c.prestamos, 0).label('prestamos'),
        func.coalesce(reservas_subq.c.reservas, 0).label('reservas'),
        (func.coalesce(prestamos_subq.c.prestamos, 0) + func.coalesce(reservas_subq.c.reservas, 0)).label('total')
    ).outerjoin(prestamos_subq, prestamos_subq.c.libro_id == Libro.id) \
     .outerjoin(reservas_subq, reservas_subq.c.libro_id == Libro.id) \
     .order_by(db.desc('total')) \
     .limit(5).all()

    datos = []
    for p in populares:
        datos.append([
            p.titulo,
            p.autor,
            p.prestamos,
            p.reservas,
            p.total
        ])

    columnas = ["#", "Libro", "Autor", "Préstamos", "Reservas Pendientes", "Total"]

    pdf = generar_reporte_con_plantilla(datos, columnas, "Reporte de Libros Populares")

    nombre_archivo = f"reporte_populares_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"
    ruta_carpeta = os.path.join(current_app.root_path, 'static', 'archivos')
    os.makedirs(ruta_carpeta, exist_ok=True)
    ruta_archivo = os.path.join(ruta_carpeta, nombre_archivo)

    with open(ruta_archivo, 'wb') as f:
        f.write(pdf)

    historial = HistorialReporte(
        nombre_reporte="Libros Populares",
        ruta_archivo=f'archivos/{nombre_archivo}',
        admin_id=current_user.id
    )
    db.session.add(historial)
    db.session.commit()

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename={nombre_archivo}'
    return response

# Extensiones permitidas para subir imágenes de perfil
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Función para validar la extensión del archivo subido
def extension_permitida(nombre_archivo):
    return '.' in nombre_archivo and \
        nombre_archivo.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# RUTA: Configuración admin
@main.route('/admin/configuracion', methods=['GET', 'POST'])
@login_required
@nocache
def configuracion():
    # Obtiene el usuario actual desde la sesión
    usuario = Usuario.query.get(current_user.id)

    if request.method == 'POST':
        # Obtiene datos del formulario
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        correo = request.form.get('correo')
        archivo = request.files.get('foto_perfil')

        # Actualiza campos si se enviaron
        if nombre:
            usuario.nombre = nombre
        if apellido:
            usuario.apellido = apellido
        if correo:
            usuario.correo = correo

        # Si se subió una foto de perfil
        if archivo and archivo.filename != '':
            filename = secure_filename(archivo.filename)
            extension = os.path.splitext(filename)[1]
            nuevo_nombre = f"user_{usuario.id}{extension}"
            ruta_guardado = os.path.join(current_app.root_path, 'static', 'fotos_perfil', nuevo_nombre)
            archivo.save(ruta_guardado)
            usuario.foto = f"fotos_perfil/{nuevo_nombre}"

            flash("Foto de perfil actualizada con éxito", "success")
        else:
            flash("Perfil actualizado con éxito", "success")

        # Guarda cambios en la base de datos
        db.session.commit()
        return redirect(url_for('main.configuracion'))

    return render_template('configuracion.html', usuario=usuario)

#  RUTA: Catálogo de libros
@main.route('/catalogo')
@login_required
@roles_requeridos('lector', 'administrador', 'bibliotecario')
@nocache
def catalogo():
    # Página actual, por defecto 1
    page = request.args.get('page', 1, type=int)
    per_page = 12  # Cantidad de libros por página

    # Consulta libros que no estén eliminados
    libros = Libro.query.filter(Libro.estado != 'eliminado').paginate(page=page, per_page=per_page)

    # IDs de libros favoritos del usuario lector
    favoritos_ids = []
    if current_user.is_authenticated and current_user.rol == 'lector':
        favoritos_ids = [f.libro_id for f in current_user.favoritos]

    return render_template('catalogo.html', libros=libros, favoritos_ids=favoritos_ids)

# RUTA: Perfil del usuario lector
@main.route('/perfil', methods=['GET', 'POST'])
@login_required
@nocache
def perfil():
    if request.method == 'POST':
        usuario = Usuario.query.get(current_user.id)
        usuario.nombre = request.form['nombre']
        usuario.correo = request.form['correo']

        # Si se subió una nueva foto de perfil
        if 'foto_perfil' in request.files:
            file = request.files['foto_perfil']
            if file.filename != '':
                filename = secure_filename(file.filename)
                ruta_carpeta = os.path.join('static', 'imagenes', 'perfil')
                os.makedirs(ruta_carpeta, exist_ok=True)  # Crea carpeta si no existe
                filepath = os.path.join(ruta_carpeta, filename)
                file.save(filepath)
                usuario.foto = f'imagenes/perfil/{filename}'

        db.session.commit()
        flash('Perfil actualizado correctamente.', 'success')
        return redirect(url_for('main.perfil'))

    return render_template('perfil.html', usuario=current_user)

#  RUTA: Mostrar foto de perfil
@main.route('/foto_perfil')
@login_required
@nocache
def foto_perfil():
    # Si el usuario tiene foto y existe el archivo la muestra
    if current_user.foto:
        ruta = os.path.join('static', current_user.foto.replace('/', os.sep))
        if os.path.exists(ruta):
            return send_file(ruta, mimetype='image/jpeg')

    # Si no tiene foto, muestra una imagen por defecto
    return redirect(url_for('static', filename='imagenes/perfil/default.png'))

# RUTA: Detalle de un libro
@main.route('/libro/<int:libro_id>')
@login_required
@nocache
def detalle_libro(libro_id):
    libro = Libro.query.get_or_404(libro_id)
    es_favorito = False

    # Si es lector, verifica si ya es favorito
    if current_user.is_authenticated and current_user.rol == 'lector':
        es_favorito = Favorito.query.filter_by(
            usuario_id=current_user.id,
            libro_id=libro.id
        ).first() is not None

    return render_template('detalle_libro.html', libro=libro, es_favorito=es_favorito)

# RUTA: Añadir o quitar favorito
@main.route('/favoritos/toggle/<int:libro_id>', methods=['POST'])
@login_required
@roles_requeridos('lector')
@nocache
def toggle_favorito(libro_id):
    libro = Libro.query.get_or_404(libro_id)
    favorito = Favorito.query.filter_by(usuario_id=current_user.id, libro_id=libro.id).first()

    if favorito:
        # Si ya es favorito, lo elimina
        db.session.delete(favorito)
        flash('Libro eliminado de tus favoritos.', 'info')
    else:
        # Si no es favorito, lo añade
        nuevo_favorito = Favorito(usuario_id=current_user.id, libro_id=libro.id)
        db.session.add(nuevo_favorito)
        flash('Libro añadido a tus favoritos.', 'success')

    db.session.commit()
    return redirect(url_for('main.detalle_libro', libro_id=libro.id))

# RUTA: Mis libros (lector)
@main.route('/mis_libros')
@login_required
@roles_requeridos('lector')
@nocache
def mis_libros():
    # Obtiene préstamos, reservas y favoritos del lector
    mis_prestamos = Prestamo.query.filter_by(usuario_id=current_user.id).all()
    mis_reservas = Reserva.query.filter_by(usuario_id=current_user.id).all()
    mis_favoritos = Favorito.query.filter_by(usuario_id=current_user.id).all()

    return render_template(
        'mis_libros.html',
        prestamos=mis_prestamos,
        reservas=mis_reservas,
        favoritos=mis_favoritos
    )

# RUTA: Recuperar contraseña
@main.route('/recuperar', methods=['GET', 'POST'])
def recuperar():
    if request.method == 'POST':
        correo = request.form['correo']
        usuario = Usuario.query.filter_by(correo=correo).first()

        if usuario:
            # Genera token y envía correo con enlace
            token = generar_token(usuario.correo)
            link = url_for('main.restablecer', token=token, _external=True)
            msg = Message(
                'Recuperar contraseña',
                sender='noreply@biblioteca.com',
                recipients=[usuario.correo]
            )
            msg.body = (
                f'Estimado usuario,\n\n'
                f'Hemos recibido una solicitud para restablecer la contraseña de su cuenta.\n'
                f'Enlace: {link}\n\n'
                f'Si no solicitó el cambio, ignore este mensaje.\n'
                f'Atentamente,\nBiblioteca.'
            )
            mail.send(msg)
            flash('Te enviamos un correo para recuperar tu contraseña.', 'info')
        else:
            flash('Correo no encontrado.', 'danger')

    return render_template('recuperar.html')

#  RUTA: Restablecer contraseña
@main.route('/restablecer/<token>', methods=['GET', 'POST'])
def restablecer(token):
    email = verificar_token(token)
    if not email:
        flash('El enlace es inválido o ha expirado.', 'danger')
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        nueva_pass = request.form['password']
        usuario = Usuario.query.filter_by(correo=email).first()
        if usuario:
            usuario.set_password(nueva_pass)
            db.session.commit()
            flash('Contraseña actualizada correctamente.', 'success')
            return redirect(url_for('main.login'))

    return render_template('restablecer.html')

#  RUTA: Mostrar todos usuarios (modal admin)
@main.route('/admin/usuarios/mostrar')
@login_required
@roles_requeridos('administrador')
@nocache
def usuarios_modal():
    usuarios = Usuario.query.all()
    return render_template('usuarios_mostrar.html', usuarios=usuarios)

#  RUTA: API préstamos por mes
@main.route('/api/prestamos_mes')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def prestamos_por_mes():
    resultados = db.session.query(
        extract('month', Prestamo.fecha_prestamo).label('mes'),
        func.count().label('total')
    ).group_by('mes').order_by('mes').all()

    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
             "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    return jsonify([
        {'mes': meses[int(r.mes) - 1], 'total': r.total}
        for r in resultados
    ])

#  RUTA: API libros más prestados
@main.route('/api/libros_populares')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def libros_populares():
    resultados = db.session.query(
        Libro.titulo,
        func.count(Prestamo.id).label('total')
    ).join(Prestamo).group_by(Libro.id).order_by(func.count(Prestamo.id).desc()).limit(5).all()

    return jsonify([{'titulo': r.titulo, 'total': r.total} for r in resultados])

#  RUTA: API libros atrasados
@main.route('/api/libros_atrasados')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def libros_atrasados():
    resultados = db.session.query(
        Libro.titulo,
        func.count(Prestamo.id).label('total')
    ).join(Prestamo).filter(Prestamo.estado == 'atrasado') \
     .group_by(Libro.id).order_by(func.count(Prestamo.id).desc()).limit(5).all()

    return jsonify([{'titulo': r.titulo, 'total': r.total} for r in resultados])

#  RUTA: Buscar usuario por llave (AJAX)
@main.route('/ajax/buscar_usuario_por_llave')
@login_required
@nocache
def ajax_buscar_usuario_por_llave():
    llave = request.args.get('llave_prestamo')
    usuario = Usuario.query.filter_by(llave_prestamo=llave).first()

    if usuario:
        return jsonify({
            'success': True,
            'nombre': usuario.nombre,
            'correo': usuario.correo,
            'usuario_id': usuario.id
        })
    else:
        return jsonify({'success': False})

#  RUTAS: Tablas simplificadas para contadores
@main.route('/admin/usuarios/solo_mostrar')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def mostrar_usuarios_sencillo():
    usuarios = Usuario.query.all()
    return render_template('usuarios_mostrar_sencillo.html', usuarios=usuarios)

@main.route('/admin/libros/solo_mostrar')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def mostrar_libros_sencillo():
    libros = Libro.query.filter(Libro.estado != 'eliminado').all()
    return render_template('libros_tabla_sencillo.html', libros=libros)

@main.route('/admin/prestamos/solo_mostrar')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def mostrar_prestamos_sencillo():
    prestamos = Prestamo.query.all()
    return render_template('prestamos_tabla_sencillo.html', prestamos=prestamos)

@main.route('/admin/reservas/solo_mostrar')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def mostrar_reservas_sencillo():
    reservas = Reserva.query.all()
    return render_template('reservas_tabla_sencillo.html', reservas=reservas)

#  RUTA: Buscador global
@main.route('/buscar', methods=['GET'])
def buscar():
    consulta = request.args.get('q', '').strip()
    resultados = []

    if consulta:
        resultados = Libro.query.filter(
            Libro.titulo.ilike(f'%{consulta}%')
        ).all()

    return render_template('resultado_busqueda.html', resultados=resultados, consulta=consulta)

#  RUTA: Filtrar por categoría
@main.route('/categoria/<categoria>')
def categoria(categoria):
    libros = Libro.query.filter_by(categoria=categoria).all()
    return render_template('categoria.html', libros=libros, categoria=categoria)

