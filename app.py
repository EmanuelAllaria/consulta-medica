from flask import Flask, request, jsonify, render_template
import os
import requests
from bs4 import BeautifulSoup
import re
import mysql.connector
import psycopg2
from psycopg2 import connect
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configuración de base de datos basada en el entorno
db_connection = None
cursor = None

try:
    if os.getenv("FLASK_ENV") == "production":
        # Conexión para PostgreSQL usando la URL en producción
        db_connection = connect("postgresql://emanuel_allaria:ScwDEklhDwyHTbX0VYIqZk59WaWNjwLM@dpg-csjc9prtq21c73dbn2tg-a/consulta_medica")
        print("Conexión a la base de datos PostgreSQL exitosa.")
    else:
        # Conexión para MySQL en desarrollo
        db_connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="consulta_medica"
        )
        print("Conexión a la base de datos MySQL exitosa.")

    cursor = db_connection.cursor()
except (mysql.connector.Error, psycopg2.Error) as err:
    print(f"Error al conectar a la base de datos: {err}")

def obtener_datos_desde_bd():
    """
    Obtiene los datos de síntomas y diagnósticos desde la base de datos MySQL.
    """
    cursor.execute("SELECT nombre, sintomas FROM enfermedades")
    rows = cursor.fetchall()
    enfermedades = []
    for row in rows:
        nombre = row[0]
        sintomas = row[1].lower().split(', ')
        enfermedades.append({'nombre': nombre, 'sintomas': sintomas})
    return enfermedades

def obtener_descripcion_web(enfermedad):
    """
    Obtiene una breve descripción de la enfermedad desde Wikipedia.
    """
    try:
        # Normalizar el nombre de la enfermedad para mejorar la compatibilidad con Wikipedia
        enfermedad_normalizada = re.sub(r'\(.*?\)', '', enfermedad)  # Remover texto entre paréntesis
        enfermedad_normalizada = enfermedad_normalizada.strip().replace(' ', '_')  # Reemplazar espacios por guiones bajos
        
        url = f"https://es.wikipedia.org/wiki/{enfermedad_normalizada}"
        headers = {'User-Agent': 'consulta-medica-bot'}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            parrafos = soup.find_all('p')
            
            for parrafo in parrafos:
                texto = parrafo.get_text(strip=True)
                if texto and len(texto) > 50:
                    return texto
            return "Descripción no disponible."
        
        elif response.status_code == 404:
            return "La página de Wikipedia para esta enfermedad no está disponible."
        else:
            return "No se pudo obtener la descripción desde Wikipedia."
    except requests.exceptions.RequestException as e:
        print(f"Error al realizar la solicitud HTTP: {e}")
        return "Descripción no disponible debido a un error de conexión."
    except Exception as e:
        print(f"Error inesperado: {e}")
        return "Descripción no disponible."

def obtener_tratamiento(diagnostico):
    """
    Obtiene el tratamiento asociado a un diagnóstico desde la base de datos.
    """
    cursor.execute("SELECT tratamiento FROM enfermedades WHERE nombre = %s", (diagnostico,))
    row = cursor.fetchone()
    if row:
        return row[0]
    return "Tratamiento no disponible"

def obtener_lista_sintomas():
    """
    Obtiene todos los síntomas desde la tabla de síntomas.
    """
    cursor.execute("SELECT nombre FROM sintomas")
    rows = cursor.fetchall()
    return [row[0].lower() for row in rows]

@app.route('/', methods=['GET'])
def ui():
    return render_template('diagnosticar.html')

@app.route('/diagnosticar', methods=['POST'])
def diagnosticar():
    try:
        data = request.json if request.is_json else request.form
        sintomas_usuario = data.get('sintomas', '')

        if not sintomas_usuario:
            return jsonify({'error': 'Por favor, proporciona una lista de síntomas'}), 400

        # Transformar los síntomas ingresados en una lista de palabras clave
        lista_sintomas_usuario = sintomas_usuario.lower().split(', ')
        lista_sintomas_bd = obtener_lista_sintomas()
        sintomas_filtrados = [s for s in lista_sintomas_usuario if s in lista_sintomas_bd]

        if not sintomas_filtrados:
            return jsonify({'error': 'Ningún síntoma proporcionado coincide con nuestra base de datos'}), 400

        # Obtener datos desde la base de datos
        enfermedades = obtener_datos_desde_bd()
        mejor_coincidencia = None
        max_sintomas_encontrados = 0

        # Buscar la enfermedad que mejor coincida con los síntomas proporcionados
        for enfermedad in enfermedades:
            sintomas_enfermedad = enfermedad['sintomas']
            sintomas_encontrados = len(set(sintomas_filtrados) & set(sintomas_enfermedad))
            if sintomas_encontrados > max_sintomas_encontrados:
                max_sintomas_encontrados = sintomas_encontrados
                mejor_coincidencia = enfermedad

        if mejor_coincidencia:
            tratamiento = obtener_tratamiento(mejor_coincidencia['nombre'])
            return jsonify({'diagnostico': mejor_coincidencia['nombre'], 'tratamiento': tratamiento, 'descripcion': obtener_descripcion_web(mejor_coincidencia['nombre'])})
        else:
            return jsonify({'error': 'No se encontró ninguna enfermedad que coincida con los síntomas proporcionados'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
