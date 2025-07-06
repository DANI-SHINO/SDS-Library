import os

class Config:
    # Clave secreta para sesiones, CSRF y seguridad general
    SECRET_KEY = os.environ.get('SECRET_KEY', 'clave-secreta-super-segura')

    # Base de datos remota en Aiven usando PyMySQL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'ssl': {
                'ssl_verify_cert': False,   # Si no tienes archivo CA
                'ssl_check_hostname': False
                # Si tienes ca.pem, sería: 'ca': '/ruta/a/ca.pem'
            }
        }
    }

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configuración de correo
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'sandbox.smtp.mailtrap.io')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 2525))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
