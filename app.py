from flask import Flask, request, jsonify, render_template
import pandas as pd
import numpy as np
import random
import joblib
import os
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

app = Flask(__name__)

# Verificar si existe un modelo entrenado previamente
MODEL_FILE = "medical_model.pkl"
VECTOR_FILE = "vectorizer.pkl"

# Diccionario de tratamientos asociados a cada diagnóstico con recomendaciones detalladas
treatment_dict = {
    "gripe": "Descansar, beber líquidos, tomar analgésicos como Paracetamol o Ibuprofeno, y descongestionantes como pseudoefedrina (Sudafed) o fenilefrina.",
    "problemas gastrointestinales": "Beber líquidos (soluciones de rehidratación oral como Pedialyte), evitar alimentos irritantes como los picantes, y descansar. Si los síntomas persisten, consultar a un médico.",
    "faringitis": "Hacer gárgaras con agua salada, beber líquidos calientes como té de miel y limón, y tomar analgésicos como Paracetamol o Ibuprofeno.",
    "infeccion viral": "Descanso, hidratación adecuada, y medicamentos como Paracetamol para controlar la fiebre y el dolor.",
    "bronquitis": "Beber líquidos, usar humidificador, evitar irritantes como el humo, y descansar. Medicamentos para la tos como dextrometorfano (Robitussin) si es necesario.",
    "migraña": "Descansar en un lugar oscuro y tranquilo, usar compresas frías y tomar medicamentos como Sumatriptán (Imigran) o analgésicos como Ibuprofeno.",
    "alergia cutanea": "Aplicar cremas antihistamínicas como Benadryl, evitar el contacto con alérgenos conocidos, y tomar antihistamínicos orales como Loratadina (Claritin) o Cetirizina (Zyrtec).",
    "neumonia": "Antibióticos si es bacteriana (Amoxicilina, Azitromicina), descanso, y mantener una buena hidratación. Consultar siempre a un médico.",
    "artritis": "Tomar antiinflamatorios como Ibuprofeno o Naproxeno, aplicar calor en las articulaciones afectadas, y hacer ejercicios de bajo impacto como natación o yoga.",
    "resfriado comun": "Beber líquidos, descansar, y tomar descongestionantes como pseudoefedrina (Sudafed) o fenilefrina, y analgésicos como Paracetamol.",
    "covid-19": "Aislamiento, descanso, buena hidratación, medicación para la fiebre como Paracetamol, y seguimiento médico. En casos graves, hospitalización.",
    "gastroenteritis": "Hidratarse bien con soluciones de rehidratación oral como Pedialyte, evitar alimentos sólidos y grasosos, y, si es necesario, usar medicamentos antidiarreicos como Loperamida (Imodium).",
    "sinusitis": "Inhalar vapor, usar descongestionantes como pseudoefedrina (Sudafed), y tomar analgésicos como Ibuprofeno o Paracetamol para el dolor. Si persiste, consultar a un médico.",
    "asma": "Uso de inhaladores broncodilatadores como Salbutamol (Ventolin), evitar desencadenantes como el polvo y el humo. Si los síntomas empeoran, buscar atención médica inmediata.",
    "otitis": "Analgésicos para el dolor como Paracetamol o Ibuprofeno, y, si es necesario, antibióticos como Amoxicilina prescritos por un médico.",
    "conjuntivitis": "Aplicar compresas frías, limpiar los ojos con suero fisiológico, y en caso de infección bacteriana, usar antibióticos tópicos como tobramicina (Tobrex).",
    "amigdalitis": "Beber líquidos calientes, hacer gárgaras con agua salada, tomar analgésicos como Ibuprofeno, y usar antibióticos como Amoxicilina si es bacteriana.",
    "hipertension": "Cambios en el estilo de vida como reducción de sal en la dieta, ejercicio regular, evitar el estrés, y tomar medicación antihipertensiva como Enalapril o Losartán si es necesario.",
    "diabetes tipo 2": "Dieta equilibrada rica en fibra, ejercicio regular, monitoreo de glucosa, y medicamentos como Metformina para controlar los niveles de azúcar en sangre.",
    "anemia": "Aumentar el consumo de alimentos ricos en hierro como carne roja y vegetales de hoja verde, y tomar suplementos de hierro como Sulfato ferroso si es necesario, recetados por un médico.",
    "frio": "Abrigarse adecuadamente, consumir bebidas calientes y mantener la temperatura corporal estable. Evitar la exposición prolongada al frío y buscar abrigo.",
    "calor": "Mantenerse hidratado, usar ropa ligera y fresca, evitar la exposición directa al sol y descansar en lugares frescos. Utilizar ventiladores o aire acondicionado si es necesario.",
    "deshidratacion": "Beber abundante agua, consumir bebidas con electrolitos como las soluciones de rehidratación oral, evitar el esfuerzo físico excesivo y descansar.",
    "golpe de calor": "Buscar un lugar fresco, aplicar compresas frías en el cuerpo, beber agua lentamente y evitar la exposición al calor extremo. Si los síntomas empeoran, buscar atención médica inmediata.",
    "hipotermia": "Llevar a la persona a un ambiente cálido, quitar la ropa mojada, abrigar con mantas y proporcionar bebidas calientes si la persona está consciente. Buscar atención médica de inmediato en casos graves."
}


def generar_datos_medicos():
    """
    Genera datos médicos ficticios para entrenar el modelo.
    """
    sintomas = [
        "fiebre dolor de cabeza tos",
        "dolor abdominal diarrea",
        "dolor de garganta dificultad para tragar",
        "fiebre escalofrios sudoracion",
        "tos con flema dolor de pecho",
        "dolor de cabeza mareo nauseas",
        "erupcion cutanea picazon",
        "dolor muscular fatiga fiebre",
        "dificultad para respirar dolor en el pecho",
        "dolor en las articulaciones inflamacion",
        "fiebre congestión nasal estornudos",
        "fiebre tos seca dificultad para respirar",
        "nauseas vomitos diarrea",
        "dolor de cabeza congestion facial",
        "dificultad para respirar sibilancias opresion en el pecho",
        "dolor de oido fiebre perdida de audicion",
        "enrojecimiento picazon secrecion en los ojos",
        "dolor de garganta inflamacion de amigdalas dificultad para tragar",
        "dolor de cabeza vision borrosa mareo",
        "fatiga piel palida dificultad para concentrarse",
        "escalofrios temblor frio",
        "sudoracion excesiva calor",
        "sed boca seca deshidratacion",
        "mareo confusion golpe de calor",
        "temblor piel palida hipotermia"
    ]
    diagnosticos = [
        "gripe",
        "problemas gastrointestinales",
        "faringitis",
        "infeccion viral",
        "bronquitis",
        "migraña",
        "alergia cutanea",
        "infeccion viral",
        "neumonia",
        "artritis",
        "resfriado comun",
        "covid-19",
        "gastroenteritis",
        "sinusitis",
        "asma",
        "otitis",
        "conjuntivitis",
        "amigdalitis",
        "hipertension",
        "anemia",
        "frio",
        "calor",
        "deshidratacion",
        "golpe de calor",
        "hipotermia"
    ]
    data = {'sintomas': sintomas, 'diagnostico': diagnosticos}
    return pd.DataFrame(data)


def train_initial_model():
    # Generar datos médicos para el entrenamiento
    df = generar_datos_medicos()

    vectorizer = CountVectorizer()
    X = vectorizer.fit_transform(df['sintomas'])
    y = df['diagnostico']

    model = MultinomialNB()
    model.fit(X, y)

    # Guardar el modelo entrenado y el vectorizador
    joblib.dump(model, MODEL_FILE)
    joblib.dump(vectorizer, VECTOR_FILE)


# Cargar el modelo si existe, si no, entrenar uno inicial
if os.path.exists(MODEL_FILE) and os.path.exists(VECTOR_FILE):
    model = joblib.load(MODEL_FILE)
    vectorizer = joblib.load(VECTOR_FILE)
else:
    train_initial_model()
    model = joblib.load(MODEL_FILE)
    vectorizer = joblib.load(VECTOR_FILE)


@app.route('/', methods=['GET'])
def ui():
    return render_template('diagnosticar.html')

@app.route('/diagnosticar', methods=['POST'])
def diagnosticar():
    try:
        data = request.json if request.is_json else request.form
        sintomas = data.get('sintomas', '')

        if not sintomas:
            return jsonify({'error': 'Por favor, proporciona una lista de síntomas'}), 400

        # Transformar los síntomas con el vectorizador
        X_new = vectorizer.transform([sintomas])
        # Predecir diagnóstico
        diagnostico = model.predict(X_new)[0]
        tratamiento = treatment_dict.get(diagnostico, "Tratamiento no disponible")

        return jsonify({'diagnostico': diagnostico, 'tratamiento': tratamiento})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/entrenar', methods=['POST'])
def entrenar():
    try:
        data = request.json
        sintomas = data.get('sintomas', '')
        diagnostico = data.get('diagnostico', '')

        if not sintomas or not diagnostico:
            return jsonify({'error': 'Por favor, proporciona síntomas y diagnóstico para entrenar'}), 400

        # Transformar los síntomas con el vectorizador y entrenar el modelo
        X_new = vectorizer.transform([sintomas])
        y_new = [diagnostico]

        # Actualizar el modelo con los nuevos datos
        model.partial_fit(X_new, y_new, classes=np.unique(model.classes_))

        # Guardar el modelo actualizado
        joblib.dump(model, MODEL_FILE)

        return jsonify({'message': 'Modelo actualizado correctamente'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
