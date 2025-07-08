from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Enum
from app.extensions import db
from datetime import datetime, timedelta
import secrets

# ------------------ MODELO USUARIO ------------------

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    apellido = db.Column(db.String(50), nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    documento = db.Column(db.String(20), unique=True, nullable=False)
    direccion = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    fecha_nacimiento = db.Column(db.Date, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default='usuario')
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=db.func.current_timestamp())
    foto = db.Column(db.String(255))
    llave_prestamo = db.Column(db.String(12), unique=True)  # Ejemplo: 123-456

    # Relaciones
    prestamos = db.relationship("Prestamo", back_populates="usuario", cascade="all, delete-orphan")
    reservas = db.relationship("Reserva", back_populates="usuario", cascade="all, delete-orphan")
    favoritos = db.relationship("Favorito", back_populates="usuario", cascade="all, delete-orphan")

    # Métodos utilitarios
    def generar_llave_prestamo(self):
        parte1 = str(secrets.randbelow(900) + 100)  # 100–999
        parte2 = str(secrets.randbelow(900) + 100)
        self.llave_prestamo = f"{parte1}-{parte2}"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<Usuario(id={self.id}, correo='{self.correo}')>"

class HistorialReporte(db.Model):
    __tablename__ = 'historial_reportes'

    id = db.Column(db.Integer, primary_key=True)
    nombre_reporte = db.Column(db.String(100), nullable=False)
    ruta_archivo = db.Column(db.String(200), nullable=False)
    fecha_generacion = db.Column(db.DateTime, default=datetime.utcnow)
    admin_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)

    admin = db.relationship("Usuario", backref="reportes_generados")

    def __repr__(self):
        return f"<HistorialReporte(id={self.id}, nombre_reporte='{self.nombre_reporte}')>"


# ------------------ MODELO LIBRO ------------------

class Libro(db.Model):
    __tablename__ = 'libros'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    autor = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(100))
    cantidad_total = db.Column(db.Integer, default=0, nullable=False)
    cantidad_disponible = db.Column(db.Integer, default=0, nullable=False)
    fecha_publicacion = db.Column(db.Date)
    editorial = db.Column(db.String(100))
    isbn = db.Column(db.String(30), unique=True, nullable=False)
    descripcion = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, default=db.func.current_timestamp())
    estado = db.Column(db.String(20), default="disponible")
    portada_url = db.Column(db.String(255), default='/static/imagenes/portada_default.png')

    # Relaciones
    prestamos = db.relationship("Prestamo", back_populates="libro", cascade="all, delete-orphan")
    reservas = db.relationship("Reserva", back_populates="libro", cascade="all, delete-orphan")
    favoritos = db.relationship("Favorito", back_populates="libro", cascade="all, delete-orphan")

    def actualizar_estado(self):
        if self.estado == "eliminado":
            return
        self.estado = "prestados" if self.cantidad_disponible == 0 else "disponible"

    def marcar_como_eliminado(self):
        self.estado = "eliminado"

    def __repr__(self):
        return f"<Libro(id={self.id}, titulo='{self.titulo}', isbn='{self.isbn}')>"


# ------------------ MODELO PRESTAMO ------------------

class Prestamo(db.Model):
    __tablename__ = 'prestamos'

    id = db.Column(db.Integer, primary_key=True)
    libro_id = db.Column(db.Integer, db.ForeignKey('libros.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha_prestamo = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    fecha_devolucion_esperada = db.Column(db.Date, nullable=False)
    fecha_devolucion = db.Column(db.Date)  # Se usa este correo para que coincida con las plantillas
    estado = db.Column(
        Enum('prestado', 'devuelto', 'atrasado', 'activo', name='estado_prestamo'),
        nullable=False,
        default='activo'
    )

    libro = db.relationship("Libro", back_populates="prestamos")
    usuario = db.relationship("Usuario", back_populates="prestamos")

    def __repr__(self):
        return f"<Prestamo(id={self.id}, libro_id={self.libro_id}, usuario_id={self.usuario_id})>"


# ------------------ MODELO RESERVA ------------------

class Reserva(db.Model):
    __tablename__ = 'reservas'

    id = db.Column(db.Integer, primary_key=True)
    libro_id = db.Column(db.Integer, db.ForeignKey('libros.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha_reserva = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_activacion = db.Column(db.DateTime, nullable=True)
    fecha_expiracion = db.Column(db.DateTime, nullable=True)
    posicion = db.Column(db.Integer, nullable=True)
    estado = db.Column(db.Enum(
        'pendiente',
        'activa',
        'confirmada',
        'vencida',
        'cancelada',
        'eliminada',
        name='estado_reserva'
    ), default='pendiente', nullable=False)
    
    # Relaciones opcionales
    libro = db.relationship('Libro', back_populates='reservas')
    usuario = db.relationship('Usuario', back_populates='reservas')

    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Reserva {self.id} - Libro {self.libro_id} - Usuario {self.usuario_id} - Estado {self.estado}>"

    def activar(self):
        """ Activa la reserva cuando hay stock disponible. """
        self.estado = 'activa'
        self.fecha_activacion = datetime.utcnow()
        self.fecha_expiracion = self.fecha_activacion + timedelta(days=7)
        self.posicion = None

    def marcar_vencida(self):
        """ Marca como vencida si expiró sin recoger. """
        self.estado = 'vencida'
        self.posicion = None

    def confirmar(self):
        """ Marca como confirmada cuando el lector recoge el libro. """
        self.estado = 'confirmada'
        self.posicion = None


# ------------------ MODELO FAVORITO ------------------

class Favorito(db.Model):
    __tablename__ = 'favoritos'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    libro_id = db.Column(db.Integer, db.ForeignKey('libros.id'), nullable=False)
    fecha_agregado = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship("Usuario", back_populates="favoritos")
    libro = db.relationship("Libro", back_populates="favoritos")

    def __repr__(self):
        return f"<Favorito(id={self.id}, usuario_id={self.usuario_id}, libro_id={self.libro_id})>"
