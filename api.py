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
                cursor.execute("""
                  SELECT m.nombre, m.creaditos, m.semestre, h.grupo, h.dia, h.hora_inicio, h.hora_fin
                  FROM materias m
                  LEFT JOIN horarios h ON m.id = h.materia_id
                  WHERE m.id NOT IN (
                  SELECT c.materia_id FROM calificaciones c WHERE c.alumno_id = %s
                   )
                 UNION
                  SELECT m.nombre, m.creaditos, m.semestre, h.grupo, h.dia, h.hora_inicio, h.hora_fin
                  FROM materias m
                  INNER JOIN calificaciones c ON m.id = c.materia_id
                  LEFT JOIN horarios h ON m.id = h.materia_id
                  WHERE c.calificacion < 70 AND c.alumno_id = %s
                """, (matricula, matricula))
                horarios_faltantes = cursor.fetchall()
                
                for fila in horarios_faltantes:
                    if 'hora_inicio' in fila and fila['hora_inicio'] is not None:
                        fila['hora_inicio'] = fila['hora_inicio'].strftime('%H:%M:%S')
                    if 'hora_fin' in fila and fila['hora_fin'] is not None:
                        fila['hora_fin'] = fila['hora_fin'].strftime('%H:%M:%S')

                return jsonify({
                    "status": "ok",
                    "rol": "alumno",
                    "alumno": alumno,
                    "datos": datos_alumno,
                    "calificaciones": calificaciones,
                    "horarios_faltantes": horarios_faltantes
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


