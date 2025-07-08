from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, PasswordField, SelectField, DateField, SubmitField,
    TextAreaField, IntegerField, HiddenField
)
from wtforms.validators import (
    DataRequired, Length, EqualTo, Regexp, ValidationError,
    Optional, NumberRange, Email
)
from app.models import Usuario
from datetime import date

# Validador de tamaño de archivo
def file_size_limit(max_size_mb=2):
    def _file_size(form, field):
        if field.data:
            field.data.stream.seek(0, 2)  # Ir al final del archivo
            file_size = field.data.stream.tell()
            field.data.stream.seek(0)     # Volver al inicio
            if file_size > max_size_mb * 1024 * 1024:
                raise ValidationError(f"El archivo no puede superar los {max_size_mb} MB.")
    return _file_size


# User Registration Form
class RegistroForm(FlaskForm):
    # First name, required, 2-50 chars
    nombre = StringField(
        'Nombre',
        validators=[DataRequired(), Length(min=2, max=50)]
    )
    # Last name, optional, 2-50 chars
    apellido = StringField(
        'Apellido',
        validators=[Optional(), Length(min=2, max=50)]
    )
    # Email address, required and must be valid format
    correo = StringField(
        'Correo electrónico',
        validators=[DataRequired(), Email()]
    )
    # ID document number, required, 5-20 chars
    documento = StringField(
        'Número de Documento',
        validators=[DataRequired(), Length(min=5, max=20)]
    )
    # Address, required, 5-100 chars
    direccion = StringField(
        'Dirección',
        validators=[DataRequired(), Length(min=5, max=100)]
    )
    # Phone number, optional, 7-20 chars
    telefono = StringField(
        'Teléfono',
        validators=[Optional(), Length(min=7, max=20)]
    )
    # Birth date, required
    fecha_nacimiento = DateField(
        'Fecha de Nacimiento',
        format='%Y-%m-%d',
        validators=[DataRequired()]
    )
    # Password, required, minimum 8 chars, must contain letters and numbers
    password = PasswordField(
        'Contraseña',
        validators=[
            DataRequired(),
            Length(min=8, message='La contraseña debe tener al menos 8 caracteres'),
            Regexp(
                r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]+$',
                message='Debe contener letras y números.'
            )
        ]
    )
    # Confirm password, must match
    confirm_password = PasswordField(
        'Confirmar contraseña',
        validators=[
            DataRequired(),
            EqualTo('password', message='Las contraseñas deben coincidir')
        ]
    )
    submit = SubmitField('Registrarse')

    # Validate if email already exists
    def validate_correo(self, correo):
        if Usuario.query.filter_by(correo=correo.data).first():
            raise ValidationError('Ya existe una cuenta con este correo.')

    # Validate if document number already exists
    def validate_documento(self, documento):
        if Usuario.query.filter_by(documento=documento.data).first():
            raise ValidationError('Ya existe una cuenta con este número de documento.')

# New Book Registration Form
class LibroForm(FlaskForm):
    # ISBN, required, only numbers, X, and hyphens
    isbn = StringField(
        'ISBN',
        validators=[
            DataRequired(message="El ISBN es obligatorio."),
            Length(min=10, max=17, message="El ISBN debe tener entre 10 y 17 caracteres."),
            Regexp(r'^[0-9X-]+$', message='El ISBN solo puede contener números, guiones y "X".')
        ]
    )
    # Title, required, max 255 chars
    titulo = StringField(
        'Título',
        validators=[
            DataRequired(message="El título es obligatorio."),
            Length(max=255, message="El título no puede exceder los 255 caracteres.")
        ]
    )
    # Author, required, max 255 chars
    autor = StringField(
        'Autor',
        validators=[
            DataRequired(message="El autor es obligatorio."),
            Length(max=255, message="El nombre del autor no puede exceder los 255 caracteres.")
        ]
    )
    # Description, optional
    descripcion = TextAreaField(
        'Descripción',
        validators=[Optional()]
    )
    # Category, required, user must select from choices
    categoria = SelectField(
        'Categoría',
        choices=[
            # List of available categories
            ('novela', 'Novela'),
            ('filosofia', 'Filosofía'),
            ('poesia', 'Poesía'),
            ('teatro', 'Teatro'),
            ('ensayo', 'Ensayo'),
            ('cronica', 'Crónica'),
            ('historieta', 'Historieta'),
            ('biografia', 'Biografía'),
            ('cuento', 'Cuento'),
            ('ciencia_ficcion', 'Ciencia Ficción'),
            ('thriller', 'Thriller'),
            ('fantasía', 'Fantasía'),
            ('clasico', 'Clásico'),
            ('terror', 'Terror'),
            ('romance', 'Romance'),
            ('historia', 'Historia'),
            ('ficcion_criminal', 'Ficción Criminal'),
            ('drama', 'Drama'),
            ('comedia', 'Comedia'),
            ('juvenil', 'Juvenil'),
            ('sátira', 'Sátira'),
            ('gonzo', 'Gonzo'),
            ('realismo_magico', 'Realismo Mágico'),
            ('novela_historica', 'Novela Histórica'),
            ('otros', 'Otros'),
            ('', 'Seleccione una categoría')
        ],
        validators=[DataRequired(message="Debe seleccionar una categoría.")],
        render_kw={"placeholder": "Seleccione una categoría"}
    )
    # Publisher, optional, max 255 chars
    editorial = StringField(
        'Editorial',
        validators=[Optional(), Length(max=255)]
    )
    # Publication date, optional
    fecha_publicacion = DateField(
        'Fecha de Publicación',
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    # Total copies, required, must be zero or positive
    cantidad_total = IntegerField(
        'Cantidad Total',
        validators=[
            DataRequired(message="La cantidad total es obligatoria."),
            NumberRange(min=0, message="La cantidad total no puede ser negativa.")
        ]
    )
    # Cover image file, only JPG or PNG allowed
    portada = FileField(
        'Portada',
        validators=[FileAllowed(['jpg', 'jpeg', 'png'], 'Solo se permiten imágenes JPG y PNG.'), file_size_limit(2) ]
    )
    # Cover URL for saving image path in DB
    portada_url = HiddenField(
        'URL de Portada',
        validators=[Optional(), Length(max=500)]
    )
    submit = SubmitField('Guardar')

# Edit Existing Book Form
class EditarLibroForm(FlaskForm):
    titulo = StringField("Título", validators=[DataRequired()])
    autor = StringField("Autor", validators=[DataRequired()])
    descripcion = TextAreaField("Descripción", validators=[Optional()])
    categoria = SelectField(
        "Categoría",
        choices=[
            ('novela', 'Novela'),
            ('filosofia', 'Filosofía'),
            ('poesia', 'Poesía'),
            ('teatro', 'Teatro'),
            ('ensayo', 'Ensayo'),
            ('cronica', 'Crónica'),
            ('historieta', 'Historieta'),
            ('biografia', 'Biografía'),
            ('cuento', 'Cuento'),
            ('audiolibro', 'Audiolibro')
        ],
        validators=[DataRequired()]
    )
    cantidad_total = IntegerField(
        "Cantidad Total",
        validators=[Optional(), NumberRange(min=0)]
    )
    cantidad_disponible = IntegerField(
        "Cantidad Disponible",
        validators=[Optional(), NumberRange(min=0)]
    )
    fecha_publicacion = DateField(
        "Fecha de Publicación",
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    editorial = StringField("Editorial", validators=[Optional()])
    portada_url = HiddenField('URL de Portada', validators=[Optional()])
    portada = FileField(
        'Portada',
        validators=[FileAllowed(['jpg', 'jpeg', 'png'], 'Solo se permiten imágenes JPG y PNG.'), file_size_limit(2) ]
    )
    submit = SubmitField("Guardar cambios")

# Loan Form
class PrestamoForm(FlaskForm):
    # Unique loan key, required, must be 7 chars like XXX-XXX
    llave_prestamo = StringField(
        "Llave de préstamo",
        validators=[
            DataRequired(),
            Length(min=7, max=7, message="La llave debe tener el formato XXX-XXX (7 caracteres)")
        ]
    )
    # Book ID, selected from options
    libro_id = SelectField("Libro", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Guardar")

# New Reservation Form (Admin)
class NuevaReservaForm(FlaskForm):
    llave_prestamo = StringField(
        "Llave de préstamo",
        validators=[
            DataRequired(),
            Length(min=7, max=7, message="La llave debe tener el formato XXX-XXX")
        ]
    )
    libro_id = SelectField("Libro", coerce=int, validators=[DataRequired()])
    fecha_expiracion = DateField("Fecha Expiración", format='%Y-%m-%d')
    submit = SubmitField("Guardar")

# Reservation Form for Reader
class ReservaLectorForm(FlaskForm):
    llave_prestamo = StringField(
        'Llave de Préstamo',
        validators=[DataRequired(message='Ingresa tu llave de préstamo.')]
    )
    submit = SubmitField('Reservar')

# Edit Existing Reservation Form
class EditarReservaForm(FlaskForm):
    libro_id = SelectField('Libro', coerce=int, validators=[DataRequired()])
    fecha_expiracion = DateField('Fecha de Expiración', format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField('Guardar cambios')

# Register New In-person Reader
class AgregarLectorPresencialForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired(), Length(min=2, max=50)])
    documento = StringField('Número de Documento', validators=[DataRequired(), Length(min=5, max=20)])
    direccion = StringField('Dirección', validators=[DataRequired(), Length(min=5, max=100)])
    correo = StringField('Correo', validators=[DataRequired(), Email(), Length(max=120)])
    submit = SubmitField('Registrar')

    # Validate document uniqueness
    def validate_correo(self, correo):
        try:
            if Usuario.query.filter_by(correo=correo.data).first():
                raise ValidationError('Ya existe una cuenta con este correo.')
        except Exception:
            raise ValidationError('Error validando el correo. Intenta de nuevo.')
# editar usuarios 
class EditarUsuarioForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired()])
    correo = StringField('Correo electrónico', validators=[DataRequired(), Email()])
    direccion = StringField('Dirección', validators=[DataRequired()])
    rol = SelectField('Rol', choices=[('lector', 'Lector'), ('bibliotecario', 'Bibliotecario'), ('administrador', 'Administrador')], validators=[DataRequired()])
    submit = SubmitField('Guardar')

