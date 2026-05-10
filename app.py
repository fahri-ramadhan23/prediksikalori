from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Bobot hasil regresi linear (dipindahkan dari frontend ke backend)
WEIGHTS = {
    'intercept': -315,
    'gender': 15.5,
    'age': -0.5,
    'weight': 4.5,
    'duration_hour': 415,
    'bpm': 2.7
}

@app.route('/')
def home():
    # Akan me-render file index.html yang ada di dalam folder 'templates'
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.json
        gender = float(data.get('gender', 0))
        age = float(data.get('age', 0))
        weight = float(data.get('weight', 0))
        duration_total_minutes = float(data.get('duration', 0))
        bpm = float(data.get('bpm', 0))

        # Konversi menit ke jam karena model dilatih menggunakan satuan jam
        duration_in_hours = duration_total_minutes / 60.0

        # Rumus prediksi Regresi Linear
        prediction = (
            WEIGHTS['intercept'] + 
            (gender * WEIGHTS['gender']) + 
            (age * WEIGHTS['age']) + 
            (weight * WEIGHTS['weight']) + 
            (duration_in_hours * WEIGHTS['duration_hour']) + 
            (bpm * WEIGHTS['bpm'])
        )

        # Menghindari kalori negatif dan membulatkan
        result = max(0, round(prediction))
        
        return jsonify({
            'status': 'success',
            'predicted_calories': result
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)
