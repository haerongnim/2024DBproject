import psycopg2
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
from functools import wraps

load_dotenv()

# 데이터베이스 설정
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

# 데이터베이스 연결 함수
def get_db_connection():
    return psycopg2.connect(
        database=DB_NAME,
        user=DB_USER ,
        password=DB_PASSWORD,
        host=DB_HOST, # 127.0.0.1 과 같음
        port=DB_PORT
    )


app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')




# 로그인 필요 데코레이터
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def home():
    role = session.get('role')
    return render_template('home.html', 
                           username=session['username'], 
                           role=role)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Person 테이블에서 사용자 확인
        cur.execute("SELECT * FROM Person WHERE email = %s", (email,))
        user = cur.fetchone()
        
        if user and check_password_hash(user[3], password):  # user[3]은 password 컬럼
            session['user_id'] = user[0]  # id
            session['username'] = user[1]  # name
            
            # 역할 확인 (Student, Professor, Villain, Muggle)
            roles = ['Student', 'Professor', 'Villain', 'Muggle']
            user_role = None
            
            for role in roles:
                cur.execute(f"SELECT * FROM {role} WHERE {role.lower()}_id = %s", (user[0],))
                if cur.fetchone():
                    user_role = role
                    break
            
            if user_role:
                session['role'] = user_role
                cur.close()
                conn.close()
                return redirect(url_for('home'))
            
        flash('잘못된 이메일 또는 비밀번호입니다.')
        cur.close()
        conn.close()
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']  # 'student', 'professor', 'villain', 'muggle' 중 하나
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # 이메일 중복 체크
            cur.execute("SELECT * FROM Person WHERE email = %s", (email,))
            if cur.fetchone():
                flash('이미 존재하는 이메일입니다.')
                return redirect(url_for('signup'))
            
            # 트랜잭션 시작
            cur.execute("BEGIN")
            
            # Person 테이블에 추가
            password_hash = generate_password_hash(password)
            cur.execute(
                "INSERT INTO Person (name, email, password) VALUES (%s, %s, %s) RETURNING id",
                (name, email, password_hash)
            )
            person_id = cur.fetchone()[0]
            
            # 역할별 테이블에 추가
            if role == 'student':
                cur.execute("INSERT INTO Student (student_id) VALUES (%s)", (person_id,))
            elif role == 'professor':
                cur.execute("INSERT INTO Professor (professor_id) VALUES (%s)", (person_id,))
            elif role == 'villain':
                cur.execute("INSERT INTO Villain (villain_id) VALUES (%s)", (person_id,))
            elif role == 'muggle':
                cur.execute("INSERT INTO Muggle (muggle_id) VALUES (%s)", (person_id,))
            
            # 트랜잭션 커밋
            conn.commit()
            flash('회원가입이 완료되었습니다. 로그인해주세요.')
            return redirect(url_for('login'))
            
        except Exception as e:
            conn.rollback()
            flash('회원가입 중 오류가 발생했습니다.')
            print(f"Error: {e}")
            return redirect(url_for('signup'))
            
        finally:
            cur.close()
            conn.close()
    
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)  # 서버 실행