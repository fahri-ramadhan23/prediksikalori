from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)

# Secret key untuk Flask session
app.secret_key = 'a_very_secret_key_123456'
DATABASE = 'database.db'

# Bobot hasil regresi linear (dipindahkan dari frontend ke backend)
WEIGHTS = {
    'intercept': -315,
    'gender': 15.5,
    'age': -0.5,
    'weight': 4.5,
    'duration_hour': 415,
    'bpm': 2.7
}

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        # Buat tabel users
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                fullname TEXT NOT NULL
            )
        ''')
        # Buat tabel prediction_history
        conn.execute('''
            CREATE TABLE IF NOT EXISTS prediction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                gender TEXT NOT NULL,
                age INTEGER NOT NULL,
                weight REAL NOT NULL,
                duration REAL NOT NULL,
                bpm INTEGER NOT NULL,
                predicted_calories INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.commit()

# Inisialisasi database saat aplikasi dimulai
init_db()

@app.route('/')
def home():
    # Proteksi halaman utama: jika belum login, alihkan ke login
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Ambil riwayat prediksi dari database untuk user yang sedang aktif
    conn = get_db_connection()
    history = conn.execute('''
        SELECT gender, age, weight, duration, bpm, predicted_calories, timestamp 
        FROM prediction_history 
        WHERE user_id = ? 
        ORDER BY timestamp DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()
    
    return render_template('index.html', fullname=session['fullname'], history=history)

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Jika sudah login, alihkan ke halaman utama
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    error = None
    if request.method == 'POST':
        fullname = request.form.get('fullname')
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not fullname or not username or not password or not confirm_password:
            error = "Semua field wajib diisi."
        elif password != confirm_password:
            error = "Konfirmasi password tidak cocok."
        else:
            conn = get_db_connection()
            user_exists = conn.execute('SELECT 1 FROM users WHERE username = ?', (username,)).fetchone()
            
            if user_exists:
                conn.close()
                error = "Username sudah terdaftar. Gunakan username lain."
            else:
                password_hash = generate_password_hash(password)
                try:
                    conn.execute('INSERT INTO users (username, password_hash, fullname) VALUES (?, ?, ?)',
                                 (username, password_hash, fullname))
                    conn.commit()
                    conn.close()
                    # Redirect ke login dengan indikator sukses
                    return redirect(url_for('login', registered='true'))
                except Exception as e:
                    conn.close()
                    error = f"Terjadi kesalahan: {str(e)}"
                    
    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Jika sudah login, alihkan ke halaman utama
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    error = None
    success = None
    
    # Ambil notifikasi registrasi sukses dari query parameter
    if request.args.get('registered') == 'true':
        success = "Registrasi berhasil! Silakan login."
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            error = "Username dan password wajib diisi."
        else:
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            conn.close()
            
            if user and check_password_hash(user['password_hash'], password):
                session['user_id'] = user['id']
                session['fullname'] = user['fullname']
                session['username'] = user['username']
                return redirect(url_for('home'))
            else:
                error = "Username atau password salah."
                
    return render_template('login.html', error=error, success=success)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/predict', methods=['POST'])
def predict():
    if 'user_id' not in session:
        return jsonify({
            'status': 'error',
            'message': 'Sesi telah berakhir. Silakan login kembali.'
        }), 401
        
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
        
        # Simpan ke tabel prediction_history di database
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO prediction_history (user_id, gender, age, weight, duration, bpm, predicted_calories)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'], 
            'Laki-laki' if gender == 1 else 'Perempuan', 
            int(age), 
            weight, 
            duration_total_minutes, 
            int(bpm), 
            result
        ))
        conn.commit()
        
        # Ambil timestamp dari entri yang baru dimasukkan untuk disinkronkan ke frontend
        db_row = conn.execute('SELECT timestamp FROM prediction_history WHERE user_id = ? ORDER BY id DESC LIMIT 1', (session['user_id'],)).fetchone()
        conn.close()
        
        timestamp = db_row['timestamp'] if db_row else ""
        
        return jsonify({
            'status': 'success',
            'predicted_calories': result,
            'new_entry': {
                'gender': 'Laki-laki' if gender == 1 else 'Perempuan',
                'age': int(age),
                'weight': weight,
                'duration': duration_total_minutes,
                'bpm': int(bpm),
                'predicted_calories': result,
                'timestamp': timestamp
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)
