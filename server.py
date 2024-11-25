import psycopg2
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
from functools import wraps
import sys
from apscheduler.schedulers.background import BackgroundScheduler
import random
import json
#from openai import OpenAI

load_dotenv()

# OpenAI 클라이언트 초기화
#client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Windows 콘솔에서 한글 출력을 위한 설정
if sys.platform == 'win32':
    import locale
    locale.setlocale(locale.LC_ALL, 'Korean_Korea.UTF-8')
    sys.stdout.reconfigure(encoding='utf-8')

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
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if role == 'Muggle':
            cur.execute("""
                SELECT heart, attack_power, money 
                FROM Muggle 
                WHERE muggle_id = %s
            """, (session['user_id'],))
            result = cur.fetchone()
            context = {
                'username': session['username'],
                'role': role,
                'heart': result[0],
                'attack_power': result[1],
                'money': result[2]
            }
        elif role in ['Student', 'Villain']:
            table_name = {'Student': 'Student', 'Villain': 'Villain'}[role]
            id_column = {'Student': 'student_id', 'Villain': 'villain_id'}[role]
            
            cur.execute(f"""
                SELECT heart, attack_power 
                FROM {table_name} 
                WHERE {id_column} = %s
            """, (session['user_id'],))
            result = cur.fetchone()
            context = {
                'username': session['username'],
                'role': role,
                'heart': result[0],
                'attack_power': result[1]
            }
        else:
            context = {
                'username': session['username'],
                'role': role
            }
        
        return render_template('home.html', **context)
    finally:
        cur.close()
        conn.close()
    

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

########################muggle#############################
# 머글 상태 조회
@app.route('/muggle/status')
@login_required
def muggle_status():
    if session.get('role') != 'Muggle':
        flash('머글만 접근할 수 있습니다.')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 머글 정보 조회
        cur.execute("""
            SELECT m.heart, m.attack_power, m.money 
            FROM Muggle m 
            WHERE m.muggle_id = %s
        """, (session['user_id'],))
        
        muggle_info = cur.fetchone()
        if not muggle_info:
            flash('머글 정보를 찾을 수 없습니다.')
            return redirect(url_for('home'))
        
        heart, attack_power, money = muggle_info
        
        return render_template('muggle/status.html', 
                             heart=heart,
                             attack_power=attack_power,
                             money=money)
                             
    finally:
        cur.close()
        conn.close()

# 물건 목록 조회
@app.route('/muggle/items')
@login_required
def view_items():
    if session.get('role') != 'Muggle':
        flash('머글만 접근할 수 있습니다.')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 현재 머글의 돈 조회
        cur.execute("""
            SELECT money 
            FROM Muggle 
            WHERE muggle_id = %s
        """, (session['user_id'],))
        
        money = cur.fetchone()[0]
        
        # 모든 물건 목록 조회
        cur.execute("""
            SELECT i.item_id, i.item_name, i.current_price,
                   CASE WHEN i.current_price <= %s THEN true ELSE false END as can_buy
            FROM Item i
            ORDER BY i.current_price
        """, (money,))
        
        items = cur.fetchall()
        
        return render_template('muggle/items.html', 
                             items=items,
                             money=money)
                             
    finally:
        cur.close()
        conn.close()

# 가격 조회 API
@app.route('/api/items/prices')
def get_item_prices():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT item_id, item_name, current_price 
            FROM Item 
            ORDER BY item_id
        """)
        items = cur.fetchall()
        return jsonify([{
            'item_id': item[0],
            'item_name': item[1],
            'price': float(item[2])
        } for item in items])
    finally:
        cur.close()
        conn.close()
# 물건 구매
@app.route('/muggle/buy_item/<int:item_id>', methods=['POST'])
@login_required
def buy_item(item_id):
    if session.get('role') != 'Muggle':
        return jsonify({'success': False, 'message': '머글만 접근할 수 있습니다.'})
    
    amount = int(request.form.get('amount', 1))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 트랜잭션 시작
        cur.execute("BEGIN")
        
        # 현재 물건 가격과 머글의 돈 확인
        cur.execute("""
            SELECT i.current_price, m.money, i.item_name
            FROM Item i, Muggle m
            WHERE i.item_id = %s AND m.muggle_id = %s
        """, (item_id, session['user_id']))
        
        result = cur.fetchone()
        if not result:
            raise Exception("물건 또는 사용자 정보를 찾을 수 없습니다.")
            
        price, money, item_name = result
        total_cost = price * amount
        
        if total_cost > money:
            raise Exception("보유 금액이 부족합니다.")
        
        # 머글의 돈 차감
        cur.execute("""
            UPDATE Muggle
            SET money = money - %s
            WHERE muggle_id = %s
        """, (total_cost, session['user_id']))
        
        # 보유 물건 추가/업데이트
        cur.execute("""
            INSERT INTO ItemOwnership (owner_id, item_id, price, amount)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (owner_id, item_id) DO UPDATE
            SET amount = ItemOwnership.amount + %s,
                price = (ItemOwnership.price * ItemOwnership.amount + %s * %s) / (ItemOwnership.amount + %s)
        """, (session['user_id'], item_id, price, amount, amount, price, amount, amount))
        
        conn.commit()
        return jsonify({
            'success': True, 
            'message': f'{item_name} {amount}개를 {price}G에 구매했습니다.'
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cur.close()
        conn.close()

# 가격 업데이트 함수
def update_item_prices():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 각 아이템의 가격을 -10%에서 +10% 사이로 랜덤하게 변동
        cur.execute("""
            UPDATE Item
            SET current_price = 
                CASE 
                    WHEN current_price * (1 + (random() * 0.2 - 0.1)) < 100 THEN 100
                    ELSE current_price * (1 + (random() * 0.2 - 0.1))
                END
            RETURNING item_id, item_name, current_price;
        """)
        
        conn.commit()
        print("가격이 업데이트되었습니다.")
    except Exception as e:
        print(f"가격 업데이트 중 오류 발생: {e}")
    finally:
        cur.close()
        conn.close()

# 기본 아이템 추가 함수
def initialize_items():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 기존 아이템이 있는지 확인
        cur.execute("SELECT COUNT(*) FROM Item")
        if cur.fetchone()[0] == 0:
            # 기본 아이템 추가
            items = [
                ('마법의 돌', 1000.00),
                ('불사조 깃털', 800.00),
                ('용의 비늘', 500.00),
                ('유니콘 뿔', 1200.00),
                ('마법 약초', 300.00)
            ]
            
            cur.executemany(
                "INSERT INTO Item (item_name, current_price) VALUES (%s, %s)",
                items
            )
            
            conn.commit()
            print("기본 아이템이 추가되었습니다.")
    finally:
        cur.close()
        conn.close()

# 보유 물건 목록 조회
@app.route('/muggle/my_items')
@login_required
def view_my_items():
    if session.get('role') != 'Muggle':
        flash('머글만 접근할 수 있습니다.')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT i.item_id, i.item_name, io.amount, io.price, i.current_price
            FROM ItemOwnership io
            JOIN Item i ON io.item_id = i.item_id
            WHERE io.owner_id = %s
        """, (session['user_id'],))
        
        items = cur.fetchall()
        return render_template('muggle/my_items.html', items=items)
    finally:
        cur.close()
        conn.close()

# 물건 판매
@app.route('/muggle/sell_item/<int:item_id>', methods=['POST'])
@login_required
def sell_item(item_id):
    if session.get('role') != 'Muggle':
        return jsonify({'success': False, 'message': '머글만 접근할 수 있습니다.'})
    
    amount = int(request.form.get('amount', 1))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("BEGIN")
        
        # 보유 물건 확인
        cur.execute("""
            SELECT io.amount, i.current_price, i.item_name
            FROM ItemOwnership io
            JOIN Item i ON io.item_id = i.item_id
            WHERE io.owner_id = %s AND io.item_id = %s
        """, (session['user_id'], item_id))
        
        result = cur.fetchone()
        if not result:
            raise Exception("보유하지 않은 물건입니다.")
            
        owned_amount, current_price, item_name = result
        
        if amount > owned_amount:
            raise Exception("보유량이 부족합니다.")
        
        total_earning = current_price * amount
        
        # 머글의 돈 증가
        cur.execute("""
            UPDATE Muggle
            SET money = money + %s
            WHERE muggle_id = %s
        """, (total_earning, session['user_id']))
        
        # 보유 물건 감소
        if amount == owned_amount:
            cur.execute("""
                DELETE FROM ItemOwnership
                WHERE owner_id = %s AND item_id = %s
            """, (session['user_id'], item_id))
        else:
            cur.execute("""
                UPDATE ItemOwnership
                SET amount = amount - %s
                WHERE owner_id = %s AND item_id = %s
            """, (amount, session['user_id'], item_id))
        
        conn.commit()
        return jsonify({
            'success': True,
            'message': f'{item_name} {amount}개를 {current_price}G에 판매했습니다.'
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cur.close()
        conn.close()

# 마법 상점 조회
@app.route('/muggle/magic_shop')
@login_required
def view_magic_shop():
    if session.get('role') != 'Muggle':
        flash('머글만 접근할 수 있습니다.')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 현재 머글의 돈 조회
        cur.execute("""
            SELECT money 
            FROM Muggle 
            WHERE muggle_id = %s
        """, (session['user_id'],))
        
        money = cur.fetchone()[0]
        
        # 구매 가능한 마법 목록 조회 (교수 이름 포함)
        cur.execute("""
            SELECT m.magic_id, m.magic_name, m.power, ms.price,
                   CASE WHEN ms.price <= %s THEN true ELSE false END as can_buy,
                   p.name as creator_name
            FROM Magic m
            JOIN MagicShop ms ON m.magic_id = ms.magic_id
            LEFT JOIN Professor pr ON m.creator_id = pr.professor_id
            LEFT JOIN Person p ON pr.professor_id = p.id
            ORDER BY ms.price
        """, (money,))
        
        magics = cur.fetchall()
        return render_template('muggle/magic_shop.html', 
                             magics=magics,
                             money=money)
    finally:
        cur.close()
        conn.close()

# 마법 구매
@app.route('/muggle/buy_magic/<int:magic_id>', methods=['POST'])
@login_required
def buy_magic(magic_id):
    if session.get('role') != 'Muggle':
        return jsonify({'success': False, 'message': '머글👤 접근할 수 있습니다.'})
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("BEGIN")
        
        # 마법 정보와 머글의 돈 확인
        cur.execute("""
            SELECT m.magic_name, m.power, ms.price, mu.money
            FROM Magic m
            JOIN MagicShop ms ON m.magic_id = ms.magic_id
            JOIN Muggle mu ON mu.muggle_id = %s
            WHERE m.magic_id = %s
        """, (session['user_id'], magic_id))
        
        result = cur.fetchone()
        if not result:
            raise Exception("마법을 찾을 수 없습니다.")
            
        magic_name, power, price, money = result
        
        if price > money:
            raise Exception("보유 금액이 부족합니다.")
        
        # 머글의 돈 차감 및 공격력 증가
        cur.execute("""
            UPDATE Muggle
            SET money = money - %s,
                attack_power = attack_power + %s
            WHERE muggle_id = %s
        """, (price, power, session['user_id']))
        
        conn.commit()
        return jsonify({
            'success': True,
            'message': f'{magic_name} 마법을 {price}G에 구매했습니다. 공격력이 {power} 증가했습니다!'
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cur.close()
        conn.close()

# 스케줄러 설정
scheduler = BackgroundScheduler()
scheduler.add_job(func=update_item_prices, trigger="interval", seconds=10)

@app.route('/buy_heart', methods=['POST'])
@login_required
def buy_heart():
    if session.get('role') == 'Professor':
        return jsonify({'success': False, 'message': '교수는 생명력을 구매할 수 없습니다.'})
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("BEGIN")
        
        # 현재 생명력과 돈/공격력 확인
        if session['role'] == 'Muggle':
            cur.execute("""
                SELECT heart, money 
                FROM Muggle 
                WHERE muggle_id = %s
            """, (session['user_id'],))
            result = cur.fetchone()
            heart, money = result
            
            if heart >= 3:
                raise Exception("최대 생명력은 3입니다.")
            if money < 1000:
                raise Exception("보유 금액이 부족합니다.")
            
            # 머글의 돈 차감 및 생명력 증가
            cur.execute("""
                UPDATE Muggle
                SET money = money - 1000,
                    heart = heart + 1
                WHERE muggle_id = %s
            """, (session['user_id'],))
            message = "생명력이 1 증가했습니다! (1000G 차감)"
            
        else:  # Student or Villain
            table_name = {'Student': 'Student', 'Villain': 'Villain'}[session['role']]
            id_column = {'Student': 'student_id', 'Villain': 'villain_id'}[session['role']]
            
            cur.execute(f"""
                SELECT heart, attack_power 
                FROM {table_name} 
                WHERE {id_column} = %s
            """, (session['user_id'],))
            result = cur.fetchone()
            heart, attack_power = result
            
            if heart >= 3:
                raise Exception("최대 생명력은 3입니다.")
            if attack_power < 5:
                raise Exception("공격력이 부족합니다.")
            
            # 공격력 차감 및 생명력 증가
            cur.execute(f"""
                UPDATE {table_name}
                SET attack_power = attack_power - 5,
                    heart = heart + 1
                WHERE {id_column} = %s
            """, (session['user_id'],))
            message = "생명력이 1 증가했습니다! (공격력 5 차감)"
        
        conn.commit()
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cur.close()
        conn.close()

@app.route('/villain/games')
@login_required
def villain_games():
    if session.get('role') != 'Villain':
        flash('빌런만 접근할 수 있습니다.')
        return redirect(url_for('home'))
    return render_template('villain/games.html')

@app.route('/villain/rock_paper_scissors')
@login_required
def rock_paper_scissors():
    if session.get('role') != 'Villain':
        flash('빌런만 접근할 수 있습니다.')
        return redirect(url_for('home'))
    return render_template('villain/rock_paper_scissors.html')

@app.route('/villain/play_rps', methods=['POST'])
@login_required
def play_rps():
    if session.get('role') != 'Villain':
        return jsonify({'success': False, 'message': '빌런만 플레이할 수 있습니다.'})
    
    data = request.get_json()
    player_choice = data.get('choice')
    computer_choice = random.choice(['rock', 'scissors', 'paper'])
    
    # 승패 결정 (미리 정의된 딕셔너리 사용)
    RESULTS = {
        'rock': {'rock': ('무승부!', False), 'scissors': ('승리!', True), 'paper': ('패배!', False)},
        'scissors': {'rock': ('패배!', False), 'scissors': ('무승부!', False), 'paper': ('승리!', True)},
        'paper': {'rock': ('승리!', True), 'scissors': ('패배!', False), 'paper': ('무승부!', False)}
    }
    
    EMOJIS = {'rock': '✊', 'scissors': '✌️', 'paper': '✋'}
    
    result, is_win = RESULTS[player_choice][computer_choice]
    message = f"당신의 선택: {EMOJIS[player_choice]}<br>컴퓨터의 선택: {EMOJIS[computer_choice]}<br>{result}"
    
    if is_win:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE Villain
                SET attack_power = attack_power + 3
                WHERE villain_id = %s
                RETURNING attack_power
            """, (session['user_id'],))
            conn.commit()
            return jsonify({'success': True, 'message': message})
        finally:
            cur.close()
            conn.close()
    
    return jsonify({'success': False, 'message': message})

@app.route('/villain/number_baseball')
@login_required
def number_baseball():
    if session.get('role') != 'Villain':
        flash('빌런만 접근할 수 있습니다.')
        return redirect(url_for('home'))
    return render_template('villain/number_baseball.html')

@app.route('/villain/complete_baseball', methods=['POST'])
@login_required
def complete_baseball():
    if session.get('role') != 'Villain':
        return jsonify({'success': False, 'message': '빌런만 플레이할 수 있습니다.'})
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE Villain
            SET attack_power = attack_power + 5
            WHERE villain_id = %s
            RETURNING attack_power
        """, (session['user_id'],))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()

# 퀴즈 데이터베이스
QUIZ_DATABASE = [
    {
        "question": "태양계에서 가장 큰 행성은?",
        "options": ["화성", "목성", "토성", "금성"],
        "correct_answer": 1
    },
    {
        "question": "물의 화학식은?",
        "options": ["CO2", "H2O", "O2", "NH3"],
        "correct_answer": 1
    },
    {
        "question": "세계에서 가장 긴 강은?",
        "options": ["나일강", "아마존강", "양쯔강", "미시시피강"],
        "correct_answer": 0
    },
    {
        "question": "인간의 정상 체온은?",
        "options": ["35.5도", "36.5도", "37.5도", "38.5도"],
        "correct_answer": 1
    },
    {
        "question": "지구에서 가장 큰 대륙은?",
        "options": ["북아메리카", "남아메리카", "아프리카", "아시아"],
        "correct_answer": 3
    }
]


def generate_quiz():
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "system",
                "content": """상식 퀴즈를 생성해주세요. 
                다음 형식의 JSON으로 응답해주세요:
                {
                    "question": "퀴즈 질문",
                    "options": ["보기1", "보기2", "보기3", "보기4"],
                    "correct_answer": 정답의인덱스(0-3),
                    "explanation": "정답에 대한 설명"
                }
                
                퀴즈는 일반상식, 과학, 역사, 문화 등 다양한 분야에서 출제해주세요.
                난이도는 중간 정도로 해주세요."""
            }],
            temperature=0.7
        )
        
        # API 응답에서 JSON 추출
        quiz_data = json.loads(response.choices[0].message.content)
        return quiz_data
        
    except Exception as e:
        print(f"퀴즈 생성 중 오류 발생: {e}")
        # 오류 발생 시 기본 퀴즈 반환
        return {
            "question": "태양계에서 가장 큰 행성은?",
            "options": ["화성", "목성", "토성", "금성"],
            "correct_answer": 1,
            "explanation": "목성은 태양계에서 가장 큰 행성입니다."
        }

@app.route('/villain/quiz_game')
@login_required
def quiz_game():
    if session.get('role') != 'Villain':
        flash('빌런만 접근할 수 있습니다.')
        return redirect(url_for('home'))
    
    quiz = random.choice(QUIZ_DATABASE)
    return render_template('villain/quiz_game.html', quiz_data=quiz)

@app.route('/villain/complete_quiz', methods=['POST'])
@login_required
def complete_quiz():
    if session.get('role') != 'Villain':
        return jsonify({'success': False, 'message': '빌런만 플레이할 수 있습니다.'})
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE Villain
            SET attack_power = attack_power + 7
            WHERE villain_id = %s
            RETURNING attack_power
        """, (session['user_id'],))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()

@app.route('/battle_list')
@login_required
def battle_list():
    if session.get('role') not in ['Student', 'Villain', 'Muggle']:
        flash('전투에 참여할 수 없는 역할입니다.')
        return redirect(url_for('home'))
    
    role_filter = request.args.get('role', 'all')
    sort_by = request.args.get('sort', 'name_asc')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 기본 쿼리 구성
        query = """
            SELECT p.id, p.name, 
                   CASE 
                       WHEN m.muggle_id IS NOT NULL THEN 'Muggle'
                       WHEN s.student_id IS NOT NULL THEN 'Student'
                       WHEN v.villain_id IS NOT NULL THEN 'Villain'
                   END as role
            FROM Person p
            LEFT JOIN Muggle m ON p.id = m.muggle_id
            LEFT JOIN Student s ON p.id = s.student_id
            LEFT JOIN Villain v ON p.id = v.villain_id
            WHERE p.id != %s
        """
        params = [session['user_id']]
        
        # 현재 사용자의 역할 제외
        query += """ AND CASE 
                      WHEN m.muggle_id IS NOT NULL THEN 'Muggle'
                      WHEN s.student_id IS NOT NULL THEN 'Student'
                      WHEN v.villain_id IS NOT NULL THEN 'Villain'
                   END != %s"""
        params.append(session['role'])
        
        # 역할 필터 적용
        if role_filter != 'all':
            query += """ AND CASE 
                          WHEN m.muggle_id IS NOT NULL THEN 'Muggle'
                          WHEN s.student_id IS NOT NULL THEN 'Student'
                          WHEN v.villain_id IS NOT NULL THEN 'Villain'
                       END = %s"""
            params.append(role_filter)
        
        # 정렬 적용
        sort_mapping = {
            'name_asc': 'p.name ASC',
            'name_desc': 'p.name DESC',
            'role_asc': 'role ASC',
            'role_desc': 'role DESC'
        }
        query += f" ORDER BY {sort_mapping.get(sort_by, 'p.name ASC')}"
        
        cur.execute(query, params)
        opponents = [{'id': row[0], 'name': row[1], 'role': row[2]} 
                    for row in cur.fetchall()]
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'opponents': opponents})
        
        return render_template('battle_list.html', 
                             opponents=opponents,
                             current_role=session['role'])
    finally:
        cur.close()
        conn.close()

@app.route('/battle', methods=['POST'])
@login_required
def battle():
    data = request.get_json()
    opponent_id = data.get('opponent_id')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("BEGIN")
        
        # 현재 사용자의 공격력과 생명력 조회
        if session['role'] == 'Muggle':
            cur.execute("""
                SELECT attack_power, heart 
                FROM Muggle 
                WHERE muggle_id = %s
            """, (session['user_id'],))
        elif session['role'] == 'Student':
            cur.execute("""
                SELECT attack_power, heart 
                FROM Student 
                WHERE student_id = %s
            """, (session['user_id'],))
        else:  # Villain
            cur.execute("""
                SELECT attack_power, heart 
                FROM Villain 
                WHERE villain_id = %s
            """, (session['user_id'],))
        
        player_stats = cur.fetchone()
        if not player_stats:
            raise Exception("사용자 정보를 찾을 수 없습니다.")
        
        player_attack, player_heart = player_stats
        
        # 상대방의 공격력 조회
        cur.execute("""
            SELECT 
                CASE 
                    WHEN m.muggle_id IS NOT NULL THEN m.attack_power
                    WHEN s.student_id IS NOT NULL THEN s.attack_power
                    WHEN v.villain_id IS NOT NULL THEN v.attack_power
                END as attack_power,
                CASE 
                    WHEN m.muggle_id IS NOT NULL THEN 'Muggle'
                    WHEN s.student_id IS NOT NULL THEN 'Student'
                    WHEN v.villain_id IS NOT NULL THEN 'Villain'
                END as role
            FROM Person p
            LEFT JOIN Muggle m ON p.id = m.muggle_id
            LEFT JOIN Student s ON p.id = s.student_id
            LEFT JOIN Villain v ON p.id = v.villain_id
            WHERE p.id = %s
        """, (opponent_id,))
        
        opponent_stats = cur.fetchone()
        if not opponent_stats:
            raise Exception("상대방 정보를 찾을 수 없습니다.")
        
        opponent_attack, opponent_role = opponent_stats
        
        # 전투 결과 처리
        if player_attack > opponent_attack:
            # 승리: 공격력 증가
            attack_increase = 2
            if session['role'] == 'Muggle':
                cur.execute("""
                    UPDATE Muggle
                    SET attack_power = attack_power + %s
                    WHERE muggle_id = %s
                """, (attack_increase, session['user_id']))
            elif session['role'] == 'Student':
                cur.execute("""
                    UPDATE Student
                    SET attack_power = attack_power + %s
                    WHERE student_id = %s
                """, (attack_increase, session['user_id']))
            else:  # Villain
                cur.execute("""
                    UPDATE Villain
                    SET attack_power = attack_power + %s
                    WHERE villain_id = %s
                """, (attack_increase, session['user_id']))
            
            message = f"승리! 공격력이 {attack_increase} 증가했습니다."
            
        elif player_attack < opponent_attack:
            # 패배: 생명력 감소
            if player_heart <= 1:
                raise Exception("생명력이 부족하여 전투할 수 없습니다.")
            
            if session['role'] == 'Muggle':
                cur.execute("""
                    UPDATE Muggle
                    SET heart = heart - 1
                    WHERE muggle_id = %s
                """, (session['user_id'],))
            elif session['role'] == 'Student':
                cur.execute("""
                    UPDATE Student
                    SET heart = heart - 1
                    WHERE student_id = %s
                """, (session['user_id'],))
            else:  # Villain
                cur.execute("""
                    UPDATE Villain
                    SET heart = heart - 1
                    WHERE villain_id = %s
                """, (session['user_id'],))
            
            message = "패배... 생명력이 1 감소했습니다."
            
        else:
            message = "무승부입니다!"
        
        conn.commit()
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    scheduler.start()
    #initialize_items()  # 서버 시작 시 기본 아이템 추가
    app.run(debug=True, host='0.0.0.0', port=5000)  # 서버 실행