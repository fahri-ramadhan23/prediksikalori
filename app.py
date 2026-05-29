from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)

# Secret key untuk Flask session
app.secret_key = 'a_very_secret_key_123456'
DATABASE = 'database.db'

# Mendeteksi URL Database PostgreSQL dari platform hosting seperti Railway
DATABASE_URL = os.environ.get('DATABASE_URL')

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
    if DATABASE_URL:
        # Mengimpor modul PostgreSQL secara dinamis agar tidak membebani eksekusi lokal tanpa dependensi postgres
        import psycopg2
        import psycopg2.extras
        # DictCursor memungkinkan akses baris dengan nama kolom, seperti sqlite3.Row
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
        return conn
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn

def execute_sql(conn, query, params=()):
    if DATABASE_URL:
        # Mengubah penanda parameter SQLite (?) menjadi format PostgreSQL (%s)
        query = query.replace('?', '%s')
    cur = conn.cursor()
    cur.execute(query, params)
    return cur

def init_db():
    if DATABASE_URL:
        conn = get_db_connection()
        cur = conn.cursor()
        # Membuat tabel PostgreSQL
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                fullname VARCHAR(100) NOT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS prediction_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                gender VARCHAR(20) NOT NULL,
                age INTEGER NOT NULL,
                weight REAL NOT NULL,
                duration REAL NOT NULL,
                bpm INTEGER NOT NULL,
                predicted_calories INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    else:
        # Membuat tabel SQLite
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                fullname TEXT NOT NULL
            )
        ''')
        cur.execute('''
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
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        conn.commit()
        conn.close()

# Inisialisasi database saat aplikasi dimulai
init_db()

@app.route('/')
def home():
    # Proteksi halaman utama: jika belum login, alihkan ke login
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Ambil riwayat prediksi dari database untuk user yang sedang aktif
    conn = get_db_connection()
    history_rows = execute_sql(conn, '''
        SELECT gender, age, weight, duration, bpm, predicted_calories, timestamp 
        FROM prediction_history 
        WHERE user_id = ? 
        ORDER BY timestamp DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()
    
    # Format timestamp ke string berformat standar agar aman dari error tipe data JSON/Jinja
    history = []
    for row in history_rows:
        ts = row['timestamp']
        if ts is not None and not isinstance(ts, str):
            ts_str = ts.strftime('%Y-%m-%d %H:%M:%S')
        else:
            ts_str = ts or ""
        history.append({
            'gender': row['gender'],
            'age': row['age'],
            'weight': row['weight'],
            'duration': row['duration'],
            'bpm': row['bpm'],
            'predicted_calories': row['predicted_calories'],
            'timestamp': ts_str
        })
    
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
            user_exists = execute_sql(conn, 'SELECT 1 FROM users WHERE username = ?', (username,)).fetchone()
            
            if user_exists:
                conn.close()
                error = "Username sudah terdaftar. Gunakan username lain."
            else:
                password_hash = generate_password_hash(password)
                try:
                    execute_sql(conn, 'INSERT INTO users (username, password_hash, fullname) VALUES (?, ?, ?)',
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
            user = execute_sql(conn, 'SELECT * FROM users WHERE username = ?', (username,)).fetchone()
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
        execute_sql(conn, '''
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
        db_row = execute_sql(conn, '''
            SELECT timestamp 
            FROM prediction_history 
            WHERE user_id = ? 
            ORDER BY id DESC LIMIT 1
        ''', (session['user_id'],)).fetchone()
        conn.close()
        
        ts_str = ""
        if db_row and db_row['timestamp']:
            ts = db_row['timestamp']
            if not isinstance(ts, str):
                ts_str = ts.strftime('%Y-%m-%d %H:%M:%S')
            else:
                ts_str = ts
        
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
                'timestamp': ts_str
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)
