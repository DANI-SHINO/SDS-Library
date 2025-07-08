# Librerías y extensiones principales
import os
import logging
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
logging.basicConfig(level=logging.INFO)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  

def extension_permitida(nombre_archivo):
    return '.' in nombre_archivo and \
           nombre_archivo.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
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
        try:
            db.session.commit()
            logging.info(f"{len(reservas_vencidas)} reservas vencidas actualizadas.")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error actualizando reservas vencidas: {e}")
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
        try:
            db.session.commit()
            logging.info(f"{len(prestamos)} préstamos marcados como atrasados.")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error marcando préstamos atrasados: {e}")
# Inyecta categorías de libros en el contexto de todas las plantillas
@main.context_processor
def inject_categorias():
    """
    Mapea categorías externas a internas y devuelve lista única.
    """
    mapeo_categorias = {
        # ...
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

        try:
            db.session.add(nuevo_usuario)
            db.session.commit()
            flash('Registro exitoso. Ya puedes iniciar sesión.', 'success')
            logging.info(f"Nuevo usuario registrado: {correo}")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error registrando usuario {correo}: {e}")
            flash('Ocurrió un error al registrar. Inténtalo de nuevo.', 'danger')

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
            logging.info(f"Usuario {correo} inició sesión.")
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
        logging.warning(f"Intento de login fallido para correo: {correo}")
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
    logging.info(f"Usuario cerró sesión.")
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
    try:
        db.session.commit()
        estado = 'activado' if usuario.activo else 'desactivado'
        flash(f"El usuario '{usuario.nombre}' ha sido {estado}.", 'success')
        logging.info(f"Usuario '{usuario.nombre}' {estado} por {current_user.nombre}.")
    except Exception as e:
        db.session.rollback()
        flash('Ocurrió un error al actualizar el usuario.', 'danger')
        logging.error(f"Error al cambiar estado de usuario {usuario.id}: {e}")

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

    try:
        db.session.commit()
        flash('Rol actualizado correctamente.', 'success')
        logging.info(f"Rol de usuario {usuario.id} cambiado a {nuevo_rol}.")
    except Exception as e:
        db.session.rollback()
        flash('Error al actualizar el rol.', 'danger')
        logging.error(f"Error cambiando rol de usuario {usuario.id}: {e}")

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
    try:
        total_administradores = Usuario.query.filter_by(rol='administrador').count()
        total_lectores = Usuario.query.filter_by(rol='lector').count()
        total_libros = Libro.query.count()
        total_prestamos = Prestamo.query.count() if 'Prestamo' in globals() else 0
        total_reservas = Reserva.query.count() if 'Reserva' in globals() else 0

        logging.info("Estadísticas del dashboard generadas.")
    except Exception as e:
        logging.error(f"Error obteniendo estadísticas del dashboard: {e}")
        total_administradores = total_lectores = total_libros = total_prestamos = total_reservas = 0

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
        logging.info(f"Datos de ISBN {isbn} obtenidos.")
        return jsonify(datos)
    logging.warning(f"ISBN {isbn} no encontrado.")
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
    except Exception as e:
        logging.error(f"Error obteniendo reportes del dashboard: {e}")
        total_reportes = 0

    data = {
        'total_administradores': Usuario.query.filter_by(rol='administrador').count(),
        'total_lectores': Usuario.query.filter_by(rol='lector').count(),
        'total_libros': Libro.query.count(),
        'total_prestamos': Prestamo.query.count() if 'Prestamo' in globals() else 0,
        'total_reservas': Reserva.query.count() if 'Reserva' in globals() else 0,
        'total_reportes': total_reportes,
    }

    logging.info("Datos del dashboard API generados.")
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
    logging.info(f"{len(usuarios)} usuarios activos mostrados.")
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
    logging.info(f"Formulario de edición para usuario {id} generado.")
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

        try:
            db.session.commit()
            flash("Usuario actualizado correctamente.", "success")
            logging.info(f"Usuario {id} actualizado correctamente.")
        except Exception as e:
            db.session.rollback()
            flash("Error al actualizar usuario.", "danger")
            logging.error(f"Error actualizando usuario {id}: {e}")

        return redirect(url_for('main.mostrar_usuarios'))
    else:
        flash("Error al validar el formulario.", "danger")
        logging.warning(f"Errores de validación en formulario de usuario {id}: {form.errors}")

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

    if usuario.id == 1:
        logging.warning("Intento de eliminar al superadmin bloqueado.")
        return jsonify({"error": "No se puede eliminar el administrador principal"}), 403

    usuario.activo = False
    try:
        db.session.commit()
        logging.info(f"Usuario {id} marcado como inactivo.")
        return jsonify({"mensaje": "Usuario eliminado"})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error eliminando usuario {id}: {e}")
        return jsonify({"error": "Error al eliminar usuario"}), 500
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
            logging.info(f"Lector presencial {correo} registrado.")
            return jsonify({"success": True, "mensaje": "Lector presencial registrado correctamente."})
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error registrando lector presencial: {e}")
            return jsonify({"success": False, "mensaje": "Error al registrar usuario.", "errores": str(e)})

    elif form.errors:
        logging.warning(f"Errores de validación: {form.errors}")
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
    Autocompleta datos usando OpenLibrary.
    Valida y guarda portada.
    """
    form = LibroForm()
    MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB

    # Autocompleta por ISBN
    isbn_param = request.args.get('isbn')
    if isbn_param and request.method == 'GET':
        data = obtener_datos_libro(isbn_param)
        if data and data.get("success"):
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
            flash(f"No se pudieron obtener datos para ISBN {isbn_param}.", 'warning')

    if form.validate_on_submit():
        isbn = form.isbn.data
        if Libro.query.filter_by(isbn=isbn).first():
            flash('Ya existe un libro con ese ISBN.', 'danger')
            return redirect(url_for('main.nuevo_libro'))

        cantidad_total = form.cantidad_total.data or 0
        portada_file = form.portada.data
        portada_url = form.portada_url.data or '/static/imagenes/portada_default.png'

        if portada_file:
            if portada_file.content_length and portada_file.content_length > MAX_FILE_SIZE:
                flash("El archivo de portada excede el tamaño permitido (2 MB).", "danger")
                return redirect(url_for('main.nuevo_libro'))

            ext = os.path.splitext(portada_file.filename)[1].lower()
            if ext not in ['.png', '.jpg', '.jpeg']:
                flash("Formato de archivo no permitido. Usa PNG o JPG.", "danger")
                return redirect(url_for('main.nuevo_libro'))

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

        try:
            db.session.add(nuevo_libro)
            db.session.commit()
            logging.info(f"Libro {isbn} registrado correctamente.")
            flash('Libro creado exitosamente.', 'success')
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error registrando libro {isbn}: {e}")
            flash('Error al registrar libro.', 'danger')

        return redirect(url_for('main.mostrar_libros'))

    return render_template('nuevo_libro.html', form=form)
# Mostrar libros
@main.route('/admin/libros/mostrar')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def mostrar_libros():
    libros = Libro.query.filter(Libro.estado != 'eliminado').all()
    logging.info(f"Mostrando {len(libros)} libros.")
    return render_template('libros_tabla.html', libros=libros)
# Eliminar libro
@main.route('/admin/libros/eliminar/<int:libro_id>', methods=['POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def eliminar_libro(libro_id):
    libro = Libro.query.get_or_404(libro_id)

    if libro.cantidad_disponible < libro.cantidad_total:
        flash('No se puede eliminar: hay ejemplares prestados.', 'danger')
        return redirect(url_for('main.admin_libros'))

    libro.marcar_como_eliminado()
    try:
        db.session.commit()
        logging.info(f"Libro {libro_id} marcado como eliminado.")
        flash('Libro marcado como eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error al eliminar libro {libro_id}: {e}")
        flash('Error al eliminar libro.', 'danger')

    return redirect(url_for('main.admin_libros'))
# Editar libro
@main.route('/admin/libros/editar/<int:libro_id>', methods=['GET', 'POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def editar_libro(libro_id):
    libro = Libro.query.get_or_404(libro_id)
    form = EditarLibroForm(obj=libro)
    MAX_FILE_SIZE = 2 * 1024 * 1024

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
            if portada_file.content_length and portada_file.content_length > MAX_FILE_SIZE:
                flash("La portada excede 2 MB.", "danger")
                return redirect(url_for('main.editar_libro', libro_id=libro_id))

            ext = os.path.splitext(portada_file.filename)[1].lower()
            if ext not in ['.png', '.jpg', '.jpeg']:
                flash("Formato no permitido. Usa PNG o JPG.", "danger")
                return redirect(url_for('main.editar_libro', libro_id=libro_id))

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

        try:
            db.session.commit()
            logging.info(f"Libro {libro_id} editado correctamente.")
            flash('Libro editado exitosamente.', 'success')
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error editando libro {libro_id}: {e}")
            flash('Error al editar libro.', 'danger')

        return redirect(url_for('main.mostrar_libros'))

    return render_template('editar_libro.html', form=form, libro=libro)
# Escanear libro
@main.route('/admin/libros/scan', methods=['GET'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def escanear_libro():
    return render_template('escanear_libro.html')
# Nueva reserva
@main.route('/admin/reservas/nuevo', methods=['GET', 'POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def reservas_agregar():
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
        reserva_existente = Reserva.query.filter_by(libro_id=libro.id, usuario_id=usuario.id)\
                                         .filter(Reserva.estado.in_(['pendiente', 'activa'])).first()
        if reserva_existente:
            flash('Reserva ya existe.', 'warning')
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
            msg = '✅ Reserva ACTIVADA.'
        else:
            posicion = Reserva.query.filter_by(libro_id=libro.id, estado='pendiente').count() + 1
            nueva_reserva = Reserva(
                usuario_id=usuario.id,
                libro_id=libro.id,
                posicion=posicion,
                estado='pendiente'
            )
            msg = f'⏳ Reserva PENDIENTE. Lugar: {posicion}.'

        try:
            db.session.add(nueva_reserva)
            db.session.commit()
            logging.info(f"Reserva creada: Usuario {usuario.id} Libro {libro.id} Estado {nueva_reserva.estado}")
            flash(msg, 'success')
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creando reserva: {e}")
            flash("Error creando reserva.", 'danger')

        return redirect(url_for('main.reservas_tabla'))

    return render_template('reservas_agregar.html', form=form)
# Reservar libro como lector
@main.route('/reservar/<int:libro_id>', methods=['GET', 'POST'])
@login_required
@roles_requeridos('lector')
@nocache
def reservar_libro_lector(libro_id):
    libro = Libro.query.get_or_404(libro_id)
    form = ReservaLectorForm()

    if form.validate_on_submit():
        if current_user.llave_prestamo != form.llave_prestamo.data:
            flash('Llave incorrecta.', 'danger')
            return redirect(url_for('main.reservar_libro_lector', libro_id=libro.id))

        reserva_existente = Reserva.query.filter_by(
            libro_id=libro.id,
            usuario_id=current_user.id
        ).filter(Reserva.estado.in_(['pendiente', 'activa'])).first()

        if reserva_existente:
            flash('Ya tienes una reserva para este libro.', 'warning')
            return redirect(url_for('main.catalogo'))

        if libro.cantidad_disponible > 0:
            flash('Hay ejemplares disponibles, solicita préstamo en biblioteca.', 'info')
            return redirect(url_for('main.catalogo'))

        posicion = Reserva.query.filter_by(libro_id=libro.id, estado='pendiente').count() + 1
        nueva_reserva = Reserva(
            usuario_id=current_user.id,
            libro_id=libro.id,
            posicion=posicion,
            estado='pendiente'
        )

        try:
            db.session.add(nueva_reserva)
            db.session.commit()
            logging.info(f"Reserva creada: Libro {libro.id}, Usuario {current_user.id}, Posición {posicion}")

            msg = Message(
                'Reserva registrada - Biblioteca',
                sender='noreply@biblioteca.com',
                recipients=[current_user.correo]
            )
            msg.body = f'''
Hola {current_user.nombre},

Tu reserva para "{libro.titulo}" ha sido registrada.
Lugar en la cola: {posicion}

Te notificaremos cuando esté disponible.
'''
            mail.send(msg)

            flash(f'⏳ Reserva registrada. Lugar: {posicion}.', 'success')

        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creando reserva libro {libro.id}: {e}")
            flash('Error al registrar la reserva.', 'danger')

        return redirect(url_for('main.catalogo'))

    return render_template('reservar_libro.html', form=form, libro=libro)
# 📌 Cancelar reserva lector
@main.route('/reservas/<int:reserva_id>/cancelar', methods=['POST'])
@login_required
@roles_requeridos('lector')
@nocache
def cancelar_reserva_lector(reserva_id):
    reserva = Reserva.query.get_or_404(reserva_id)

    if reserva.usuario_id != current_user.id:
        flash('No tienes permiso.', 'danger')
        return redirect(url_for('main.mis_libros'))

    libro = reserva.libro

    try:
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
        logging.info(f"Reserva {reserva.id} cancelada por Usuario {current_user.id}")

        msg = Message(
            'Reserva Cancelada',
            sender='noreply@biblioteca.com',
            recipients=[current_user.correo]
        )
        msg.body = f'''
Hola {current_user.nombre},

Tu reserva para "{libro.titulo}" ha sido cancelada correctamente.
'''
        mail.send(msg)

        flash(f'Reserva para "{libro.titulo}" cancelada.', 'success')

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error cancelando reserva {reserva.id}: {e}")
        flash('Error al cancelar reserva.', 'danger')

    return redirect(url_for('main.mis_libros'))
#  Editar reserva admin/bibliotecario
@main.route('/admin/reservas/editar/<int:reserva_id>', methods=['GET', 'POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def editar_reserva(reserva_id):
    reserva = Reserva.query.get_or_404(reserva_id)
    form = EditarReservaForm(obj=reserva)
    form.libro_id.choices = [(l.id, l.titulo) for l in Libro.query.order_by(Libro.titulo).all()]

    if request.method == 'GET':
        form.libro_id.data = reserva.libro_id
        form.fecha_expiracion.data = reserva.fecha_expiracion

    if form.validate_on_submit():
        try:
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
            logging.info(f"Reserva {reserva_id} editada.")
            flash('✅ Reserva actualizada.', 'success')

        except Exception as e:
            db.session.rollback()
            logging.error(f"Error editando reserva {reserva_id}: {e}")
            flash('Error actualizando reserva.', 'danger')

        return redirect(url_for('main.reservas_tabla'))

    return render_template('editar_reserva.html', form=form, reserva=reserva)
# Eliminar reserva admin/bibliotecario
@main.route('/admin/reservas/eliminar/<int:reserva_id>', methods=['POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def eliminar_reserva(reserva_id):
    reserva = Reserva.query.get_or_404(reserva_id)
    libro = reserva.libro

    try:
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
        logging.info(f"Reserva {reserva_id} eliminada.")
        flash(f'🗑️ Reserva #{reserva.id} eliminada.', 'success')

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error eliminando reserva {reserva_id}: {e}")
        flash('Error eliminando reserva.', 'danger')

    return redirect(url_for('main.reservas_tabla'))
#  Nuevo préstamo
@main.route('/admin/prestamos/nuevo', methods=['GET', 'POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario', 'lector')
@nocache
def nuevo_prestamo():
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

            try:
                db.session.add(nuevo_prestamo)
                db.session.commit()
                logging.info(f"Préstamo creado: Usuario {usuario.id}, Libro {libro.id}")

                msg = Message(
                    'Préstamo Registrado',
                    sender='noreply@biblioteca.com',
                    recipients=[usuario.correo]
                )
                msg.body = f'''
Hola {usuario.nombre},

Se ha registrado un préstamo para "{libro.titulo}".

📅 Préstamo: {nuevo_prestamo.fecha_prestamo}
⏰ Devolución esperada: {nuevo_prestamo.fecha_devolucion_esperada}

Por favor, devuelve el libro a tiempo.
'''
                mail.send(msg)

                flash('Préstamo registrado.', 'success')

            except Exception as e:
                db.session.rollback()
                logging.error(f"Error creando préstamo: {e}")
                flash('Error registrando préstamo.', 'danger')

            return redirect(url_for('main.mostrar_prestamos'))

        else:
            flash('Libro no disponible.', 'danger')

    return render_template('prestamos_agregar.html', form=form)
# Devolver préstamo
@main.route('/admin/prestamos/devolver/<int:prestamo_id>', methods=['POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def devolver_prestamo(prestamo_id):
    prestamo = Prestamo.query.get_or_404(prestamo_id)

    if prestamo.fecha_devolucion:
        flash('Ya fue devuelto.', 'warning')
    else:
        try:
            prestamo.fecha_devolucion = datetime.now().date()
            prestamo.estado = 'devuelto'

            libro = prestamo.libro
            if libro:
                libro.cantidad_disponible += 1
                libro.actualizar_estado()
                activar_siguiente_reserva(libro)

            db.session.commit()
            logging.info(f"Préstamo {prestamo_id} devuelto.")
            flash('📚 Devuelto. Stock actualizado.', 'success')

        except Exception as e:
            db.session.rollback()
            logging.error(f"Error devolviendo préstamo {prestamo_id}: {e}")
            flash('Error marcando devolución.', 'danger')

    return redirect(url_for('main.mostrar_prestamos'))

@main.route('/admin/prestamos/mostrar')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def mostrar_prestamos():
    prestamos = Prestamo.query.all()
    return render_template('prestamos_tabla.html', prestamos=prestamos)
# Prestar reserva activa
@main.route('/admin/reservas/prestar/<int:reserva_id>', methods=['POST'])
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def prestar_reserva(reserva_id):
    reserva = Reserva.query.get_or_404(reserva_id)

    if reserva.estado != 'activa':
        flash('⚠️ Solo reservas activas.', 'warning')
        return redirect(url_for('main.reservas_tabla'))

    libro = Libro.query.get(reserva.libro_id)
    if not libro:
        flash('❌ Libro no encontrado.', 'danger')
        return redirect(url_for('main.reservas_tabla'))

    prestamo_existente = Prestamo.query.filter_by(
        usuario_id=reserva.usuario_id,
        libro_id=reserva.libro_id,
        estado='activo'
    ).first()
    if prestamo_existente:
        flash('⚠️ Préstamo duplicado detectado.', 'warning')
        return redirect(url_for('main.reservas_tabla'))

    try:
        nuevo_prestamo = Prestamo(
            usuario_id=reserva.usuario_id,
            libro_id=reserva.libro_id,
            fecha_prestamo=datetime.utcnow().date(),
            fecha_devolucion_esperada=(datetime.utcnow() + timedelta(days=7)).date(),
            estado='activo'
        )
        db.session.add(nuevo_prestamo)

        libro.actualizar_estado()
        reserva.confirmar()
        activar_siguiente_reserva(libro)

        db.session.commit()
        logging.info(f"Reserva {reserva_id} convertida en préstamo.")
        flash(f'📚 Préstamo creado desde reserva #{reserva.id}.', 'success')

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error prestando reserva {reserva_id}: {e}")
        flash('Error creando préstamo.', 'danger')

    return redirect(url_for('main.reservas_tabla'))
# Tabla de reservas
@main.route('/admin/reservas/mostrar')
@login_required
@roles_requeridos('administrador', 'bibliotecario')
@nocache
def reservas_tabla():
    reservas = Reserva.query.filter(Reserva.estado != 'eliminada').all()
    return render_template('reservas_tabla.html', reservas=reservas)
#  Historial reportes
@main.route('/admin/reportes/historial')
@login_required
@roles_requeridos('administrador')
@nocache
def historial_reportes():
    historial = HistorialReporte.query.order_by(
        HistorialReporte.fecha_generacion.desc()
    ).all()
    return render_template('reportes/historial_reportes.html', historial=historial)
#  Fragmento atrasados
@main.route('/admin/reportes/atrasados')
@login_required
@roles_requeridos('administrador')
@nocache
def reporte_libros_atrasados():
    atrasados = Prestamo.query.filter(
        Prestamo.fecha_devolucion_esperada < date.today(),
        Prestamo.fecha_devolucion.is_(None)
    ).all()
    return render_template('reportes/fragmento_atrasados.html', atrasados=atrasados)
#  Descargar PDF préstamos
@main.route('/admin/reportes/descargar_reporte_prestados')
@login_required
@roles_requeridos('administrador')
@nocache
def descargar_reporte_prestados():
    prestamos = Prestamo.query.all()
    datos = []
    for idx, p in enumerate(prestamos, start=1):
        fecha_dev = p.fecha_devolucion.strftime('%Y-%m-%d') if p.fecha_devolucion else "No devuelto"
        datos.append([
            idx,
            p.libro.titulo,
            p.usuario.correo,
            p.fecha_prestamo.strftime('%Y-%m-%d'),
            fecha_dev
        ])

    columnas = ["#", "Libro", "Correo", "Fecha Préstamo", "Fecha Devolución"]

    try:
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
        logging.info(f"Reporte préstamos generado: {nombre_archivo}")

        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename={nombre_archivo}'
        return response

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error generando PDF préstamos: {e}")
        flash('Error generando PDF.', 'danger')
        return redirect(url_for('main.historial_reportes'))
# Reporte populares
@main.route('/admin/reportes/populares')
@login_required
@roles_requeridos('administrador')
@nocache
def reporte_libros_populares():
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
     .order_by(db.desc('total')).limit(5).all()

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
    for idx, p in enumerate(populares, start=1):
        datos.append([
            idx,
            p.titulo,
            p.autor,
            p.prestamos,
            p.reservas,
            p.total
        ])

    columnas = ["#", "Libro", "Autor", "Préstamos", "Reservas Pendientes", "Total"]

    try:
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
        logging.info(f"Reporte populares generado: {nombre_archivo}")

        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename={nombre_archivo}'
        return response

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error generando PDF populares: {e}")
        flash('Error generando PDF.', 'danger')
        return redirect(url_for('main.historial_reportes'))
# RUTA: Configuración admin
@main.route('/admin/configuracion', methods=['GET', 'POST'])
@login_required
@nocache
def configuracion():
    try:
        usuario = db.session.get(Usuario, current_user.id)

        if request.method == 'POST':
            nombre = request.form.get('nombre')
            apellido = request.form.get('apellido')
            correo = request.form.get('correo')
            archivo = request.files.get('foto_perfil')

            if nombre:
                usuario.nombre = nombre
            if apellido:
                usuario.apellido = apellido
            if correo:
                usuario.correo = correo

            if archivo and archivo.filename != '':
                if not allowed_file(archivo.filename):
                    flash("Tipo de archivo no permitido.", "danger")
                    return redirect(request.url)

                if len(archivo.read()) > MAX_CONTENT_LENGTH:
                    flash("El archivo es demasiado grande.", "danger")
                    return redirect(request.url)
                archivo.seek(0)  # Volver a inicio del archivo

                filename = secure_filename(archivo.filename)
                extension = os.path.splitext(filename)[1]
                nuevo_nombre = f"user_{usuario.id}{extension}"
                ruta_guardado = os.path.join(current_app.root_path, 'static', 'fotos_perfil', nuevo_nombre)
                archivo.save(ruta_guardado)
                usuario.foto = f"fotos_perfil/{nuevo_nombre}"

                flash("Foto de perfil actualizada con éxito", "success")
            else:
                flash("Perfil actualizado con éxito", "success")

            db.session.commit()
            logging.info(f"Usuario {usuario.id} actualizó su configuración")
            return redirect(url_for('main.configuracion'))

        return render_template('configuracion.html', usuario=usuario)

    except Exception as e:
        logging.error(f"Error en configuracion: {e}")
        flash("Ocurrió un error al actualizar la configuración.", "danger")
        return redirect(url_for('main.configuracion'))
# RUTA: Perfil del usuario lector
@main.route('/perfil', methods=['GET', 'POST'])
@login_required
@nocache
def perfil():
    try:
        if request.method == 'POST':
            usuario = db.session.get(Usuario, current_user.id)
            usuario.nombre = request.form['nombre']
            usuario.correo = request.form['correo']

            if 'foto_perfil' in request.files:
                file = request.files['foto_perfil']
                if file.filename != '':
                    if not allowed_file(file.filename):
                        flash("Tipo de archivo no permitido.", "danger")
                        return redirect(request.url)

                    if len(file.read()) > MAX_CONTENT_LENGTH:
                        flash("El archivo es demasiado grande.", "danger")
                        return redirect(request.url)
                    file.seek(0)

                    filename = secure_filename(file.filename)
                    ruta_carpeta = os.path.join('static', 'imagenes', 'perfil')
                    os.makedirs(ruta_carpeta, exist_ok=True)
                    filepath = os.path.join(ruta_carpeta, filename)
                    file.save(filepath)
                    usuario.foto = f'imagenes/perfil/{filename}'

            db.session.commit()
            logging.info(f"Usuario {usuario.id} actualizó su perfil")
            flash('Perfil actualizado correctamente.', 'success')
            return redirect(url_for('main.perfil'))

        return render_template('perfil.html', usuario=current_user)

    except Exception as e:
        logging.error(f"Error en perfil: {e}")
        flash('Error al actualizar el perfil.', 'danger')
        return redirect(url_for('main.perfil'))
# RUTA: Recuperar contraseña
@main.route('/recuperar', methods=['GET', 'POST'])
def recuperar():
    try:
        if request.method == 'POST':
            correo = request.form['correo']
            usuario = Usuario.query.filter_by(correo=correo).first()

            if usuario:
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
                logging.info(f"Token de recuperación enviado a {usuario.correo}")
                flash('Te enviamos un correo para recuperar tu contraseña.', 'info')
            else:
                flash('Correo no encontrado.', 'danger')

        return render_template('recuperar.html')

    except Exception as e:
        logging.error(f"Error en recuperar: {e}")
        flash('No se pudo procesar la solicitud de recuperación.', 'danger')
        return redirect(url_for('main.login'))
# RUTA: Restablecer contraseña
@main.route('/restablecer/<token>', methods=['GET', 'POST'])
def restablecer(token):
    try:
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
                logging.info(f"Usuario {usuario.id} restableció su contraseña")
                flash('Contraseña actualizada correctamente.', 'success')
                return redirect(url_for('main.login'))

        return render_template('restablecer.html')

    except Exception as e:
        logging.error(f"Error en restablecer: {e}")
        flash('No se pudo restablecer la contraseña.', 'danger')
        return redirect(url_for('main.login'))
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
