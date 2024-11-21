from flask import Flask, request, jsonify
import psycopg2
from psycopg2 import sql
from flask import abort

app = Flask(__name__)

# 데이터베이스 연결 설정
def get_db_connection():
    conn = psycopg2.connect(
        host="###",
        dbname="###",
        user="###",
        password="###"
    )
    return conn

# authorization 체크 함수
def check_authorization(user_type):
    # 예시로 학생(Student)만 목록 조회가 가능하다는 권한 체크
    if user_type != 'Student':
        abort(403, description="Forbidden: You do not have permission to view this resource.")

# 학생이 수강할 수 있는 모든 수업 목록 조회
@app.route('/courses', methods=['GET'])
def get_courses():
    # 권한 체크 (예: 학생만 조회 가능)
    user_type = request.args.get('user_type')  # 쿼리 파라미터로 사용자가 어떤 타입인지 전달
    check_authorization(user_type)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 모든 수업 정보를 조회하는 쿼리
    cur.execute("""
        SELECT course_id, instructor_id, capacity, current_enrollment, opening_status 
        FROM Course;
    """)
    
    courses = cur.fetchall()
    
    # 결과를 JSON 형태로 반환
    course_list = []
    for course in courses:
        course_list.append({
            "course_id": course[0],
            "instructor_id": course[1],
            "capacity": course[2],
            "current_enrollment": course[3],
            "opening_status": course[4]
        })
    
    cur.close()
    conn.close()
    
    return jsonify(course_list)

# 학생과 빌런만 하트 구매 가능
@app.route('/magic_shop', methods=['GET'])
def get_magic_shop_items():
    user_type = request.args.get('user_type')
    check_authorization_for_magic_shop(user_type)
    
    conn = get_db_connection()
    cur = conn.cursor()

    # Magic Shop에서 하트만 구매할 수 있도록 쿼리
    cur.execute("""
        SELECT m.magic_id, m.magic_name, ms.price
        FROM MagicShop ms
        JOIN Magic m ON ms.magic_id = m.magic_id
        WHERE m.magic_name = 'Heart';
    """)
    
    items = cur.fetchall()
    
    magic_shop_items = []
    for item in items:
        magic_shop_items.append({
            "magic_id": item[0],
            "magic_name": item[1],
            "price": item[2]
        })

    cur.close()
    conn.close()
    
    return jsonify(magic_shop_items)

# Magic Shop 권한 체크 (학생과 빌런만 하트 구매 가능)
def check_authorization_for_magic_shop(user_type):
    if user_type not in ['Student', 'Villain']:
        abort(403, description="Forbidden: You do not have permission to buy from the magic shop.")

@app.route('/match', methods=['POST'])
def create_match():
    challenger_id = request.json.get('challenger_id')
    opponent_id = request.json.get('opponent_id')
    result = request.json.get('result')
    
    # challenger_id와 opponent_id는 Student, Villain, Muggle만 가능
    valid_types = ['Student', 'Villain', 'Muggle']
    
    # 확인 로직
    if not (challenger_id and opponent_id and result):
        abort(400, description="Invalid input")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 경기 결과 기록
    cur.execute("""
        INSERT INTO Match (challenger_id, opponent_id, result)
        VALUES (%s, %s, %s)
    """, (challenger_id, opponent_id, result))
    
    conn.commit()
    
    cur.close()
    conn.close()
    
    return jsonify({"message": "Match created successfully!"}), 201

@app.route('/magic_nhaengsi', methods=['POST'])
def create_magic_nhaengsi():
    magic_id = request.json.get('magic_id')
    student_id = request.json.get('student_id')
    nhaengsi_content = request.json.get('nhaengsi_content')
    score = request.json.get('score')

    if not (magic_id and student_id and nhaengsi_content and score):
        abort(400, description="Invalid input")
    
    conn = get_db_connection()
    cur = conn.cursor()

    # Magic n행시 점수 저장
    cur.execute("""
        INSERT INTO MagicNhaengsi (magic_id, student_id, n행시내용, score)
        VALUES (%s, %s, %s, %s)
    """, (magic_id, student_id, nhaengsi_content, score))
    
    conn.commit()

    cur.close()
    conn.close()

    return jsonify({"message": "Magic n행시 added successfully!"}), 201

if __name__ == '__main__':
    app.run(debug=True)
