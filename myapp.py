from flask import Flask
from app.extensions import db, login_manager, mail
from app.models import Usuario
from app.routes import main
from app.config import Config
from app.utils import enviar_recordatorios
from datetime import datetime
from dotenv import load_dotenv
import os
import logging

logging.basicConfig(level=logging.INFO)

# ✅ Cargar variables de entorno
load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    app.register_blueprint(main)

    with app.app_context():
        try:
            db.create_all()
            logging.info("Tablas creadas correctamente.")
        except Exception as e:
            logging.error(f"Error creando tablas: {e}")

        # Solo crea admin si no existe
        if not Usuario.query.filter_by(rol='administrador').first():
            admin_password = os.environ.get('ADMIN_PASSWORD')

            if not admin_password:
                logging.warning("ADMIN_PASSWORD no definida en variables de entorno. Usando contraseña por defecto temporal.")

            admin = Usuario(
                nombre='admin',
                apellido='admin',
                correo='admin@biblioteca.com',
                documento='1000000000',
                direccion='Oficina principal',
                telefono='0000000000',
                fecha_nacimiento=datetime(1990, 1, 1),
                rol='administrador',
                activo=True
            )
            admin.set_password(admin_password)
            admin.generar_llave_prestamo()

            try:
                db.session.add(admin)
                db.session.commit()
                logging.info("Usuario administrador creado correctamente.")
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error creando usuario admin: {e}")

        try:
            enviar_recordatorios(app)
        except Exception as e:
            logging.warning(f"Error enviando recordatorios: {e}")

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
