from itsdangerous import URLSafeTimedSerializer
from flask import current_app
import random
import os
from io import BytesIO
from app.models import Usuario, Prestamo, Reserva
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import  TA_LEFT
from reportlab.lib.units import inch
from app.extensions import mail, db
from flask_mail import Message
from datetime import date, timedelta
import os
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph,Indenter, Table, TableStyle, Spacer
)

def generar_reporte_con_plantilla(datos, columnas, subtitulo):
    """
    Genera un PDF usando la plantilla base.
    :param datos: lista de filas [[col1, col2, ...], ...]
    :param columnas: lista de encabezados ["#", "Libro", ...]
    :param subtitulo: título del reporte
    :return: bytes del PDF
    """
    buffer = BytesIO()

    plantilla_path = os.path.join(current_app.root_path, 'static', 'imagenes', 'plantilla.jpg')

    datos_con_numeracion = []
    for idx, fila in enumerate(datos, 1):
        datos_con_numeracion.append([idx] + fila)

    ReporteSBS(
        buffer=buffer,
        subtitulo=subtitulo,
        columnas=columnas,
        datos=datos_con_numeracion,
        plantilla_fondo=plantilla_path
    )

    pdf = buffer.getvalue()
    buffer.close()
    return pdf

class FooterCanvas(canvas.Canvas):
    def __init__(self, *args, plantilla_fondo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []
        self.plantilla_fondo = plantilla_fondo
        self.width, self.height = LETTER

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            self.draw_header_footer(page_count)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_header_footer(self, page_count):
        # Dibuja la plantilla de fondo en cada página (CUBRIENDO TODA LA PÁGINA)
        if self.plantilla_fondo:
            self.drawImage(
                self.plantilla_fondo,
                0, 0,  # Empezar desde abajo a la izquierda
                width=self.width,
                height=self.height,
                preserveAspectRatio=False
            )

        # Número de página encima del fondo
        self.setFont("Helvetica", 8)
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(self.width - inch, 0.75 * inch, page_text)


class ReporteSBS:
    def __init__(self, buffer, subtitulo, columnas, datos, plantilla_fondo=None):
        self.buffer = buffer
        self.subtitulo = subtitulo
        self.columnas = columnas
        self.datos = datos
        self.plantilla_fondo = plantilla_fondo

        self.styles = getSampleStyleSheet()
        self.width, self.height = LETTER
        self.story = []

        self.build_pdf()

    def build_pdf(self):
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=LETTER,
            rightMargin=40, leftMargin=40,
            topMargin=200,  # Controla dónde empieza TODO el contenido (título incluido)
            bottomMargin=100
        )

        # TÍTULO PRINCIPAL
        # - fontSize: más pequeño (24)
        # - textColor: azul oscuro más visible
        # - spaceAfter: controla la distancia hacia el subtítulo
        titulo_style = ParagraphStyle(
            'Titulo',
            fontSize=24,  # Tamaño más pequeño
            alignment=TA_LEFT,
            textColor=colors.HexColor("#F5F5F5"),  # Azul oscuro más visible
            spaceAfter=15  # Espacio debajo del título
        )

        # SUBTÍTULO
        # - fontSize: lo mantienes
        # - spaceBefore: espacio extra SOLO arriba del subtítulo (para bajarlo)
        # - spaceAfter: espacio debajo del subtítulo
        subtitulo_style = ParagraphStyle(
            'Subtitulo',
            textColor=colors.HexColor("#F5F5F5"),
            fontSize=20,   # Opcional: un poco más pequeño si quieres
            alignment=TA_LEFT,
            spaceBefore=20,  # Baja solo el subtítulo unos px extra
            spaceAfter=20    # Espacio debajo del subtítulo para separar de la tabla
        )
        self.story.append(Indenter(left=60, right=0))  # 40 puntos a la derecha
        self.story.append(Paragraph(self.subtitulo, subtitulo_style))
        self.story.append(Indenter(left=-60, right=0)) # Regresa

        # ESPACIO EXTRA para bajar la tabla aún más
        # Puedes ajustar este número para mover solo la tabla.
        self.story.append(Spacer(1, 30))  #  Más alto → la tabla baja más

        # Construir la tabla
        self.build_table()

        # Construir PDF con fondo y pie de página
        doc.build(
            self.story,
            onFirstPage=self.add_background_and_footer,
            onLaterPages=self.add_background_and_footer
        )


    def build_table(self):
        data = []
        encabezados = [Paragraph(f"<b>{col}</b>", self.styles["Normal"]) for col in self.columnas]
        data.append(encabezados)

        for fila in self.datos:
            data.append(fila)

        tabla = Table(data, hAlign="CENTER")
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ffffff")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
        ]))
        self.story.append(tabla)

    def add_background_and_footer(self, canvas, doc):
        # Dibuja la plantilla de fondo primero
        if self.plantilla_fondo:
            canvas.drawImage(
                self.plantilla_fondo,
                0, 0,
                width=self.width,
                height=self.height,
                preserveAspectRatio=False
            )
        # Número de página
        canvas.setFont("Helvetica", 8)
        page_text = f"Página {doc.page}"
        canvas.drawRightString(self.width - inch, 0.75 * inch, page_text)

def activar_siguiente_reserva(libro):
    """
    Activa la siguiente reserva pendiente para este libro,
    solo si hay ejemplares disponibles.
    """

    if libro.cantidad_disponible <= 0:
        # No hay stock, no se hace nada
        return

    # Trae todas las reservas PENDIENTES en orden de fecha_reserva
    reservas_pendientes = Reserva.query.filter_by(
        libro_id=libro.id,
        estado='pendiente'
    ).order_by(Reserva.fecha_reserva.asc()).all()

    if reservas_pendientes:
        siguiente_reserva = reservas_pendientes[0]

        # Activa la primera en la cola
        siguiente_reserva.activar()
        libro.cantidad_disponible -= 1
        libro.actualizar_estado()

        # Recalcula posiciones para los que quedan pendientes
        nuevas_pendientes = reservas_pendientes[1:]
        for idx, reserva in enumerate(nuevas_pendientes, start=1):
            reserva.posicion = idx

        # Envía correo al usuario avisando
        msg = Message(
            '¡Tu reserva ahora está ACTIVA!',
            sender='noreply@biblioteca.com',
            recipients=[siguiente_reserva.usuario.correo]
        )
        msg.body = f"""
Hola {siguiente_reserva.usuario.nombre},

Tu reserva para el libro "{libro.titulo}" ahora está ACTIVA.
Tienes 7 días para recogerlo, hasta el {siguiente_reserva.fecha_expiracion.strftime('%Y-%m-%d')}.

¡No pierdas tu turno!

Biblioteca Avocado 📚
"""
        mail.send(msg)

def generar_token(email):
    serializer = URLSafeTimedSerializer(current_app.secret_key)
    return serializer.dumps(email, salt='recuperar-contrasena')

def verificar_token(token, max_age=3600):
    serializer = URLSafeTimedSerializer(current_app.secret_key)
    try:
        email = serializer.loads(token, salt='recuperar-contrasena', max_age=max_age)
    except:
        return None
    return email

def generar_llave_prestamo():
    while True:
        nueva_llave = f"{random.randint(100, 999)}-{random.randint(100, 999)}"
        if not Usuario.query.filter_by(llave_prestamo=nueva_llave).first():
            return nueva_llave

# app/utils.py
def enviar_recordatorios(app):
    with app.app_context():
        mañana = date.today() + timedelta(days=1)
        prestamos = Prestamo.query.filter(
            Prestamo.estado == 'activo',
            Prestamo.fecha_devolucion_esperada == mañana
        ).all()

        for prestamo in prestamos:
            usuario = prestamo.usuario
            libro = prestamo.libro

            msg = Message(
                '⏰ Recordatorio de Devolución',
                sender='noreply@biblioteca.com',
                recipients=[usuario.correo]
            )
            msg.body = f"""
Hola {usuario.nombre},

Te recordamos que debes devolver el libro "{libro.titulo}" mañana.

📅 Fecha de devolución esperada: {prestamo.fecha_devolucion_esperada}

¡Gracias por usar nuestra biblioteca!

Biblioteca Avocado
"""
            mail.send(msg)



