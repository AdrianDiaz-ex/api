from flask import Flask, request, jsonify, Response
import mysql.connector
from fpdf import FPDF  
import os
from datetime import timedelta


class PDFBoleta(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 18)
        self.set_text_color(0, 51, 102)
        self.cell(0, 10, 'Boleta de Calificaciones', border=0, ln=True, align='C')
        self.ln(5)
        self.set_line_width(0.5)
        self.line(10, 25, 200, 25)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Página {self.page_no()}', align='C')

    def alumno_info(self, nombre, apellido, semestre):
        self.set_font('Arial', 'B', 14)
        self.set_text_color(0, 0, 0)
        self.cell(0, 10, f'Alumno: {nombre} {apellido}', ln=True)
        self.cell(0, 10, f'Semestre: {semestre}', ln=True)
        self.ln(5)

    def calificaciones_table(self, calificaciones):
        # Encabezado de tabla
        self.set_fill_color(0, 51, 102)
        self.set_text_color(255, 255, 255)
        self.set_font('Arial', 'B', 12)
        self.cell(140, 10, 'Materia', border=1, fill=True)
        self.cell(40, 10, 'Calificación', border=1, ln=True, fill=True)

        # Contenido de tabla
        self.set_font('Arial', '', 12)
        self.set_text_color(0, 0, 0)
        fill = False
        for cal in calificaciones:
            self.set_fill_color(230, 230, 230) if fill else self.set_fill_color(255, 255, 255)
            self.cell(140, 10, cal['materia'], border=1, fill=fill)
            self.cell(40, 10, str(cal['calificacion']), border=1, ln=True, fill=fill)
            fill = not fill

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
                    for clave in ['hora_inicio', 'hora_fin']:
                        valor = fila.get(clave)
                        if valor is not None:
                            if isinstance(valor, timedelta):
                                # Convierte timedelta a string tipo "HH:MM:SS"
                                total_seconds = int(valor.total_seconds())
                                hours = total_seconds // 3600
                                minutes = (total_seconds % 3600) // 60
                                seconds = total_seconds % 60
                                fila[clave] = f"{hours:02}:{minutes:02}:{seconds:02}"
                            elif hasattr(valor, 'strftime'):
                                # Si fuera un datetime.time
                                fila[clave] = valor.strftime('%H:%M:%S')

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

        cursor.execute("""
            SELECT m.nombre AS materia, c.calificacion
            FROM calificaciones c
            INNER JOIN materias m ON c.materia_id = m.id
            WHERE c.alumno_id = %s AND m.semestre = %s
        """, (alumno_id, ultimo_semestre))
        calificaciones = cursor.fetchall()

        pdf = PDFBoleta()
        pdf.add_page()
        pdf.alumno_info(alumno['nombre'], alumno['apellido'], ultimo_semestre)
        pdf.calificaciones_table(calificaciones)

        response = Response(pdf.output(dest='S').encode('latin-1'))
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=boleta_{alumno_id}.pdf'
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

