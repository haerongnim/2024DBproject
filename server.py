# 필요한 라이브러리 임포트
import psycopg2 # PostgreSQL 데이터베이스 연결
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash   # 비밀번호 암호화/검증
import os
from dotenv import load_dotenv
from functools import wraps
import sys
from apscheduler.schedulers.background import BackgroundScheduler   # 주기적 작업 실행용(물건 가격 변화)
import random   # 게임 로직용 난수 생성


# .env 파일에서 환경 변수를 로드
load_dotenv()

# Flask 애플리케이션 인스턴스 생성
app = Flask(__name__)

# 환경 변수에서 비밀키를 가져와 Flask 앱의 시크릿 키로 설정
app.secret_key = os.getenv('SECRET_KEY')    # 세션 데이터 암호화에 사용되는 키

# Windows 환경에서 한글 출력을 위한 설정
if sys.platform == 'win32':    # Windows 운영체제인 경우
    import locale
    # 한국어 로케일 설정
    locale.setlocale(locale.LC_ALL, 'Korean_Korea.UTF-8')
    # 표준 출력 인코딩을 UTF-8로 설정
    sys.stdout.reconfigure(encoding='utf-8')

# 데이터베이스 연결 정보를 환경 변수에서 가져옴
DB_NAME = os.getenv('DB_NAME')          # 데이터베이스 이름
DB_USER = os.getenv('DB_USER')          # 데이터베이스 사용자
DB_PASSWORD = os.getenv('DB_PASSWORD')   # 데이터베이스 비밀번호
DB_HOST = os.getenv('DB_HOST', 'localhost')  # 호스트 주소(기본값: localhost)
DB_PORT = os.getenv('DB_PORT', '5432')      # 포트 번호(기본값: 5432)

# PostgreSQL 데이터베이스 연결을 생성하는 함수
def get_db_connection():
    """
    PostgreSQL 데이터베이스 연결을 생성하고 반환하는 함수
    환경변수에 저장된 연결 정보를 사용하여 데이터베이스에 연결
    Returns:
        psycopg2.connection: 데이터베이스 연결 객체
    """
    return psycopg2.connect(
        database=DB_NAME,      # 데이터베이스 이름
        user=DB_USER,          # 사용자 이름
        password=DB_PASSWORD,   # 비밀번호
        host=DB_HOST,          # 호스트 주소 (127.0.0.1과 동일)
        port=DB_PORT,          # 포트 번호
    )


# 로그인 필수 데코레이터 - 비로그인 사용자 접근 제한
def login_required(f):
    """
    로그인이 필요한 라우트에 적용되는 데코레이터
    비로그인 사용자의 접근을 제한하고 로그인 페이지로 리다이렉트
    """
    @wraps(f)  # 원본 함수의 메타데이터 보존
    def decorated_function(*args, **kwargs):
        # 세션에 user_id가 없으면 (로그인하지 않은 상태)
        if 'user_id' not in session:
            # 로그인 페이지로 리다이렉트
            return redirect(url_for('login'))
        # 로그인된 상태면 원래 함수 실행
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'Admin':
            return jsonify({'error': '관리자 권한이 필요합니다.'}), 403
        return f(*args, **kwargs)
    return decorated_function

# 회원가입 처리
@app.route('/signup', methods=['GET', 'POST'])  # '/signup' URL에 대한 GET, POST 요청 처리
def signup():
    """
    회원가입 처리 로직:
    1. POST 요청 시 사용자 정보 검증
    2. 이메일 중복 체크
    3. 비밀번호 해싱
    4. Person 테이블에 기본 정보 저장
    5. 선택한 역할(Student/Professor/Villain/Muggle)에 따라 해당 테이블에도 정보 저장
    6. 트랜잭션 처리로 데이터 일관성 보장
    """
    # POST 요청인 경우 회원가입 처리
    if request.method == 'POST':
        # 폼에서 입력받은 데이터 가져오기
        name = request.form['name']  # 이름
        email = request.form['email']  # 이메일
        password = request.form['password']  # 비밀번호
        role = request.form['role']  # 역할(student/professor/villain/muggle)
        
        # 데이터베이스 연결 생성
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # 이메일 중복 체크
            cur.execute("SELECT * FROM Person WHERE email = %s", (email,))
            if cur.fetchone():  # 이미 존재하는 이메일이면
                flash('이미 존재하는 이메일입니다.')  # 에러 메시지 표시
                return redirect(url_for('signup'))  # 회원가입 페이지로 리다이렉트
            
            # 트랜잭션 시작
            cur.execute("BEGIN")
            
            # Person 테이블에 사용자 정보 추가
            password_hash = generate_password_hash(password)  # 비밀번호 해싱
            cur.execute(
                "INSERT INTO Person (name, email, password) VALUES (%s, %s, %s) RETURNING id",
                (name, email, password_hash)
            )
            person_id = cur.fetchone()[0]  # 생성된 사용자의 ID 가져오기
            
            # 선택한 역할에 따라 해당 테이블에 추가
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
            flash('회원가입이 완료되었습니다. 로그인해주세요.')  # 성공 메시지 표시
            return redirect(url_for('login'))  # 로그인 페이지로 리다이렉트
            
        except Exception as e:  # 오류 발생 시
            conn.rollback()  # 트랜잭션 롤백
            flash('회원가입 중 오류가 발생했습니다.')  # 에러 메시지 표시
            print(f"Error: {e}")  # 오류 내용 출력
            return redirect(url_for('signup'))  # 회원가입 페이지로 리다이렉트
            
        finally:  # 항상 실행
            cur.close()  # 커서 닫기
            conn.close()  # 데이터베이스 연결 종료
    
    # GET 요청인 경우 회원가입 페이지 표시
    return render_template('signup.html')

# 로그인 기능을 처리하는 라우트 핸들러
@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    로그인 처리 로직:
    1. POST 요청으로 이메일/비밀번호 받음
    2. Person 테이블에서 이메일로 사용자 검색
    3. 비밀번호 해시 검증
    4. 역할 테이블 검사하여 사용자 유형 확인
    5. 세션에 사용자 정보 저장
    """
    # POST 요청인 경우 로그인 처리
    if request.method == 'POST':
        # 폼에서 이메일과 비밀번호 가져오기
        email = request.form['email']
        password = request.form['password']
        
        # 데이터베이스 연결 생성
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Person 테이블에서 입력된 이메일로 사용자 정보 조회
            cur.execute("SELECT * FROM Person WHERE email = %s", (email,))
            user = cur.fetchone()
            
            # 사용자가 존재하고 비밀번호가 일치하는 경우
            if user and check_password_hash(user[3], password):  # user[3]은 password 컬럼
                # 세션에 사용자 ID와 이름 저장
                session['user_id'] = user[0]  # id
                session['username'] = user[1]  # name
                
                # 역할 확�
                cur.execute("SELECT * FROM Admin WHERE admin_id = %s", (user[0],))
                if cur.fetchone():
                    session['role'] = 'Admin'
                    return redirect(url_for('home'))
                    
                # 사용자의 역할 확인을 위한 역할 목록
                roles = ['Student', 'Professor', 'Villain', 'Muggle']
                user_role = None
                
                # 각 역할 테이블을 확인하여 사용자의 역할 찾기
                for role in roles:
                    cur.execute(f"SELECT * FROM {role} WHERE {role.lower()}_id = %s", (user[0],))
                    if cur.fetchone():
                        user_role = role
                        break
                
                # 역할이 확인된 경우
                if user_role:
                    # 세션에 역할 저장하고 홈 화면으로 리다이렉트
                    session['role'] = user_role
                    cur.close()
                    conn.close()
                    return redirect(url_for('home'))
            
            # 로그인 실패 시 에러 메시지 표시
            flash('잘못된 이메일 또는 비밀번호입니다.')
            cur.close()
            conn.close()
            return redirect(url_for('login'))
            
        finally:
            cur.close()
            conn.close()
            
    # GET 요청이거나 로그인 실패 시 로그인 페이지 표시
    return render_template('login.html')

# 로그아웃 처리 라우트 핸들러
@app.route('/logout')
def logout():
    # 세션 데이터 모두 삭제
    session.clear()
    # 로그인 페이지로 리다이렉트
    return redirect(url_for('login'))

############################# 홈 화면 #############################
@app.route('/')  # 루트 URL에 대한 라우트 핸들러
@login_required  # 로그인이 필요한 페이지임을 명시하는 데코레이터
def home():
    """
    홈 화면 처리 로직:
    1. 사용자 역할에 따라 다른 정보 표시
    2. Muggle: 생명력, 공격력, 보유금액 표시
    3. Student/Villain: 생명력, 공격력 표시
    4. Professor: 기본 정보만 표시
    5. 데이터베이스 오류 시 세션 클리어 및 재로그인 요청
    """
    role = session.get('role')  # 세션에서 사용자 역할 가져오기
    conn = get_db_connection()  # 데이터베이스 연결 생성
    cur = conn.cursor()  # 커서 생성
    
    try:
        if role == 'Muggle':  # 머글인 경우
            # 머글의 생명력, 공격력, 보유금액 조회
            cur.execute("""
                SELECT heart, attack_power, money 
                FROM Muggle 
                WHERE muggle_id = %s
            """, (session['user_id'],))
            result = cur.fetchone()  # 조회 결과 가져오기
            if result is None:  # 결과가 없는 경우
                session.clear()  # 세션 데이터 불일치로 인해 세션 클리어
                flash('데이터베이스 오류가 발생했습니다. 다시 로그인해주세요.')
                return redirect(url_for('login'))  # 로그인 페이지로 리다이렉트
            context = {  # 템플릿에 전달할 컨텍스트 데이터 구성
                'username': session['username'],
                'role': role,
                'heart': result[0],
                'attack_power': result[1],
                'money': result[2]
            }
        elif role in ['Student', 'Villain']:  # 학생이나 빌런인 경우
            # 테이블명과 ID 컬럼명 매핑
            table_name = {'Student': 'Student', 'Villain': 'Villain'}[role]
            id_column = {'Student': 'student_id', 'Villain': 'villain_id'}[role]
            
            # 생명력과 공격력 조회
            cur.execute(f"""
                SELECT heart, attack_power 
                FROM {table_name} 
                WHERE {id_column} = %s
            """, (session['user_id'],))
            result = cur.fetchone()  # 조회 결과 가져오기
            if result is None:  # 결과가 없는 경우
                session.clear()  # 세션 데이터 불일치로 인해 세션 클리어
                flash('데이터베이스 오류가 발생했습니다. 다시 로그인해주세요.')
                return redirect(url_for('login'))  # 로그인 페이지로 리다이렉트
            context = {  # 템플릿에 전달할 컨텍스트 데이터 구성
                'username': session['username'],
                'role': role,
                'heart': result[0],
                'attack_power': result[1]
            }
        else:  # 교수인 경우
            context = {  # 기본 정보만 포함하는 컨텍스트 데이터 구성
                'username': session['username'],
                'role': role
            }
        
        return render_template('home.html', **context)  # 홈 화면 템플릿 렌더링
    finally:
        cur.close()  # 커서 닫기
        conn.close()  # 데이터베이스 연결 종료


##### 생명력 구매 기능 #####
@app.route('/buy_heart', methods=['POST'])  # '/buy_heart' URL에 대한 POST 요청 처리
@login_required  # 로그인이 필요한 기능임을 명시하는 데코레이터
def buy_heart():
    # 교수는 생명력을 구매할 수 없음
    if session.get('role') == 'Professor':
        return jsonify({'success': False, 'message': '교수는 생명력을 구매할 수 없습니다.'})
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("BEGIN")  # 트랜잭션 시작
        
        # 현재 생명력과 돈/공격력 확인
        if session['role'] == 'Muggle':  # 머글인 경우
            # 머글의 현재 생명력과 보유 금액 조회
            cur.execute("""
                SELECT heart, money 
                FROM Muggle 
                WHERE muggle_id = %s
            """, (session['user_id'],))
            result = cur.fetchone()
            heart, money = result
            
            # 생명력이 3 이상이면 구매 불가
            if heart >= 3:
                raise Exception("최대 생명력은 3입니다.")
            # 보유 금액이 1000 미만이면 구매 불가    
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
            
        else:  # 학생 또는 빌런인 경우
            # 테이블명과 ID 컬럼명 매핑
            table_name = {'Student': 'Student', 'Villain': 'Villain'}[session['role']]
            id_column = {'Student': 'student_id', 'Villain': 'villain_id'}[session['role']]
            
            # 현재 생명력과 공격력 조회
            cur.execute(f"""
                SELECT heart, attack_power 
                FROM {table_name} 
                WHERE {id_column} = %s
            """, (session['user_id'],))
            result = cur.fetchone()
            heart, attack_power = result
            
            # 생명력이 3 이상이면 구매 불가
            if heart >= 3:
                raise Exception("최대 생명력은 3입니다.")
            # 공격력이 5 미만이면 구매 불가    
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
        
        conn.commit()  # 트랜잭션 커밋
        return jsonify({  # 성공 응답 반환
            'success': True,
            'message': message
        })
        
    except Exception as e:  # 오류 발생 시
        conn.rollback()  # 트랜잭션 롤백
        return jsonify({'success': False, 'message': str(e)})  # 실패 응답 반환
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()
        conn.close()

############################# 머글 #############################

##### 물건 거래소 #####
# 머글이 구매할 수 있는 모든 아이템 목록을 보여주는 라우트 핸들러
@app.route('/muggle/items')  # '/muggle/items' URL에 대한 라우트 정의
@login_required  # 로그인이 필요한 페이지임을 명시하는 데코레이터
def view_items():
    # 현재 세션의 role이 Muggle이 아닌 경우 접근 제한
    if session.get('role') != 'Muggle':
        flash('머글만 접근할 수 있습니다.')  # 에러 메시지를 플래시 메시지로 설정
        return redirect(url_for('home'))  # 홈페이지로 리다이렉트
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()  # DB 연결 객체 생성
    cur = conn.cursor()  # DB 커서 생성
    
    try:
        # 현재 로그인한 머글의 보유 금액을 조회하는 쿼리 실행
        cur.execute("""
            SELECT money 
            FROM Muggle 
            WHERE muggle_id = %s
        """, (session['user_id'],))  # 현재 사용자의 ID로 조회
        
        # 조회 결과에서 보유 금액 추출
        money = cur.fetchone()[0]  # 첫 번째 컬럼(money) 값 가져오기
        
        # 모든 아이템 목록을 조회하고 각 아이템의 구매 가능 여부를 계산하는 쿼리 실행
        cur.execute("""
            SELECT i.item_id,           -- 아이템 ID
                   i.item_name,         -- 아이템 이름
                   i.current_price,     -- 현재 가격
                   CASE WHEN i.current_price <= %s THEN true ELSE false END as can_buy  -- 구매 가능 여부
            FROM Item i
            ORDER BY i.current_price    -- 가격순으로 정렬
        """, (money,))  # 현재 보유 금액을 파라미터로 전달
        
        # 조회 결과 저장
        items = cur.fetchall()  # 모든 아이템 정보를 리스트로 가져오기
        
        # items.html 템플릿을 렌더링하여 응답 반환
        return render_template('muggle/items.html',  # 템플릿 파일 지정
                             items=items,  # 아이템 목록 전달
                             money=money)  # 보유 금액 전달
                             
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()  # 커서 닫기
        conn.close()  # 연결 종료

# 실시간 아이템 가격 정보를 제공하는 API 엔드포인트
# 실시간 아이템 가격 정보를 제공하는 API 엔드포인트 
@app.route('/api/items/prices')  # '/api/items/prices' URL에 대한 라우트 정의
def get_item_prices():  # 아이템 가격 정보를 가져오는 함수
    # 데이터베이스 연결 생성
    conn = get_db_connection()  # DB 연결 객체 생성
    cur = conn.cursor()  # DB 커서 생성
    
    try:
        # 모든 아이템의 현재 가격 정보를 조회하는 쿼리 실행
        cur.execute("""
            SELECT item_id, item_name, current_price  --- 아이템 ID, 이름, 현재 가격 조회
            FROM Item  --- Item 테이블에서
            ORDER BY item_id  --- 아이템 ID 기준으로 정렬
        """)
        items = cur.fetchall()  # 모든 아이템 정보를 리스트로 가져오기
        
        # 조회 결과를 JSON 형식으로 변환하여 반환
        return jsonify([{
            'item_id': item[0],  # 아이템 ID
            'item_name': item[1],  # 아이템 이름 
            'price': float(item[2])  # 가격(decimal을 float으로 변환)
        } for item in items])  # 리스트 컴프리헨션으로 딕셔너리 리스트 생성
        
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()  # 커서 닫기
        conn.close()  # 연결 종료

# 물건 구매 처리 라우트
@app.route('/muggle/buy_item/<int:item_id>', methods=['POST'])  # 물건 구매를 처리하는 POST 라우트, item_id를 URL 파라미터로 받음
@login_required  # 로그인이 필요한 기능임을 명시
def buy_item(item_id):
    # 머글 권한 체크 - 머글이 아닌 경우 에러 반환
    if session.get('role') != 'Muggle':
        return jsonify({'success': False, 'message': '머글만 접근할 수 있습니다.'})
    
    # 구매할 수량을 폼 데이터에서 가져옴 (기본값: 1)
    amount = int(request.form.get('amount', 1))
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 트랜잭션 시작 - 데이터 일관성을 위해
        cur.execute("BEGIN")
        
        # 아이템의 현재 가격, 머글의 보유금액, 아이템 이름을 조회
        cur.execute("""
            SELECT i.current_price, m.money, i.item_name  -- 아이템 가격, 머글 보유금액, 아이템 이름 조회
            FROM Item i, Muggle m  -- Item과 Muggle 테이블 조인
            WHERE i.item_id = %s   -- 특정 아이템 ID 조건
            AND m.muggle_id = %s   -- 특정 머글 ID 조건
        """, (item_id, session['user_id']))
        
        # 조회 결과 확인
        result = cur.fetchone()
        if not result:
            raise Exception("물건 또는 사용자 정보를 을 수 없습니다.")
            
        # 조회 결과에서 필요한 정보 추출
        price, money, item_name = result
        total_cost = price * amount  # 총 구매 비용 계산
        
        # 보유금액이 부족한 경우 에러 발생
        if total_cost > money:
            raise Exception("보유 금액이 부족합니다.")
        
        # 머글의 보유금액에서 구매 비용 차감
        cur.execute("""
            UPDATE Muggle  -- Muggle 테이블 업데이트
            SET money = money - %s  -- 보유금액에서 구매비용 차감
            WHERE muggle_id = %s    -- 특정 머글 ID 조건
        """, (total_cost, session['user_id']))
        
        # 보유 물건 추가/업데이트
        # UPSERT 구문: 이미 보유 중이면 수량과 평균 구매가격 업데이트, 없으면 새로 추가
        cur.execute("""
            INSERT INTO ItemOwnership (owner_id, item_id, price, amount)  -- 새로운 소유 정보 추가
            VALUES (%s, %s, %s, %s)  -- 소유자ID, 아이템ID, 가격, 수량 입력
            ON CONFLICT (owner_id, item_id) DO UPDATE  -- 이미 존재하는 경우 업데이트
            SET amount = ItemOwnership.amount + %s,  -- 기존 수량에 구매 수량 추가
                price = (ItemOwnership.price * ItemOwnership.amount + %s * %s) / (ItemOwnership.amount + %s)  -- 평균 구매가격 재계산
        """, (session['user_id'], item_id, price, amount, amount, price, amount, amount))
        # 트랜잭션 커밋 - 모든 변경사항 저장
        conn.commit()
        # 성공 응답 반환
        return jsonify({
            'success': True, 
            'message': f'{item_name} {amount}개를 {price}G에 구매했습니다.'
        })
        
    except Exception as e:
        # 오류 발생 시 트랜잭션 롤백
        conn.rollback()
        # 에러 메시지 반환
        return jsonify({'success': False, 'message': str(e)})
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()
        conn.close()

# 주기적으로 아이템 가격을 업데이트하는 함수
def update_item_prices():
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    # 커서 생성
    cur = conn.cursor()
    
    try:
        # 각 아이템의 가격을 -10%에서 +10% 사이로 랜덤하게 변동
        # 단, 최저가는 100G로 제한
        cur.execute("""
            -- Item 테이블의 current_price 컬럼을 업데이트
            UPDATE Item
            SET current_price = 
                CASE 
                    -- 가격이 100G 미만이 되는 경우 100G로 고정
                    WHEN current_price * (1 + (random() * 0.2 - 0.1)) < 100 THEN 100
                    -- 그 외의 경우 현재 가격의 ±10% 범위 내에서 랜덤하게 변동
                    -- random() * 0.2는 0~0.2 사이의 난수 생성
                    -- 0.1을 빼서 -0.1~0.1 사이의 값으로 변환 (즉, ±10%)
                    ELSE current_price * (1 + (random() * 0.2 - 0.1))
                END
            -- 업데이트된 아이템의 정보를 반환
            RETURNING item_id, item_name, current_price;
        """)
        
        # 트랜잭션 커밋 - 변경사항 저장
        conn.commit()
        # 업데이트 완료 메시지 출력
        print("가격이 업데이트되었습니다.")
    except Exception as e:
        # 오류 발생 시 에러 메시지 출력
        print(f"가격 업데이트 중 오류 발생: {e}")
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()
        conn.close()

# 백그라운드 스케줄러 설정
# APScheduler 라이브러리를 사용하여 주기적인 작업 실행을 위한 스케줄러 생성
scheduler = BackgroundScheduler()
# update_item_prices 함수를 5초마다 실행하도록 작업 추가
scheduler.add_job(func=update_item_prices, trigger="interval", seconds=5)

# 초기 아이템 데이터를 설정하는 함수
def initialize_items():
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    # 커서 객체 생성
    cur = conn.cursor()
    
    try:
        # Item 테이블의 전체 레코드 수를 조회하는 쿼리 실행
        # SELECT COUNT(*) - 테이블의 전체 레코드 수를 반환
        # FROM Item - Item 테이블에서 조회
        cur.execute("SELECT COUNT(*) FROM Item")
        
        # 테이블이 비어있는 경우에만 초기 데이터 추가
        if cur.fetchone()[0] == 0:
            # 기본 아이템 목록 정의 - (아이템명, 가격) 형태의 튜플 리스트
            items = [
                ('마법의 돌', 1000.00),  # 가격: 1000G
                ('불사조 깃털', 800.00),  # 가격: 800G
                ('용의 비늘', 500.00),    # 가격: 500G
                ('유니콘 뿔', 1200.00),   # 가격: 1200G
                ('마법 약초', 300.00)     # 가격: 300G
            ]
            
            # 기본 아이템들을 Item 테이블에 일괄 추가
            # INSERT INTO Item - Item 테이블에 데이터 삽입
            # (item_name, current_price) - 삽입할 컬럼명
            # VALUES (%s, %s) - 각 컬럼에 대한 값을 파라미터로 전달
            cur.executemany(
                "INSERT INTO Item (item_name, current_price) VALUES (%s, %s)",
                items
            )
            
            # 변경사항을 데이터베이스에 반영
            conn.commit()
            # 초기화 완료 메시지 출력
            print("기본 아이템이 추가되었습니다.")
    finally:
        # 데이터베이스 리소스 정리
        cur.close()  # 커서 닫기
        conn.close() # 연결 종료

# 보유 물건 목록 조회 라우트
@app.route('/muggle/my_items')  # '/muggle/my_items' URL에 대한 라우트 핸들러 정의
@login_required  # 로그인이 필요한 페이지임을 명시하는 데코레이터
def view_my_items():
    # 머글 권한 체크 - 현재 세션의 role이 'Muggle'이 아닌 경우 접근 제한
    if session.get('role') != 'Muggle':
        flash('머글만 접근할 수 있습니다.')  # 에러 메시지를 플래시 메시지로 설정
        return redirect(url_for('home'))  # 홈 페이지로 리다이렉트
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    # 커서 객체 생성
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT i.item_id, i.item_name, io.amount, io.price, i.current_price --- 아이템 ID, 이름, 보유수량, 구매가격, 현재가격을 조회
            FROM ItemOwnership io --- ItemOwnership 테이블을 기준으로
            JOIN Item i ON io.item_id = i.item_id --- Item 테이블과 조인하여 아이템 정보 가져오기
            WHERE io.owner_id = %s --- 현재 사용자가 소유한 아이템만 필터링
        """, (session['user_id'],))
        
        # 조회 결과를 변수에 저장
        items = cur.fetchall()
        # 보유 물건 목록 페이지 템플릿 렌더링
        return render_template('muggle/my_items.html', items=items)
    finally:
        # 데이터베이스 리소스 정리
        cur.close()  # 커서 닫기
        conn.close()  # 연결 종료

# 물건 판매 처리 라우트 - 머글이 보유한 아이템을 판매하는 기능
@app.route('/muggle/sell_item/<int:item_id>', methods=['POST'])  # POST 요청으로 item_id를 받아 처리
@login_required  # 로그인 필수
def sell_item(item_id):
    # 머글 권한 체크 - 머글이 아닌 경우 접근 제한
    if session.get('role') != 'Muggle':
        return jsonify({'success': False, 'message': '머글만 접근할 수 있습니다.'})
    
    # 판매할 수량을 폼 데이터에서 가져옴 (기본값: 1)
    amount = int(request.form.get('amount', 1))
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("BEGIN")  # 트랜잭션 시작
        
        # 보유 물건 정보 확인 쿼리
        # ItemOwnership과 Item 테이블을 조인하여 보유량, 현재가격, 아이템명 조회
        # owner_id와 item_id로 특정 사용자의 특정 아이템 정보를 필터링
        cur.execute("""
            SELECT io.amount, i.current_price, i.item_name
            FROM ItemOwnership io
            JOIN Item i ON io.item_id = i.item_id
            WHERE io.owner_id = %s AND io.item_id = %s
        """, (session['user_id'], item_id))
        
        # 조회 결과 확인
        result = cur.fetchone()
        if not result:
            raise Exception("보유하지 않은 물건입니다.")
            
        # 조회 결과에서 각 값 추출
        owned_amount, current_price, item_name = result
        
        # 판매 수량이 보유량보다 많은지 체크
        if amount > owned_amount:
            raise Exception("보유량이 부족합니다.")
        
        # 총 판매 수�� 계산
        total_earning = current_price * amount
        
        # 머글의 보유금액 증가 쿼리
        # 판매 수익만큼 money 필드를 증가
        cur.execute("""
            UPDATE Muggle
            SET money = money + %s
            WHERE muggle_id = %s
        """, (total_earning, session['user_id']))
        
        # 보유 물건 수량 조정
        if amount == owned_amount:
            # 전량 판매시 - ItemOwnership 테이블에서 해당 레코드 삭제
            cur.execute("""
                DELETE FROM ItemOwnership
                WHERE owner_id = %s AND item_id = %s
            """, (session['user_id'], item_id))
        else:
            # 일부 판매시 - amount 필드 �����소
            cur.execute("""
                UPDATE ItemOwnership
                SET amount = amount - %s
                WHERE owner_id = %s AND item_id = %s
            """, (amount, session['user_id'], item_id))
        
        # 트랜잭션 커밋
        conn.commit()
        # 성공 응답 반환
        return jsonify({
            'success': True,
            'message': f'{item_name} {amount}개를 {current_price}G에 판매했습니다.'
        })
        
    except Exception as e:
        conn.rollback()  # 오류 발생시 롤백
        return jsonify({'success': False, 'message': str(e)})  # 오류 메시지 반환
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()  # 커서 닫기
        conn.close()  # 연결 종료

# 마법 상점 조회 라우트 - 머글이 구매할 수 있는 마법들의 목록을 보여주는 페이지
@app.route('/muggle/magic_shop')  # '/muggle/magic_shop' URL에 대한 라우트 핸들러
@login_required  # 로그인이 필요한 페이지임을 명시
def view_magic_shop():
    # 머글 권한 체크 - 머글이 아닌 사용자의 접근을 제한
    if session.get('role') != 'Muggle':
        flash('머글만 접근할 수 있습니다.')  # 에러 메시지를 플래시 메시지로 표시
        return redirect(url_for('home'))  # 홈페이지로 리다이렉트
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 현재 머글의 보유금액 조회 쿼리
        # Muggle 테이블에서 현재 로그인한 사용자의 money 필드를 조회
        cur.execute("""
            SELECT money 
            FROM Muggle 
            WHERE muggle_id = %s
        """, (session['user_id'],))
        
        money = cur.fetchone()[0]  # 조회된 보유금액을 변수에 저장
        
        # 판매중인 마법 목록 조회 쿼리
        # Magic, MagicShop, Professor, Person 테이블을 조인하여
        # 마법 정보, 가격, 구매 가능 여부, 제작자(교수) 정보를 함께 조회
        cur.execute("""
            SELECT m.magic_id,           -- 마법 ID
                   m.magic_name,         -- 마법 이름
                   m.power,              -- 마법 공격력
                   ms.price,             -- 마법 가격
                   CASE WHEN ms.price <= %s THEN true ELSE false END as can_buy,  -- 구매 가능 여부
                   p.name as creator_name  -- 제작자(교수) 이름
            FROM Magic m
            JOIN MagicShop ms ON m.magic_id = ms.magic_id  -- 마법과 상점 정보 조인
            LEFT JOIN Professor pr ON m.creator_id = pr.professor_id  -- 제작자 정보 조인
            LEFT JOIN Person p ON pr.professor_id = p.id  -- 제작자의 개인정보 조인
            ORDER BY ms.price  -- 가격 순으로 정렬
        """, (money,))
        
        magics = cur.fetchall()  # 조회된 마법 목록을 변수에 저장
        # 마법 상점 페이지 템플릿을 렌더링하여 반환
        # 마법 목록과 현재 보유금액 정보를 템플릿에 전달
        return render_template('muggle/magic_shop.html', 
                             magics=magics,
                             money=money)
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()  # 커서 닫기
        conn.close()  # 연결 종료

# 마법 구매 처리 라우트 - 머글이 마법을 구매할 수 있는 엔드포인트
@app.route('/muggle/buy_magic/<int:magic_id>', methods=['POST'])
@login_required  # 로그인 필요 데코레이터
def buy_magic(magic_id):
    # 머글 권한 체크 - 머글이 아닌 경우 에러 반환
    if session.get('role') != 'Muggle':
        return jsonify({'success': False, 'message': '머글만 접근할 수 있습니다.'})
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("BEGIN")  # 트랜잭션 시작
        
        # 마법 정보와 머글의 보유금액 확인을 위한 쿼리
        # - Magic 테이블: 마법 이름과 공격력 조회
        # - MagicShop 테이블: 마법 가격 조회
        # - Muggle 테이블: 현재 머글의 보유금액 조회
        cur.execute("""
            SELECT m.magic_name, m.power, ms.price, mu.money
            FROM Magic m
            JOIN MagicShop ms ON m.magic_id = ms.magic_id  -- 마법과 상점 정보 조인
            JOIN Muggle mu ON mu.muggle_id = %s  -- 현재 머글 정보 조인
            WHERE m.magic_id = %s  -- 구매하려는 마법 ID로 필터링
        """, (session['user_id'], magic_id))
        
        # 조회 결과 확인
        result = cur.fetchone()
        if not result:
            raise Exception("마법을 찾을 수 없습니다.")
            
        # 조회된 정보 변수에 저장
        magic_name, power, price, money = result
        
        # 보유금액이 마법 가격보다 적은 경우 에러 발생
        if price > money:
            raise Exception("보유 금액이 부족합니다.")
        
        # 머글의 보유금액 차감 및 공격력 증가를 위한 쿼리
        # - money: 현재 보유금액에서 마법 가격만큼 차감
        # - attack_power: 현재 공격력에 마법의 공격력만큼 증가
        cur.execute("""
            UPDATE Muggle
            SET money = money - %s,  -- 보유금액 차감
                attack_power = attack_power + %s  -- 공격력 증가
            WHERE muggle_id = %s  -- 현재 머글 ID로 필터링
        """, (price, power, session['user_id']))
        
        conn.commit()  # 트랜잭션 커밋
        # 성공 응답 반환 - 구매 완료 메시지 포함
        return jsonify({
            'success': True,
            'message': f'{magic_name} 마법을 {price}G에 구매했습니다. 공격력이 {power} 증가했습니다!'
        })
        
    except Exception as e:
        conn.rollback()  # 오류 발생 시 롤백
        return jsonify({'success': False, 'message': str(e)})  # 에러 메시지 반환
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()  # 커서 닫기
        conn.close()  # 연결 종료



############################# 빌런 #############################
##### 빌런 게임 조회 #####
@app.route('/villain/games')  # '/villain/games' URL에 대한 라우트 핸들러 정의
@login_required  # 로그인이 필요한 페이지임을 명시하는 데코레이터
def villain_games():
    # 빌런 권한 체크 - 현재 세션의 role이 'Villain'이 아닌 경우
    if session.get('role') != 'Villain':
        flash('빌런만 접근할 수 있습니다.')  # 에러 메시지를 플래시 메시지로 설정
        return redirect(url_for('home'))  # 홈페이지로 리다이렉트
    
    # PostgreSQL 데이터베이스 연결 객체 생성
    conn = get_db_connection()
    # 데이터베이스 작업을 위한 커서 객체 생성
    cur = conn.cursor()
    
    try:
        # Game 테이블에서 게임 정보를 조회하는 SQL 쿼리
        # game_name: 게임 이름
        # game_description: 게임 설명
        # difficulty: 게임 난이도
        # reward: 게임 보상
        # route_name: 게임 라우트 이름
        # ORDER BY difficulty: 난이도 순으로 정렬
        cur.execute("""
            SELECT game_name, game_description, difficulty, reward, route_name 
            FROM Game 
            ORDER BY difficulty
        """)
        
        # fetchall()로 가져온 각 행을 딕셔너리로 변환
        # zip()으로 컬럼명과 값을 매핑하여 딕셔너리 생성
        games = [dict(zip(['game_name', 'game_description', 'difficulty', 'reward', 'route_name'], row)) 
                for row in cur.fetchall()]
                
        # villain/games.html 템플릿을 렌더링하며 games 데이터를 전달
        return render_template('villain/games.html', games=games)
        
    finally:
        # 데이터베이스 리소스 정리
        cur.close()  # 커서 객체 닫기
        conn.close()  # 데이터베이스 연결 종료

##### 가위바위보 게임화면으로 이동 #####
@app.route('/villain/rock_paper_scissors')  # 가위바위보 게임 화면 URL 라우트 정의
@login_required  # 로그인이 필요한 페이지임을 명시하는 데코레이터
def rock_paper_scissors():
    # 빌런 권한 체크 - 현재 세션의 role이 'Villain'이 아닌 경우 접근 제한
    if session.get('role') != 'Villain':
        flash('빌런만 접근할 수 있습니다.')  # 에러 메시지를 플래시 메시지로 설정
        return redirect(url_for('home'))  # 홈페이지로 리다이렉트
    # 가위바위보 게임 화면 템플릿 렌더링하여 반환
    return render_template('villain/rock_paper_scissors.html')

##### 가위바위보 게임 플레이 #####
@app.route('/villain/play_rps', methods=['POST'])  # 가위바위보 게임 플레이 처리 POST 라우트
@login_required  # 로그인 필요
def play_rps():
    # 빌런 권한 체크 - 빌런이 아닌 경우 에러 반환
    if session.get('role') != 'Villain':
        return jsonify({'success': False, 'message': '빌런만 플레이할 수 있습니다.'})
    
    # 클라이언트로부터 받은 JSON 데이터에서 플레이어의 선택 추출
    data = request.get_json()
    player_choice = data.get('choice')
    # 컴퓨터의 선택을 무작위로 생성 (rock, scissors, paper 중 하나)
    computer_choice = random.choice(['rock', 'scissors', 'paper'])
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 트랜잭션 시작
        cur.execute("BEGIN")
        
        # Game 테이블에서 가위바위보 게임의 ID를 조회하는 쿼리
        # route_name이 'rock_paper_scissors'인 게임의 game_id를 가져옴
        cur.execute("""
            SELECT game_id FROM Game WHERE route_name = 'rock_paper_scissors'
        """)
        game_id = cur.fetchone()[0]  # 조회된 game_id 저장
        
        # 승패 결정을 위한 규칙을 딕셔너리로 정의
        # (결과 메시지, 승리 여부)를 값으로 가짐
        RESULTS = {
            'rock': {'rock': ('무승부!', False), 'scissors': ('승리!', True), 'paper': ('패배!', False)},
            'scissors': {'rock': ('패배!', False), 'scissors': ('무승부!', False), 'paper': ('승리!', True)},
            'paper': {'rock': ('승리!', True), 'scissors': ('패배!', False), 'paper': ('무승부!', False)}
        }
        
        # 선택에 대한 이모지 매핑 딕셔너리
        EMOJIS = {'rock': '✊', 'scissors': '✌️', 'paper': '✋'}
        
        # 게임 결과 판정 - 플레이어와 컴퓨터의 선택으로 결과 결정
        result, is_win = RESULTS[player_choice][computer_choice]
        # HTML 형식의 결과 메시지 생성
        message = f"당신의 선택: {EMOJIS[player_choice]}<br>컴퓨터의 선택: {EMOJIS[computer_choice]}<br>{result}"
        
        # GameAttempt 테이블에 게임 시도 기록을 저장하는 쿼리
        # game_id, villain_id, result(승리 여부) 저장
        cur.execute("""
            INSERT INTO GameAttempt (game_id, villain_id, result)
            VALUES (%s, %s, %s)
        """, (game_id, session['user_id'], is_win))
        
        # 승리한 경우 빌런의 공격력을 3 증가시키는 쿼리
        if is_win:
            cur.execute("""
                UPDATE Villain
                SET attack_power = attack_power + 3
                WHERE villain_id = %s
            """, (session['user_id'],))
        
        # 트랜잭션 커밋 - 모든 데이터베이스 변경사항 반영
        conn.commit()
        return jsonify({'success': True, 'message': message})  # 성공 응답 반환
        
    except Exception as e:
        # 오류 발생 시 트랜잭션 롤백
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})  # 에러 메시지 반환
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()  # 커서 닫기
        conn.close()  # 연결 종료

##### 숫자야구 게임화면으로 이동 #####
@app.route('/villain/number_baseball')  # '/villain/number_baseball' URL에 대한 라우트 핸들러 정의
@login_required  # 로그인이 필요한 페이지임을 명시하는 데코레이터
def number_baseball():
    # 빌런 권한 체크 - 현재 세션의 role이 'Villain'이 아닌 경우 접근 제한
    if session.get('role') != 'Villain':
        flash('빌런만 접근할 수 있습니다.')  # 에러 메시지를 플래시 메시지로 설정
        return redirect(url_for('home'))  # 홈페이지로 리다이렉트
    # 숫자야구 게임 화면 템플릿 렌더링하여 반환
    return render_template('villain/number_baseball.html')

##### 숫자야구 게임 플레이 #####
@app.route('/villain/complete_baseball', methods=['POST'])  # '/villain/complete_baseball' URL에 대한 POST 요청 처리
@login_required  # 로그인이 필요한 기능임을 명시하는 데코레이터
def complete_baseball():
    # 빌런 권한 체크 - 현재 세션의 role이 'Villain'이 아닌 경우 접근 제한
    if session.get('role') != 'Villain':
        return jsonify({'success': False, 'message': '빌런만 플레이할 수 있습니다.'})
    
    # 클라이언트로부터 받은 게임 결과 데이터 추출
    data = request.get_json()
    is_win = data.get('result', False)  # 승리 여부 (기본값: False)
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 트랜잭션 시작
        cur.execute("BEGIN")
        
        # 숫자야구 게임의 ID를 Game 테이블에서 조회
        # route_name이 'number_baseball'인 게임의 game_id를 가져옴
        cur.execute("""
            SELECT game_id 
            FROM Game 
            WHERE route_name = 'number_baseball'
        """)
        game_id = cur.fetchone()[0]  # 조회된 game_id 저장
        
        # 게임 시도 기록을 GameAttempt 테이블에 저장
        # game_id, villain_id, result(승리 여부) 저장
        cur.execute("""
            INSERT INTO GameAttempt (game_id, villain_id, result)
            VALUES (%s, %s, %s)
        """, (game_id, session['user_id'], is_win))
        
        # 승리한 경우 빌런의 공격력을 5 증가시키는 쿼리
        if is_win:
            cur.execute("""
                UPDATE Villain
                SET attack_power = attack_power + 5
                WHERE villain_id = %s
            """, (session['user_id'],))
        
        # 트랜잭션 커밋 - 모든 데이터베이스 변경사항 반영
        conn.commit()
        return jsonify({'success': True})  # 성공 응답 반환
        
    except Exception as e:
        # 오류 발생 시 트랜잭션 롤백
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})  # 에러 메시지 반환
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()  # 커서 닫기
        conn.close()  # 연결 종료

# 퀴즈 데이터베이스 - 퀴즈 문제, 보기, 정답을 담은 리스트
QUIZ_DATABASE = [
    {
        "question": "태양계에서 가장 큰 행성은?",
        "options": ["화성", "목성", "토성", "금성"],
        "correct_answer": 1  # 목성이 정답 (인덱스 1)
    },
    {
        "question": "물의 화학식은?",
        "options": ["CO2", "H2O", "O2", "NH3"],
        "correct_answer": 1  # H2O가 정답 (인덱스 1)
    },
    {
        "question": "세계에 가장 긴 강은?",
        "options": ["나일강", "아마존강", "양쯔강", "미시시피강"],
        "correct_answer": 0  # 나일강이 정답 (인덱스 0)
    },
    {
        "question": "인간의 정상 체온은?",
        "options": ["35.5도", "36.5도", "37.5도", "38.5도"],
        "correct_answer": 1  # 36.5도가 정답 (인덱스 1)
    },
    {
        "question": "지구에서 가장 큰 대륙은?",
        "options": ["북아메리카", "남아메리카", "아프리카", "아시아"],
        "correct_answer": 3  # 아시아가 정답 (인덱스 3)
    }
]

##### 퀴즈 게임화면으로 이동 #####
@app.route('/villain/quiz_game')  # 퀴즈 게임 화면을 보여주는 라우트
@login_required  # 로그인이 필요한 페이지임을 나타내는 데코레이터
def quiz_game():
    # 빌런 권한 체크 - 현재 세션의 role이 Villain이 아니면 접근 제한
    if session.get('role') != 'Villain':
        flash('빌런만 접근할 수 있습니다.')  # 에러 메시지를 플래시 메시지로 설정
        return redirect(url_for('home'))  # 홈페이지로 리다이렉트
    
    # 퀴즈 데이터베이스에서 무작위로 하나의 퀴즈 선택
    quiz = random.choice(QUIZ_DATABASE)
    # 선택된 퀴즈와 함께 퀴즈 게임 화면 템플릿 렌더링하여 반환
    return render_template('villain/quiz_game.html', quiz_data=quiz)

##### 퀴즈 게임 플레이 #####
@app.route('/villain/complete_quiz', methods=['POST'])  # 퀴즈 완료 처리를 위한 POST 라우트
@login_required  # 로그인이 필요한 페이지임을 나타내는 데코레이터
def complete_quiz():
    # 빌런 권한 체크 - 현재 세션의 role이 Villain이 아니면 접근 제한
    if session.get('role') != 'Villain':
        return jsonify({'success': False, 'message': '빌런만 플레이할 수 있습니다.'})
    
    # 클라이언트로부터 받은 퀴즈 결과 데이터 파싱
    data = request.get_json()
    is_correct = data.get('result', False)  # 퀴즈 정답 여부
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 트랜잭션 시작
        cur.execute("BEGIN")
        
        # 퀴즈 게임의 ID를 Game 테이블에서 조회하는 쿼리
        # Game 테이블에서 route_name이 'quiz_game'인 게임의 game_id를 선택
        cur.execute("""
            SELECT game_id FROM Game WHERE route_name = 'quiz_game'
        """)
        game_id = cur.fetchone()[0]
        
        # 게임 시도 기록을 GameAttempt 테이블에 저장하는 쿼리
        # game_id, villain_id, 결과를 GameAttempt 테이블에 삽입
        cur.execute("""
            INSERT INTO GameAttempt (game_id, villain_id, result)
            VALUES (%s, %s, %s)
        """, (game_id, session['user_id'], is_correct))
        
        # 정답을 맞춘 경우 공격력 7 증가시키는 쿼리
        # Villain 테이블에서 해당 villain_id를 가진 빌런의 attack_power를 7 증가
        if is_correct:
            cur.execute("""
                UPDATE Villain
                SET attack_power = attack_power + 7
                WHERE villain_id = %s
            """, (session['user_id'],))
        
        # 트랜잭션 커밋 - 모든 데이터베이스 변경사항 반영
        conn.commit()
        return jsonify({'success': True})  # 성공 응답 반환
        
    except Exception as e:
        # 오류 발생 시 롤백 - 모든 변경사항 취소
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})  # 에러 메시지 반환
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()  # 커서 닫기
        conn.close()  # 연결 종료

##### 게임 시도 목록 조회 #####
@app.route('/villain/game_history')
@login_required
def view_game_history():
    # 빌런 권한 체크
    if session.get('role') != 'Villain':
        flash('빌런만 접근할 수 있습니다.')
        return redirect(url_for('home'))
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 각 게임별 시도 횟수, 승리 횟수, 마지막 시도 시간을 조회
        cur.execute("""
            SELECT g.game_name, 
                   COUNT(*) as total_attempts,
                   SUM(CASE WHEN ga.result = true THEN 1 ELSE 0 END) as wins,
                   MAX(ga.attempt_time) as last_attempt
            FROM Game g
            JOIN GameAttempt ga ON g.game_id = ga.game_id
            WHERE ga.villain_id = %s
            GROUP BY g.game_name
            ORDER BY last_attempt DESC
        """, (session['user_id'],))
        
        # 게임 기록을 가져와서 게임 기록 화면 템플릿 렌더링
        game_history = cur.fetchall()
        return render_template('villain/game_history.html', game_history=game_history)
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()
        conn.close()

######################## 학생 #############################
##### 강의 목록 조회 #####
@app.route('/student/courses')  # '/student/courses' URL에 대한 라우트 핸들러 정의
@login_required  # 로그인이 필요한 페이지임을 명시하는 데코레이터
def view_courses():
    # 현재 세션의 role이 Student가 아닌 경우 접근 제한
    if session.get('role') != 'Student':
        flash('학생만 접근할 수 있습니다.')  # 에러 메시지를 플래시 메시지로 설정
        return redirect(url_for('home'))  # 홈페이지로 리다이렉트
    
    # URL 파라미터에서 정렬 기준을 가져옴. 기본값은 'magic_name_asc'
    sort_by = request.args.get('sort', 'magic_name_asc')
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 강의 목록을 조회하는 SQL 쿼리 작성
        # Magic, Course, Professor, Person 테이블을 조인하여 필요한 정보를 가져옴
        # LEFT JOIN으로 Enrollment 테이블과 연결하여 현재 학생의 수강신청 여부도 확인
        query = """
            SELECT 
                m.magic_id,              -- 마법 ID
                m.magic_name,            -- 마법 이름
                p.name as professor_name, -- 교수 이름
                c.capacity,              -- 수강 정원
                c.current_enrollment,     -- 현재 수강 인원
                c.opening_status,         -- 수강신청 가능 여부
                CASE WHEN e.student_id IS NOT NULL THEN true ELSE false END as is_enrolled  -- 현재 학생의 수강신청 여부
            FROM Magic m                 -- Magic 테이블을 기준으로
            JOIN Course c ON m.magic_id = c.course_id           -- Course 테이블과 조인
            JOIN Professor pr ON c.instructor_id = pr.professor_id  -- Professor 테이블과 조인
            JOIN Person p ON pr.professor_id = p.id             -- Person 테이블과 조인
            LEFT JOIN Enrollment e ON m.magic_id = e.course_id AND e.student_id = %s  -- Enrollment 테이블과 LEFT JOIN
        """
        
        # 정렬 조건을 매핑하는 딕셔너리 정의
        sort_mapping = {
            'magic_name_asc': 'magic_name ASC',  # 마법 이름 오름차순
            'magic_name_desc': 'magic_name DESC',  # 마법 이름 내림차순
            'professor_asc': 'professor_name ASC',  # 교수 이름 오름차순
            'professor_desc': 'professor_name DESC',  # 교수 이름 내림차순
            'capacity_asc': 'capacity ASC',  # 수강 정원 오름차순
            'capacity_desc': 'capacity DESC'  # 수강 정원 내림차순
        }
        # 선택된 정렬 조건을 쿼리에 추가 (없으면 기본값으로 magic_name ASC 사용)
        query += f" ORDER BY {sort_mapping.get(sort_by, 'magic_name ASC')}"
        
        # 쿼리 실행 (현재 로그인한 학생의 ID를 파라미터로 전달)
        cur.execute(query, (session['user_id'],))
        # 쿼리 결과를 가져옴
        courses = cur.fetchall()
        
        # 강의 목록 페이지 템플릿을 렌더링하여 반환
        # courses: 조회된 강의 목록
        # sort_by: 현재 적용된 정렬 기준
        return render_template('student/courses.html', 
                             courses=courses,
                             sort_by=sort_by)
    finally:
        # 데이터베이스 커서와 연결 종료
        cur.close()
        conn.close()

##### 강의 수강신청 #####
@app.route('/student/enroll/<int:magic_id>', methods=['POST'])  # 수강신청을 처리하는 POST 라우트
@login_required  # 로그인 필요
def enroll_course(magic_id):
    # 학생 권한 체크 - 현재 세션의 role이 'Student'가 아닌 경우 접근 제한
    if session.get('role') != 'Student':
        return jsonify({'success': False, 'message': '학생만 수강신청할 수 있습니다.'})
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 트랜잭션 시작 - 데이터 일관성을 위해 트랜잭션으로 묶음
        cur.execute("BEGIN")
        
        # 해당 강의의 수강 가능 여부 확인
        # Course 테이블에서 수강정원, 현재 수강인원, 수강신청 가능상태를 조회
        cur.execute("""
            SELECT c.capacity,            -- 수강 정원
                   c.current_enrollment,  -- 현재 수강 인원
                   c.opening_status       -- 수강신청 가능 여부
            FROM Course c
            WHERE c.course_id = %s        -- 특정 강의 ID로 필터링
        """, (magic_id,))
        
        # 강의 정보 조회 결과 확인
        course_info = cur.fetchone()
        if not course_info:  # 강의가 존재하지 않는 경우 예외 발생
            raise Exception("강의를 찾을 수 없습니다.")
        
        # 조회된 강의 정보를 각 변수에 할당
        capacity, current_enrollment, opening_status = course_info
        
        # 수강신청 가능 여부 검증
        if not opening_status:  # 수강신청이 마감된 경우
            raise Exception("수강신청이 마감된 강의입니다.")
        
        if current_enrollment >= capacity:  # 수강 정원이 초과된 경우
            raise Exception("수강 정원이 초과되었습니다.")
        
        # 수강신청 정보를 Enrollment 테이블에 삽입
        # course_id와 student_id를 이용해 수강 관계 생성
        cur.execute("""
            INSERT INTO Enrollment (course_id, student_id)  -- 수강신청 테이블에 데이터 삽입
            VALUES (%s, %s)                                -- 강의ID와 학생ID 입력
        """, (magic_id, session['user_id']))
        
        # 현재 수강 인원 증가 및 수강신청 상태 업데이트
        # 수강인원이 정원에 도달하면 수강신청 상태를 false로 변경
        cur.execute("""
            UPDATE Course
            SET current_enrollment = current_enrollment + 1,  -- 현재 수강인원 1 증가
                opening_status = CASE                        -- 수강신청 가능 상태 조건부 업데이트
                    WHEN current_enrollment + 1 >= capacity THEN false  -- 정원 도달시 false
                    ELSE true                                          -- 그 외에는 true
                END
            WHERE course_id = %s                            -- 특정 강의 ID로 필터링
        """, (magic_id,))
        
        # 트랜잭션 커밋 - 모든 데이터베이스 변경사항 반영
        conn.commit()
        return jsonify({'success': True, 'message': '수강신청이 완료되었습니다.'})
        
    except Exception as e:
        # 오류 발생 시 롤백 - 모든 변경사항을 취소하고 이전 상태로 복구
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()  # 커서 닫기
        conn.close()  # 연결 종료

##### N행시 제출 #####
@app.route('/student/submit_nsentence/<int:magic_id>', methods=['POST'])  # N행시 제출을 처리하는 POST 라우트
@login_required  # 로그인 필요
def submit_nsentence(magic_id):
    # 학생 권한 체크 - 현재 세션의 role이 'Student'가 아닌 경우 접근 제한
    if session.get('role') != 'Student':
        return jsonify({'success': False, 'message': '학생만 N행시를 제출할 수 있습니다.'})
    
    # POST 요청의 폼 데이터에서 N행시 내용 추출
    content = request.form.get('content')
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 트랜잭션 시작 - 데이터 일관성을 위해 트랜잭션으로 묶음
        cur.execute("BEGIN")
        
        # 수강 여부와 기존 N행시 점수 확인 쿼리
        # Enrollment 테이블과 Magic_NSentence 테이블을 LEFT JOIN하여
        # 해당 학생이 해당 마법 강의를 수강하는지와 기존 N행시 점수가 있는지 확인
        cur.execute("""
            SELECT mn.score 
            FROM Enrollment e
            LEFT JOIN Magic_NSentence mn ON e.course_id = mn.magic_id AND e.student_id = mn.student_id
            WHERE e.course_id = %s AND e.student_id = %s
        """, (magic_id, session['user_id']))
        
        # 조회 결과 확인
        result = cur.fetchone()
        if not result:  # 수강 중이 아닌 경우 예외 발생
            raise Exception("수강 중인 강의가 아닙니다.")
        
        if result[0] is not None:  # 이미 점수가 매겨진 경우 예외 발생
            raise Exception("이미 평가된 N행시는 수정할 수 없습니다.")
        
        # N행시 제출 또는 수정을 위한 UPSERT 쿼리
        # 해당 magic_id와 student_id 조합이 없으면 INSERT
        # 있으면 UPDATE하되, 점수가 NULL인 경우에만 업데이트
        cur.execute("""
            INSERT INTO Magic_NSentence (magic_id, student_id, content)
            VALUES (%s, %s, %s)
            ON CONFLICT (magic_id, student_id) 
            DO UPDATE SET content = EXCLUDED.content
            WHERE Magic_NSentence.score IS NULL
        """, (magic_id, session['user_id'], content))
        
        # 트랜잭션 커밋 - 모든 변경사항을 데이터베이스에 반영
        conn.commit()
        return jsonify({'success': True, 'message': 'N행시가 제출되었습니다.'})
        
    except Exception as e:
        # 오류 발생 시 롤백 - 모든 변경사항을 취소하고 이전 상태로 복구
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()  # 커서 닫기
        conn.close()  # 연결 종료

##### 내 강의 목록 조회 #####
@app.route('/student/my_courses')  # 내 강의 목록을 조회하는 라우트
@login_required  # 로그인 필요
def view_my_courses():
    # 학생 권한 체크 - 현재 세션의 role이 'Student'가 아닌 경우 접근 제한
    if session.get('role') != 'Student':
        flash('학생만 접근할 수 있습니다.')  # 에러 메시지를 플래시 메시지로 설정
        return redirect(url_for('home'))  # 홈페이지로 리다이렉트
    
    # URL 파라미터에서 정렬 기준을 가져옴 (기본값: magic_name_asc)
    sort_by = request.args.get('sort', 'magic_name_asc')
    
    # 정렬 조건 매핑 딕셔너리 - 각 정렬 옵션에 대한 SQL ORDER BY 절 정의
    sort_conditions = {
        'magic_name_asc': 'm.magic_name ASC',  # 마법 이름 오름차순
        'magic_name_desc': 'm.magic_name DESC',  # 마법 이름 내림차순
        'professor_asc': 'p.name ASC',  # 교수 이름 오름차순
        'professor_desc': 'p.name DESC',  # 교수 이름 내림차순
        'score_asc': 'COALESCE(mn.score, -1) ASC',  # 점수 오름차순 (NULL은 -1로 처리)
        'score_desc': 'COALESCE(mn.score, -1) DESC'  # 점수 내림차순 (NULL은 -1로 처리)
    }
    
    # 선택된 정렬 조건 가져오기 (없으면 기본값 사용)
    order_by = sort_conditions.get(sort_by, 'm.magic_name ASC')
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 수강 중인 강의 목록 조회 쿼리
        # SELECT: 필요한 정보들을 선택
        #   - magic_id: 마법 ID
        #   - magic_name: 마법 이름
        #   - power: 마법 공격력
        #   - professor_name: 교수 이름
        #   - nsentence: N행시 내용
        #   - score: N행시 점수
        #   - grade: 점수에 따른 학점(A,B,C,D,F) 계산
        # FROM: Enrollment 테이블을 기준으로
        # JOIN: 필요한 테이블들과 조인
        #   - Magic: 마법 정보
        #   - Course: 강의 정보
        #   - Professor: 교수 정보
        #   - Person: 개인 정보
        #   - Magic_NSentence: N행시 정보 (LEFT JOIN으로 없는 경우도 포함)
        # WHERE: 현재 로그인한 학생의 강의만 필터링
        # ORDER BY: 선택된 정렬 조건으로 정렬
        cur.execute("""
            SELECT 
                m.magic_id,           --- 마법 ID
                m.magic_name,         --- 마법 이름
                m.power as attack_power,  --- 마법 공격력
                p.name AS professor_name, --- 교수 이름
                mn.content AS nsentence,  --- N행시 내용
                mn.score,                 --- N행시 점수
                CASE 
                    WHEN mn.score >= 90 THEN 'A'  --- 90점 이상 A
                    WHEN mn.score >= 80 THEN 'B'  --- 80점 이상 B
                    WHEN mn.score >= 70 THEN 'C'  --- 70점 이상 C
                    WHEN mn.score >= 60 THEN 'D'  --- 60점 이상 D
                    WHEN mn.score IS NOT NULL THEN 'F'  --- 60점 미만 F
                    ELSE NULL                          --- 점수가 없으면 NULL
                END AS grade
            FROM Enrollment e                          --- 수강신청 테이블
            JOIN Magic m ON e.course_id = m.magic_id  --- 마법 정보 조인
            JOIN Course c ON m.magic_id = c.course_id --- 강의 정보 조인
            JOIN Professor pr ON c.instructor_id = pr.professor_id  --- 교수 정보 조인
            JOIN Person p ON pr.professor_id = p.id   --- 교수 개인정보 조인
            LEFT JOIN Magic_NSentence mn ON e.course_id = mn.magic_id AND e.student_id = mn.student_id  --- N행시 정보 조인
            WHERE e.student_id = %s    --- 현재 로그인한 학생의 강의만 필터링
            ORDER BY """ + order_by,   # 선택된 정렬 조건으로 정렬
            (session['user_id'],)
        )
        
        # 조회 결과 가져오기
        courses = cur.fetchall()
        # 내 강의 목록 페이지 템플릿 렌더링
        # courses: 조회된 강의 목록
        # sort_by: 현재 선택된 정렬 기준
        return render_template('student/my_courses.html', courses=courses, sort_by=sort_by)
        
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()  # 커서 닫기
        conn.close()  # 연결 종료

##### N행시 게시판 조회 #####
@app.route('/student/nsentence_board')  # N행시 게시판을 조회하는 라우트
@login_required  # 로그인이 필요한 기능임을 명시하는 데코레이터
def view_nsentence_board():
    # 학생 권한 체크 - 현재 세션의 role이 'Student'가 아닌 경우 접근 제한
    if session.get('role') != 'Student':
        flash('학생만 접근할 수 있습니다.')  # 에러 메시지를 플래시 메시지로 설정
        return redirect(url_for('home'))  # 홈페이지로 리다이렉트
    
    # URL 파라미터에서 선택된 강의 ID 가져오기 (정수형으로 변환)
    selected_course = request.args.get('course', type=int)
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT DISTINCT m.magic_id, m.magic_name  --- 중복 제거된 마법 ID와 마법 이름
            FROM Enrollment e  --- 수강신청 테이블
            JOIN Magic m ON e.course_id = m.magic_id  --- 마법 정보 조인
            WHERE e.student_id = %s  --- 현재 로그인한 학생의 강의만 필터링
            ORDER BY m.magic_name  --- 마법 이름으로 정렬
        """, (session['user_id'],))
        magic_courses = cur.fetchall()  # 조회 결과 저장
        
        if selected_course:  # 특정 강의가 선택된 경우
            cur.execute("""
                SELECT mn.magic_id, m.magic_name, p.name, mn.content, mn.score  --- 마법 ID, 마법 이름, 작성자 이름, N행시 내용, 점수
                FROM Magic_NSentence mn  --- N행시 테이블
                JOIN Magic m ON mn.magic_id = m.magic_id  --- 마법 정보 조인
                JOIN Person p ON mn.student_id = p.id  --- 작성자 정보 조인
                WHERE mn.magic_id = %s  --- 선택된 강의의 N행시만 필터링
                AND EXISTS (
                    SELECT 1 FROM Enrollment e 
                    WHERE e.course_id = mn.magic_id 
                    AND e.student_id = %s
                )  --- 현재 학생이 수강 중인 강의인지 확인
                ORDER BY mn.score DESC NULLS LAST, p.name  --- 점수 내림차순(NULL값은 마지막), 작성자 이름
            """, (selected_course, session['user_id']))
        else:  # 전체 강의의 N행시 조회
            cur.execute("""
                SELECT mn.magic_id, m.magic_name, p.name, mn.content, mn.score  --- 마법 ID, 마법 이름, 작성자 이름, N행시 내용, 점수
                FROM Magic_NSentence mn  --- N행시 테이블
                JOIN Magic m ON mn.magic_id = m.magic_id  --- 마법 정보 조인
                JOIN Person p ON mn.student_id = p.id  --- 작성자 정보 조인
                WHERE EXISTS (
                    SELECT 1 FROM Enrollment e 
                    WHERE e.course_id = mn.magic_id 
                    AND e.student_id = %s
                )  --- 현재 학생이 수강 중인 강의의 N행시만 필터링
                ORDER BY m.magic_name, mn.score DESC NULLS LAST, p.name  --- 마법 이름, 점수 내림차순(NULL값은 마지막), 작성자 이름
            """, (session['user_id'],))
        
        # 조회 결과 가져오기
        nsentences = cur.fetchall()
        # N행시 게시판 페이지 템플릿 렌더링
        # magic_courses: 수강 중인 강의 목록
        # nsentences: N행시 목록
        # selected_course: 선택된 강의 ID
        return render_template('student/nsentence_board.html', 
                             magic_courses=magic_courses,
                             nsentences=nsentences,
                             selected_course=selected_course)
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()  # 커서 닫기
        conn.close()  # 연결 종료

######################## 교수 #############################
##### 연구 화면으로 이동 #####
@app.route('/professor/research')  # '/professor/research' URL에 대한 라우트 핸들러 정의
@login_required  # 로그인이 필요한 페이지임을 명시하는 데코레이터
def magic_research():
    # 현재 세션의 role이 Professor가 아닌 경우 접근 제한
    if session.get('role') != 'Professor':
        flash('교수만 접근할 수 있습니다.')  # 에러 메시지를 플래시 메시지로 설정
        return redirect(url_for('home'))  # 홈페이지로 리다이렉트
    return render_template('professor/research.html')  # 연구 페이지 템플릿 렌더링

##### 연구 시도 #####
@app.route('/professor/research/attempt', methods=['POST'])  # 연구 시도를 처리하는 POST 라우트 
@login_required  # 로그인이 필요한 페이지임을 명시하는 데코레이터
def attempt_research():
    # 교수 권한 체크 - 현재 세션의 role이 Professor가 아닌 경우 접근 제한
    if session.get('role') != 'Professor':
        # 실패 응답 반환 - JSON 형식으로 성공 여부와 메시지 전달
        return jsonify({'success': False, 'message': '교수만 연구를 할 수 있습니다.'})
    
    # 50% 확률로 연구 성공 여부 결정 - random.random()은 0~1 사이의 난수 생성
    if random.random() <= 0.5:
        # 성공 시 3~8 글자 사이의 랜덤 길이 생성
        name_length = random.randint(3, 8)
        # 성공 응답 반환 - JSON 형식으로 성공 여부, 메시지, 마법 이름 길이 전달
        return jsonify({
            'success': True,
            'message': '연구에 성공했습니다!',
            'name_length': name_length  # 프론트엔드에서 마법 이름 입력 필드 생성에 사용
        })
    else:
        # 실패 시 실패 메시지 반환 - JSON 형식으로 성공 여부와 메시지 전달
        return jsonify({
            'success': False,
            'message': '연구에 실패했습니다. 다시 시도해주세요.'
        })

##### 마법 생성 #####
@app.route('/professor/create_magic', methods=['POST'])  # 마법 생성을 처리하는 POST 라우트
@login_required  # 로그인이 필요한 페이지임을 명시하는 데코레이터
def create_magic():
    # 교수 권한 체크 - 현재 세션의 role이 Professor가 아닌 경우 접근 제한
    if session.get('role') != 'Professor':
        return jsonify({'success': False, 'message': '교수만 마법을 만들 수 있습니다.'})
    
    # 폼 데이터에서 마법 이름과 수강 정원 가져오기
    magic_name = request.form.get('magic_name')  # 마법 이름을 폼에서 가져옴
    power = random.randint(5, 15)  # 5~15 사이의 랜덤 공격력 생성
    capacity = int(request.form.get('capacity', 30))  # 기본값 30의 수강 정원을 폼에서 가져옴
    price = random.randint(50, 200)  # 50~200 사이의 랜덤 가격 생성
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()  # 데이터베이스 연결 객체 생성
    cur = conn.cursor()  # 커서 객체 생성
    
    try:
        cur.execute("BEGIN")  # 트랜잭션 시작 - 데이터 일관성 보장
        
        # Magic 테이블에 새 마법 추가
        # magic_name, power, creator_id를 입력받아 새로운 마법을 생성하고 생성된 magic_id를 반환
        cur.execute("""
            INSERT INTO Magic (magic_name, power, creator_id)
            VALUES (%s, %s, %s)
            RETURNING magic_id
        """, (magic_name, power, session['user_id']))
        
        magic_id = cur.fetchone()[0]  # 생성된 마법의 ID 가져오기
        
        # Course 테이블에 강좌 정보 추가
        # magic_id를 course_id로 사용하여 새로운 강좌 생성
        cur.execute("""
            INSERT INTO Course (course_id, instructor_id, capacity)
            VALUES (%s, %s, %s)
        """, (magic_id, session['user_id'], capacity))
        
        # MagicShop 테이블에 마법 상점 정보 추가
        # 생성된 마법을 상점에 등록
        cur.execute("""
            INSERT INTO MagicShop (magic_id, price)
            VALUES (%s, %s)
        """, (magic_id, price))
        
        conn.commit()  # 트랜잭션 커밋 - 모든 변경사항 저장
        # 성공 응답 반환 - JSON 형식으로 성공 여부와 생성된 마법 정보 전달
        return jsonify({
            'success': True,
            'message': f'마법 "{magic_name}"이(가) 생성되었습니다. (공격력: {power}, 가격: {price}골드)'
        })
        
    except Exception as e:
        conn.rollback()  # 오류 발생 시 롤백 - 모든 변경사항 취소
        return jsonify({'success': False, 'message': str(e)})  # 오류 메시지 반환
    finally:
        cur.close()  # 커서 객체 해제
        conn.close()  # 데이터베이스 연결 종료

##### 학생 성적 관리 #####
# 교수가 학생들의 성적을 관리할 수 있는 페이지를 처리하는 라우트
@app.route('/professor/grade_students')  # 성적 관리 페이지의 URL 경로 설정
@login_required  # 로그인한 사용자만 접근 가능하도록 데코레이터 설정
def view_students():
    # 현재 로그인한 사용자가 교수인지 확인
    if session.get('role') != 'Professor':
        # 교수가 아닌 경우 오류 메시지를 표시하고 홈페이지로 리다이렉트
        flash('교수만 접근할 수 있습니다.')
        return redirect(url_for('home'))
    
    # PostgreSQL 데이터베이스 연결 객체 생성
    conn = get_db_connection()
    # SQL 쿼리 실행을 위한 커서 객체 생성
    cur = conn.cursor()
    
    try:
        # 교수가 만든 마법들과 수강 학생들의 정보를 조회하는 SQL 쿼리 실행
        cur.execute("""
            SELECT 
                m.magic_id,      -- 마법 고유 ID
                m.magic_name,    -- 마법 이름
                array_agg(p.name) as student_names,    -- 수강 학생들의 이름 배열
                array_agg(p.id) as student_ids,        -- 수강 학생들의 ID 배열
                array_agg(s.attack_power) as attack_powers,  -- 학생들의 공격력 배열
                array_agg(mn.content) as contents,     -- N행시 내용 배열
                array_agg(mn.score) as scores          -- N행시 점수 배열
            FROM Magic m
            JOIN Course c ON m.magic_id = c.course_id  -- 마법과 강좌 정보 연결
            JOIN Enrollment e ON m.magic_id = e.course_id  -- 수강 신청 정보 연결
            JOIN Student s ON e.student_id = s.student_id  -- 학생 정보 연결
            JOIN Person p ON s.student_id = p.id          -- 개인 정보 연결
            LEFT JOIN Magic_NSentence mn ON m.magic_id = mn.magic_id  -- N행시 정보 연결(없을 수도 있음)
                AND e.student_id = mn.student_id
            WHERE m.creator_id = %s  -- 현재 로그인한 교수가 만든 마법만 필터링
            GROUP BY m.magic_id, m.magic_name  -- 마법 단위로 그룹화
            ORDER BY m.magic_name  -- 마법 이름 순으로 정렬
        """, (session['user_id'],))
        
        # 쿼리 실행 결과를 변수에 저장
        magic_groups = cur.fetchall()
        # 성적 관리 페이지 템플릿을 렌더링하여 결과 반환
        return render_template('professor/grade.html', magic_groups=magic_groups)
    finally:
        # 데이터베이스 리소스 정리
        cur.close()  # 커서 객체 닫기
        conn.close()  # 데이터베이스 연결 종료

##### 학생 성적 부여 #####
# 성적 부여를 처리하는 POST 라우트 정의
@app.route('/professor/submit_grade', methods=['POST'])  
# 로그인이 필요한 페이지임을 명시하는 데코레이터
@login_required  
def submit_grade():
    # 교수 권한이 있는지 체크
    if session.get('role') != 'Professor':
        # 교수가 아닌 경우 에러 메시지 반환
        return jsonify({'success': False, 'message': '교수만 성적을 부여할 수 있습니다.'})
    
    try:
        # 폼 데이터에서 필요한 정보 추출
        magic_id = request.form.get('magic_id')  # 마법 ID 가져오기
        student_id = request.form.get('student_id')  # 학생 ID 가져오기
        score = int(request.form.get('score'))  # 점수를 정��로 �����환하��� 가져오기
        
        # 필수 데이터가 모두 존재하는지 확인
        if not all([magic_id, student_id, score is not None]):
            # 누락된 데이터가 있는 경우 에러 메시지 반환
            return jsonify({'success': False, 'message': '필요한 정보가 누락되었습니다.'})
        
        # 점수가 0-100 사이인지 검증
        if score < 0 or score > 100:
            # 범위를 벗어난 경우 에러 메시지 반환
            return jsonify({'success': False, 'message': '성적은 0-100 사이여야 합니다.'})
        
        # 데이터베이스 연결 객체 생성
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # 해당 마법이 현재 로그인한 교수가 만든 것인지 확인하는 쿼리
            cur.execute("""
                SELECT 1 FROM Magic 
                WHERE magic_id = %s  -- 입력받은 마법 ID
                AND creator_id = %s  -- 현재 로그인한 교수 ID
            """, (magic_id, session['user_id']))
            
            # 교수가 만든 마법이 아닌 경우
            if not cur.fetchone():
                return jsonify({'success': False, 'message': '본인이 만든 마법에 대해서만 평가할 수 있습니다.'})
            
            # N행시 존재 여부와 기존 평가 여부를 확인하는 쿼리
            cur.execute("""
                SELECT score FROM Magic_NSentence
                WHERE magic_id = %s  -- 입력받은 마법 ID
                AND student_id = %s  -- 입력받은 학생 ID
            """, (magic_id, student_id))
            
            result = cur.fetchone()
            # N행시가 존재하지 않는 경우
            if not result:
                return jsonify({'success': False, 'message': 'N행시가 존재하지 않습니다.'})
            # 이미 평가된 경우
            if result[0] is not None:
                return jsonify({'success': False, 'message': '이미 평가된 N행시입니다.'})
            
            # 트랜잭션 시작
            cur.execute("BEGIN")  
            
            # N행시 성적을 업데이트하는 쿼리
            cur.execute("""
                UPDATE Magic_NSentence
                SET score = %s  -- 입력받은 점수
                WHERE magic_id = %s  -- 마법 ID
                AND student_id = %s  -- 학생 ID
            """, (score, magic_id, student_id))
            
            # 성적에 비례해서 학생의 공격력 증가 (점수/10)
            attack_increase = score // 10
            # 학생의 공격력을 업데이트하는 쿼리
            cur.execute("""
                UPDATE Student
                SET attack_power = attack_power + %s  -- 증가할 공격력
                WHERE student_id = %s  -- 학생 ID
            """, (attack_increase, student_id))
            
            # 트랜잭션 커밋
            conn.commit()  
            # 성공 메시지 반환
            return jsonify({
                'success': True,
                'message': f'성적이 부여되었습니다. 학생의 공격력이 {attack_increase} 증가했습니다.'
            })
            
        except Exception as e:
            # 오류 발생 시 트랜잭션 롤백
            conn.rollback()  
            return jsonify({'success': False, 'message': str(e)})
        finally:
            # 데이터베이스 리소스 정리
            cur.close()  # 커서 객체 닫기
            conn.close()  # 데이터베이스 연결 종료
            
    except Exception as e:
        # 전체 처리 과정에서 발생한 예외 처리
        return jsonify({'success': False, 'message': str(e)})






##### 전투 목록 조회 #####
# '/battle_list' URL에 대한 라우트 핸들러 정의
@app.route('/battle_list')  
# 로그인이 필요한 페이지임을 명시하는 데코레이터
@login_required  
def battle_list():
    # 현재 세션의 role이 Student, Villain, Muggle이 아닌 경우 접근 제한
    if session.get('role') not in ['Student', 'Villain', 'Muggle']:
        # 에러 메시지를 플래시 메시지로 설정
        flash('전투에 참여할 수 없는 역할입니다.')  
        # 홈페이지로 리다이렉트
        return redirect(url_for('home'))  
    
    # URL 파라미터에서 role과 정렬 기준을 가져옴. 기본값은 각각 'all'과 'name_asc'
    role_filter = request.args.get('role', 'all')  
    sort_by = request.args.get('sort', 'name_asc')
    
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 기본 쿼리 구성 - Person 테이블을 기준으로 각 역할 테이블과 LEFT JOIN
        query = """
            -- 사용자 ID, 이름, 역할을 조회
            SELECT p.id, p.name, 
                   CASE 
                       WHEN m.muggle_id IS NOT NULL THEN 'Muggle'    -- Muggle인 경우
                       WHEN s.student_id IS NOT NULL THEN 'Student'   -- Student인 경우
                       WHEN v.villain_id IS NOT NULL THEN 'Villain'   -- Villain인 경우
                   END as role
            FROM Person p
            -- 각 역할 테이블과 LEFT JOIN
            LEFT JOIN Muggle m ON p.id = m.muggle_id
            LEFT JOIN Student s ON p.id = s.student_id
            LEFT JOIN Villain v ON p.id = v.villain_id
            -- 현재 사용자 제외
            WHERE p.id != %s
        """
        # 쿼리 파라미터에 현재 사용자 ID 추가
        params = [session['user_id']]  
        
        # 현재 사용자의 역할을 가진 사용자들도 제외하는 조건 추가
        query += """ AND CASE 
                      WHEN m.muggle_id IS NOT NULL THEN 'Muggle'
                      WHEN s.student_id IS NOT NULL THEN 'Student'
                      WHEN v.villain_id IS NOT NULL THEN 'Villain'
                   END != %s"""
        params.append(session['role'])
        
        # role_filter가 'all'이 아닌 경우, 해당 역할을 가진 사용자만 필터링
        if role_filter != 'all':
            query += """ AND CASE 
                          WHEN m.muggle_id IS NOT NULL THEN 'Muggle'
                          WHEN s.student_id IS NOT NULL THEN 'Student'
                          WHEN v.villain_id IS NOT NULL THEN 'Villain'
                       END = %s"""
            params.append(role_filter)
        
        # 정렬 조건을 매핑하는 딕셔너리 정의
        sort_mapping = {
            'name_asc': 'p.name ASC',    # 이름 오름차순
            'name_desc': 'p.name DESC',   # 이름 내림차순
            'role_asc': 'role ASC',       # 역할 오름차순
            'role_desc': 'role DESC'      # 역할 내림차순
        }
        # 선택된 정렬 조건을 쿼리에 추가 (없으면 기본값으로 이름 오름차순 사용)
        query += f" ORDER BY {sort_mapping.get(sort_by, 'p.name ASC')}"
        
        # 쿼리 실행
        cur.execute(query, params)
        # 조회 결과를 딕셔너리 리스트로 변환
        opponents = [{'id': row[0], 'name': row[1], 'role': row[2]} 
                    for row in cur.fetchall()]
        
        # AJAX 요청인 경우 JSON 응답 반환
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'opponents': opponents})
        
        # 일반 요청인 경우 HTML 템플릿 렌더링
        return render_template('battle_list.html', 
                             opponents=opponents,
                             current_role=session['role'])
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()
        conn.close()

@app.route('/battle', methods=['POST'])  # '/battle' URL에 대한 POST 요청 처리
@login_required  # 로그인이 필요한 기능임을 명시하는 데코레이터
def battle():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        data = request.get_json()
        opponent_id = data.get('opponent_id')
        
        # 현재 사용자의 생명력 확인
        if session['role'] == 'Student':
            cur.execute("SELECT heart, attack_power FROM Student WHERE student_id = %s", (session['user_id'],))
        elif session['role'] == 'Villain':
            cur.execute("SELECT heart, attack_power FROM Villain WHERE villain_id = %s", (session['user_id'],))
        elif session['role'] == 'Muggle':
            cur.execute("SELECT heart, attack_power FROM Muggle WHERE muggle_id = %s", (session['user_id'],))
        
        user_stats = cur.fetchone()
        if not user_stats or user_stats[0] <= 0:
            return jsonify({'success': False, 'message': '생명력이 0 이하인 상태에서는 전투할 수 없습니다.'})
        
        user_heart, user_attack = user_stats
        
        # 상대방 정보 확인
        cur.execute("""
            SELECT 
                CASE 
                    WHEN s.student_id IS NOT NULL THEN 'Student'
                    WHEN v.villain_id IS NOT NULL THEN 'Villain'
                    WHEN m.muggle_id IS NOT NULL THEN 'Muggle'
                END as role,
                COALESCE(s.heart, v.heart, m.heart) as heart,
                COALESCE(s.attack_power, v.attack_power, m.attack_power) as attack_power
            FROM Person p
            LEFT JOIN Student s ON p.id = s.student_id
            LEFT JOIN Villain v ON p.id = v.villain_id
            LEFT JOIN Muggle m ON p.id = m.muggle_id
            WHERE p.id = %s
        """, (opponent_id,))
        
        opponent = cur.fetchone()
        if not opponent or opponent[1] <= 0:
            return jsonify({'success': False, 'message': '선택한 상대와 전투할 수 없습니다.'})
        
        opponent_role, opponent_heart, opponent_attack = opponent
        
        cur.execute("BEGIN")
        
        # 공격력 비교로 승패 결정
        if user_attack > opponent_attack:
            # 승리: 공격력 증가
            if session['role'] == 'Student':
                cur.execute("UPDATE Student SET attack_power = attack_power + 2 WHERE student_id = %s", 
                           (session['user_id'],))
            elif session['role'] == 'Villain':
                cur.execute("UPDATE Villain SET attack_power = attack_power + 2 WHERE villain_id = %s", 
                           (session['user_id'],))
            elif session['role'] == 'Muggle':
                cur.execute("UPDATE Muggle SET attack_power = attack_power + 2 WHERE muggle_id = %s", 
                           (session['user_id'],))
            message = "전투에서 승리했습니다! 공격력이 2 증가했습니다."
        elif user_attack < opponent_attack:
            # 패배: 생명력 감소
            if session['role'] == 'Student':
                cur.execute("UPDATE Student SET heart = heart - 1 WHERE student_id = %s", 
                           (session['user_id'],))
            elif session['role'] == 'Villain':
                cur.execute("UPDATE Villain SET heart = heart - 1 WHERE villain_id = %s", 
                           (session['user_id'],))
            elif session['role'] == 'Muggle':
                cur.execute("UPDATE Muggle SET heart = heart - 1 WHERE muggle_id = %s", 
                           (session['user_id'],))
            message = "전투에서 패배했습니다. 생명력이 1 감소했습니다."
        else:
            message = "비겼습니다! 아무 일도 일어나지 않았습니다."
        
        conn.commit()
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cur.close()
        conn.close()



##### 랭킹 조회 #####
@app.route('/rankings')  # '/rankings' URL에 대한 라우트 핸들러 정의
@login_required  # 로그인이 필요한 페이지임을 명시하는 데코레이터
def view_rankings():
    # 현재 세션의 role 가져오기
    role = session.get('role')
    # 데이터베이스 연결 생성
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if role == 'Professor':
            # 교수는 모든 역할의 랭킹을 볼 수 있음
            # Person 테이블을 기준으로 각 역할 테이블과 LEFT JOIN하여 모든 사용자의 공격력 조회
            cur.execute("""
                SELECT p.name,                                     -- Person 테이블에서 이름 선택
                       CASE                                        -- role 컬럼 생성을 위한 CASE문
                           WHEN s.student_id IS NOT NULL THEN 'Student'    -- student_id가 있으면 Student
                           WHEN v.villain_id IS NOT NULL THEN 'Villain'    -- villain_id가 있으면 Villain
                           WHEN m.muggle_id IS NOT NULL THEN 'Muggle'     -- muggle_id가 있으면 Muggle
                       END as role,
                       COALESCE(s.attack_power, v.attack_power, m.attack_power) as attack_power  -- 각 역할의 공격력 중 NULL이 아닌 첫 번째 값 선택
                FROM Person p                                     -- Person 테이블을 기준으로
                LEFT JOIN Student s ON p.id = s.student_id       -- Student 테이블과 LEFT JOIN
                LEFT JOIN Villain v ON p.id = v.villain_id       -- Villain 테이블과 LEFT JOIN
                LEFT JOIN Muggle m ON p.id = m.muggle_id         -- Muggle 테이블과 LEFT JOIN
                WHERE COALESCE(s.attack_power, v.attack_power, m.attack_power) IS NOT NULL  -- 공격력이 NULL이 아닌 행만 선택
                ORDER BY attack_power DESC                        -- 공격력 기준 내림차순 정렬
            """)
        else:
            # 다른 역할은 자신의 역할에 해당하는 랭킹만 볼 수 있음
            # 역할에 따른 테이블명과 ID 컬럼명 매핑
            table_name = {'Student': 'Student', 'Villain': 'Villain', 'Muggle': 'Muggle'}[role]
            id_column = f'{table_name.lower()}_id'
            
            # 해당 역할의 사용자들만 조회
            cur.execute(f"""
                SELECT p.name, t.attack_power                     -- 이름과 공격력 선택
                FROM {table_name} t                               -- 해당 역할의 테이블
                JOIN Person p ON t.{id_column} = p.id            -- Person 테이블과 JOIN
                ORDER BY t.attack_power DESC                      -- 공격력 기준 내림차순 정렬
            """)
        
        # 조회 결과를 딕셔너리 리스트로 변환
        # 교수의 경우 name, role, attack_power를, 다른 역할의 경우 name, attack_power만 포함
        rankings = [dict(zip(['name', 'role', 'attack_power'] if role == 'Professor' else 
                           ['name', 'attack_power'], row))
                   for row in cur.fetchall()]
        
        # 랭킹 페이지 템플릿 렌더링
        return render_template('rankings.html', rankings=rankings, role=role)
    finally:
        # 데이터베이스 연결 자원 해제
        cur.close()
        conn.close()

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # dead_users view에서 해당 사용자 확인
        cur.execute("SELECT * FROM dead_users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        
        if not user:
            return jsonify({'success': False, 'message': '삭제할 수 없는 사용자입니다.'})
        
        # 트랜잭션 시작
        cur.execute("BEGIN")
        
        if user[3] == 'Student':
            # Magic_NSentence 삭제
            cur.execute("DELETE FROM Magic_NSentence WHERE student_id = %s", (user_id,))
            # Enrollment 삭제
            cur.execute("DELETE FROM Enrollment WHERE student_id = %s", (user_id,))
            # Student 테이블에서 삭제
            cur.execute("DELETE FROM Student WHERE student_id = %s", (user_id,))
        elif user[3] == 'Muggle':
            cur.execute("DELETE FROM ItemOwnership WHERE owner_id = %s", (user_id,))
            # 머글 테이블에서 삭제
            cur.execute("DELETE FROM Muggle WHERE muggle_id = %s", (user_id,))
        elif user[3] == 'Villain':
            cur.execute("DELETE FROM Villain WHERE villain_id = %s", (user_id,))
            
        # Person 테이블에서 삭제
        cur.execute("DELETE FROM Person WHERE id = %s", (user_id,))
        
        # 트랜잭션 커밋
        conn.commit()
        return jsonify({'success': True, 'message': '사용자가 삭제되었습니다.'})
        
    except Exception as e:
        # 오류 발생 시 롤백
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cur.close()
        conn.close()

@app.route('/admin/dead_users')
@login_required
@admin_required
def view_dead_users():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT * FROM dead_users")
        dead_users = cur.fetchall()
        return render_template('admin/dead_users.html', dead_users=dead_users)
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    scheduler.start()
    initialize_items()
    app.run(debug=True, host='0.0.0.0', port=5000)
    initialize_items()
    app.run(debug=True, host='0.0.0.0', port=5000)