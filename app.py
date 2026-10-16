import os
from decimal import Decimal, InvalidOperation

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for

load_dotenv()

app = Flask(__name__)


@app.route("/")
@app.route("/productos", methods=["GET", "POST"])
@app.route("/productos/<int:producto_id>/editar", methods=["GET", "POST"], endpoint="editar_producto")
@app.route("/productos/<int:producto_id>/eliminar", methods=["POST"], endpoint="eliminar_producto")
def productos(producto_id=None):
    conexion = None
    cursor = None
    columnas = []
    filas = []
    error = None
    estado = 200
    eliminar = request.path.endswith("/eliminar")
    editando = producto_id is not None and not eliminar
    datos = {campo: request.form.get(campo, "").strip() for campo in ("nombre", "precio", "stock")}
    if request.method == "POST" and not eliminar:
        try:
            precio = Decimal(datos["precio"])
            stock = int(datos["stock"])
            if not 1 <= len(datos["nombre"]) <= 100:
                raise ValueError()
            if not precio.is_finite() or not 0 <= precio <= Decimal("99999999.99"):
                raise ValueError()
            if precio != precio.quantize(Decimal("0.01")) or not 0 <= stock <= 2147483647:
                raise ValueError()
        except (ValueError, InvalidOperation):
            error = "Ingresa un nombre de hasta 100 caracteres, un precio válido con máximo dos decimales y un stock entero no negativo."
            estado = 400

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
        if producto_id is not None:
            cursor.execute("SELECT id, nombre, precio, stock FROM productos WHERE id = %s", (producto_id,))
            producto = cursor.fetchone()
            if producto is None:
                error = "El producto solicitado no existe."
                estado = 404
            elif request.method == "GET":
                datos = dict(zip(("nombre", "precio", "stock"), producto[1:]))
        if request.method == "POST" and error is None:
            if eliminar:
                cursor.execute("DELETE FROM productos WHERE id = %s", (producto_id,))
            elif editando:
                cursor.execute(
                    "UPDATE productos SET nombre = %s, precio = %s, stock = %s WHERE id = %s",
                    (datos["nombre"], precio, stock, producto_id),
                )
            else:
                cursor.execute(
                    "INSERT INTO productos (nombre, precio, stock) VALUES (%s, %s, %s)",
                    (datos["nombre"], precio, stock),
                )
            conexion.commit()
            return redirect(url_for("productos", resultado="eliminado" if eliminar else "actualizado" if editando else "creado"))
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
        error = "No se pudo completar la operación. Revisa la conexión y los permisos de MySQL."
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
        "productos.html", columnas=columnas, productos=filas, error=error,
        datos=datos, editando=editando, producto_id=producto_id,
        id_indice=columnas.index("id") if "id" in columnas else None,
        resultado=request.args.get("resultado"), creado=request.args.get("creado") == "1"
    ), estado


if __name__ == "__main__":
    app.run(debug=False)
