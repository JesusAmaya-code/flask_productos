import os

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, render_template

load_dotenv()

app = Flask(__name__)


@app.route("/")
@app.route("/productos")
def productos():
    conexion = None
    cursor = None
    columnas = []
    filas = []
    error = None
    estado = 200

    try:
        requeridas = ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "DB_PORT")
        if any(os.getenv(nombre) is None for nombre in requeridas):
            raise ValueError("Faltan variables de configuración")
        if any(not os.getenv(nombre) for nombre in ("DB_HOST", "DB_USER", "DB_NAME")):
            raise ValueError("Configuración incompleta")
        puerto = int(os.environ["DB_PORT"])
        if not 1 <= puerto <= 65535:
            raise ValueError("Puerto inválido")

        conexion = mysql.connector.connect(
            host=os.environ["DB_HOST"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"],
            port=puerto,
            connection_timeout=10,
        )
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM productos")
        columnas = [columna[0] for columna in cursor.description]
        filas = cursor.fetchall()
    except ValueError:
        app.logger.error("Configuración de MySQL incompleta o inválida.")
        error = "Revisa las variables de conexión en el archivo .env."
        estado = 500
    except mysql.connector.Error as exc:
        # Solo registrar el código: el texto del error podría incluir datos sensibles.
        app.logger.error("Error de MySQL (código %s).", exc.errno)
        error = "No se pudieron cargar los productos. Revisa la conexión y los permisos de MySQL."
        estado = 503
    finally:
        # Cada cierre es independiente: un fallo del cursor no impide cerrar la conexión.
        if cursor is not None:
            try:
                cursor.close()
            except mysql.connector.Error:
                app.logger.warning("No se pudo cerrar el cursor de MySQL.")
        if conexion is not None:
            try:
                conexion.close()
            except mysql.connector.Error:
                app.logger.warning("No se pudo cerrar la conexión de MySQL.")

    return render_template(
        "productos.html", columnas=columnas, productos=filas, error=error
    ), estado


if __name__ == "__main__":
    app.run(debug=False)
