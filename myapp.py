from flask import Flask
from app.extensions import db, login_manager, mail
from app.models import Usuario
from app.routes import main
from app.config import Config
from app.utils import enviar_recordatorios
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)

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
        # Protege creación de tablas con try/except
        try:
            db.create_all()
        except Exception as e:
            logging.error(f"Error creando tablas: {e}")

        # Solo crea admin si no existe
        if not Usuario.query.filter_by(rol='administrador').first():
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
            # Contraseña robusta
            admin.set_password('Adm1nL1br@2025')
            admin.generar_llave_prestamo()

            try:
                db.session.add(admin)
                db.session.commit()
                logging.info("Usuario administrador creado correctamente.")
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error creando admin: {e}")

    return app


if __name__ == '__main__':
    app = create_app()
    # ✅ Maneja posibles errores de conexión de correo
    try:
        enviar_recordatorios(app)
    except Exception as e:
        logging.warning(f"Error enviando recordatorios: {e}")

    app.run(debug=True)
