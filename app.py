from flask import Flask, request, jsonify, render_template
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import os
import requests
from bs4 import BeautifulSoup
import re
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configuración de base de datos basada en el entorno
engine = None

try:
    if os.getenv("FLASK_ENV") == "production":
        # Conexión para PostgreSQL usando SQLAlchemy con pg8000
        db_url = "postgresql+pg8000://emanuel_allaria:ScwDEklhDwyHTbX0VYIqZk59WaWNjwLM@dpg-csjc9prtq21c73dbn2tg-a/consulta_medica"
    else:
        # Conexión para MySQL en desarrollo
        db_url = "mysql+mysqlconnector://root:@localhost/consulta_medica"

    # Crear el motor de conexión
    engine = create_engine(db_url)
    print("Conexión a la base de datos exitosa.")
except SQLAlchemyError as err:
    print(f"Error al conectar a la base de datos: {err}")

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

def obtener_datos_desde_bd():
    """
    Obtiene los datos de síntomas y diagnósticos desde la base de datos.
    """
    with engine.connect() as connection:
        # Consulta los datos de las enfermedades y sus restricciones
        result = connection.execute(text("""
            SELECT e.nombre, e.sintomas, r.edad_minima, r.edad_maxima, r.genero
            FROM enfermedades e
            LEFT JOIN restricciones_enfermedades r ON e.id = r.enfermedad_id
        """)).mappings()
        
        enfermedades = [
            {
                'nombre': row['nombre'],
                'sintomas': row['sintomas'].lower().split(', '),
                'edad_minima': row['edad_minima'],
                'edad_maxima': row['edad_maxima'],
                'genero': row['genero']
            }
            for row in result
        ]
    return enfermedades

def obtener_tratamiento(diagnostico):
    """
    Obtiene el tratamiento asociado a un diagnóstico desde la base de datos.
    """
    with engine.connect() as connection:
        result = connection.execute(text("SELECT tratamiento FROM enfermedades WHERE nombre = :nombre"), {'nombre': diagnostico}).mappings()
        row = result.fetchone()
        return row['tratamiento'] if row else "Tratamiento no disponible"

def obtener_lista_sintomas():
    """
    Obtiene todos los síntomas desde la tabla de síntomas.
    """
    with engine.connect() as connection:
        result = connection.execute(text("SELECT nombre FROM sintomas")).mappings()
        return [row['nombre'].lower() for row in result]

@app.route('/', methods=['GET'])
def ui():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT nombre FROM sintomas ORDER BY nombre ASC")).mappings()
        sintomas = [row['nombre'] for row in result]
    return render_template('diagnosticar.html', sintomas=sintomas)

@app.route('/diagnosticar', methods=['POST'])
def diagnosticar():
    try:
        data = request.json if request.is_json else request.form
        sintomas_usuario = data.get('sintomas', '')
        edad_usuario = int(data.get('edad', 0))
        genero_usuario = data.get('genero', '').lower()

        if not sintomas_usuario or not edad_usuario or not genero_usuario:
            return jsonify({'error': 'Por favor, proporciona una lista de síntomas, edad y género'}), 400

        lista_sintomas_usuario = sintomas_usuario.lower().split(', ')
        lista_sintomas_bd = obtener_lista_sintomas()
        sintomas_filtrados = [s for s in lista_sintomas_usuario if s in lista_sintomas_bd]

        if not sintomas_filtrados:
            return jsonify({'error': 'Ningún síntoma proporcionado coincide con nuestra base de datos'}), 400

        enfermedades = obtener_datos_desde_bd()
        mejor_coincidencia = None
        max_sintomas_encontrados = 0

        for enfermedad in enfermedades:
            sintomas_enfermedad = enfermedad['sintomas']
            sintomas_encontrados = len(set(sintomas_filtrados) & set(sintomas_enfermedad))
            
            # Verificar restricciones de edad y género en la tabla restricciones_enfermedades
            if sintomas_encontrados > max_sintomas_encontrados:
                if (
                    (enfermedad['edad_minima'] is None or edad_usuario >= enfermedad['edad_minima']) and
                    (enfermedad['edad_maxima'] is None or edad_usuario <= enfermedad['edad_maxima']) and
                    (enfermedad['genero'] == 'todos' or enfermedad['genero'] == genero_usuario)
                ):
                    max_sintomas_encontrados = sintomas_encontrados
                    mejor_coincidencia = enfermedad

        if mejor_coincidencia:
            tratamiento = obtener_tratamiento(mejor_coincidencia['nombre'])
            descripcion = obtener_descripcion_web(mejor_coincidencia['nombre'])
            return jsonify({'diagnostico': mejor_coincidencia['nombre'], 'tratamiento': tratamiento, 'descripcion': descripcion})
        else:
            return jsonify({'error': 'No se encontró ninguna enfermedad que coincida con los síntomas proporcionados'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
