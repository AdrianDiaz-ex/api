from flask import Flask, request, jsonify, Response
import mysql.connector
from fpdf import FPDF  
import os

app = Flask(__name__)

@app.route('/login', methods=['POST'])
def login():
    datos = request.json
    correo = datos.get('correo')
    password = datos.get('password')
    tipo = datos.get('tipo')

    try:
        conn = mysql.connector.connect(
            host='sql5.freesqldatabase.com',
            user='sql5786672',
            password='aqaA1EVWzd',
            database='sql5786672',
            port=3306
        )
        cursor = conn.cursor(dictionary=True)

        if tipo == 'alumno':
            cursor.execute("SELECT * FROM inicio_sesion WHERE user=%s AND password=%s", (correo, password))
            alumno = cursor.fetchone()
            if alumno:
                matricula = alumno['Alumno']
                cursor.execute("SELECT * FROM alumnos WHERE id=%s", (matricula,))
                datos_alumno = cursor.fetchall()
                cursor.execute("SELECT c.calificacion, m.nombre, m.creaditos, m.semestre from calificaciones c inner join materias m on c.materia_id=m.id where c.alumno_id=%s", (matricula,))
                calificaciones = cursor.fetchall()

                return jsonify({
                    "status": "ok",
                    "rol": "alumno",
                    "alumno": alumno,
                    "datos": datos_alumno,
                    "calificaciones": calificaciones
                })
            else:
                return jsonify({"status": "error", "mensaje": "Credenciales incorrectas"}), 401

        elif tipo == 'admin':
            cursor.execute("SELECT * FROM admin WHERE admin=%s AND password=%s", (correo, password))
            admin = cursor.fetchone()
            if admin:
                cursor.execute("SELECT * FROM alumnos")
                alumnos = cursor.fetchall()
                cursor.execute("SELECT * FROM calificaciones")
                calificaciones = cursor.fetchall()
                return jsonify({
                    "status": "ok",
                    "rol": "admin",
                    "admin": admin,
                    "alumnos": alumnos,
                    "calificaciones": calificaciones
                })
            else:
                return jsonify({"status": "error", "mensaje": "Credenciales incorrectas"}), 401

        else:
            return jsonify({"status": "error", "mensaje": "Tipo de usuario no válido"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route('/boleta/<int:alumno_id>', methods=['GET'])
def boleta(alumno_id):
    try:
        conn = mysql.connector.connect(
            host='sql5.freesqldatabase.com',
            user='sql5786672',
            password='aqaA1EVWzd',
            database='sql5786672',
            port=3306
        )
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT nombre, apellido FROM alumnos WHERE id=%s", (alumno_id,))
        alumno = cursor.fetchone()

        if not alumno:
            return jsonify({"status": "error", "mensaje": "Alumno no encontrado"}), 404

        # 1️⃣ Obtener el semestre más alto del alumno
        cursor.execute("""
            SELECT MAX(m.semestre) AS ultimo_semestre
            FROM calificaciones c
            INNER JOIN materias m ON c.materia_id = m.id
            WHERE c.alumno_id = %s
        """, (alumno_id,))
        semestre_result = cursor.fetchone()
        ultimo_semestre = semestre_result['ultimo_semestre']

        if not ultimo_semestre:
            return jsonify({"status": "error", "mensaje": "No hay calificaciones para este alumno"}), 404

        # 2️⃣ Obtener calificaciones del último semestre
        cursor.execute("""
            SELECT m.nombre AS materia, c.calificacion
            FROM calificaciones c
            INNER JOIN materias m ON c.materia_id = m.id
            WHERE c.alumno_id = %s AND m.semestre = %s
        """, (alumno_id, ultimo_semestre))
        calificaciones = cursor.fetchall()

        # Generar PDF
        from fpdf import FPDF
        from flask import Response

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt=f"Boleta de {alumno['nombre']} {alumno['apellido']}", ln=True)
        pdf.cell(200, 10, txt=f"Semestre: {ultimo_semestre}", ln=True)

        pdf.set_font("Arial", size=12)
        for cal in calificaciones:
            pdf.cell(200, 10, txt=f"{cal['materia']}: {cal['calificacion']}", ln=True)

        response = Response(pdf.output(dest='S').encode('latin-1'))
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=boleta_{alumno_id}.pdf'
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/horarios_faltantes/<int:alumno_id>', methods=['GET'])
def horarios_faltantes(alumno_id):
    try:
        conn = mysql.connector.connect(
            host='sql5.freesqldatabase.com',
            user='sql5786672',
            password='aqaA1EVWzd',
            database='sql5786672',
            port=3306
        )
        cursor = conn.cursor(dictionary=True)

        # 1️⃣ Obtener materias aprobadas
        cursor.execute("""
            SELECT materia_id 
            FROM calificaciones 
            WHERE alumno_id = %s AND calificacion >= 70
        """, (alumno_id,))
        materias_aprobadas = [row['materia_id'] for row in cursor.fetchall()]

        # 2️⃣ Obtener materias que NO están aprobadas
        format_strings = ','.join(['%s'] * len(materias_aprobadas)) if materias_aprobadas else 'NULL'
        query = f"""
            SELECT h.*, m.nombre AS materia_nombre, ma.nombre AS maestro_nombre 
            FROM horarios h 
            INNER JOIN materias m ON h.materia_id = m.id
            INNER JOIN profesores ma ON h.maestro_id = ma.id
            WHERE h.materia_id NOT IN ({format_strings}) 
        """
        params = tuple(materias_aprobadas) if materias_aprobadas else ()
        cursor.execute(query, params)
        horarios = cursor.fetchall()

        # ✅ Convertir timedelta a string
        from datetime import timedelta
        for fila in horarios:
            for clave, valor in fila.items():
                if isinstance(valor, timedelta):
                    fila[clave] = str(valor)

        return jsonify({
            "status": "ok",
            "horarios_faltantes": horarios
        })

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

