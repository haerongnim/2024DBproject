import psycopg2
from dotenv import load_dotenv
import os
import sys
from werkzeug.security import generate_password_hash

# Windows 콘솔에서 한글 출력을 위한 설정
if sys.platform == 'win32':
    import locale
    locale.setlocale(locale.LC_ALL, 'Korean_Korea.UTF-8')
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432')
    )

def create_tables():
    commands = [
        # Person 테이블: 모든 사용자의 기본 정보를 저장
        """
        CREATE TABLE IF NOT EXISTS Person (
            id SERIAL PRIMARY KEY,          -- 자동 증가하는 고유 식별자
            name VARCHAR(100) NOT NULL,     -- 사용자 이름 (필수)
            email VARCHAR(100) UNIQUE NOT NULL,  -- 고유한 이메일 주소 (필수)
            password VARCHAR(255) NOT NULL   -- 암호화된 비밀번호 (필수)
        )
        """,
        # Student 테이블: 학생 특성 정보 저장
        """
        CREATE TABLE IF NOT EXISTS Student (
            student_id INTEGER PRIMARY KEY REFERENCES Person(id),  -- Person 테이블의 id를 참조
            heart INTEGER DEFAULT 3,        -- 생명력 (기본값: 3)
            attack_power INTEGER DEFAULT 10 -- 공격력 (기본값: 10)
        )
        """,
        # Professor 테이블: 교수 정보 저장
        """
        CREATE TABLE IF NOT EXISTS Professor (
            professor_id INTEGER PRIMARY KEY REFERENCES Person(id)  -- Person 테이블의 id를 참조
        )
        """,
        # Villain 테이블: 악당 특성 정보 저장
        """
        CREATE TABLE IF NOT EXISTS Villain (
            villain_id INTEGER PRIMARY KEY REFERENCES Person(id),  -- Person 테이블의 id를 참조
            heart INTEGER DEFAULT 3,        -- 생명력 (기본값: 3)
            attack_power INTEGER DEFAULT 15 -- 공격력 (기본값: 15)
        )
        """,
        # Muggle 테이블: 머글 특성 정보 저장
        """
        CREATE TABLE IF NOT EXISTS Muggle (
            muggle_id INTEGER PRIMARY KEY REFERENCES Person(id),  -- Person 테이블의 id를 참조
            heart INTEGER DEFAULT 3,        -- 생명력 (기본값: 3)
            attack_power INTEGER DEFAULT 5, -- 공격력 (기본값: 5)
            money DECIMAL(10,2) DEFAULT 1000.00  -- 보유 금액 (기본값: 1000.00)
        )
        """,
        # Magic 테이블: 마법 정보 저장
        """
        CREATE TABLE IF NOT EXISTS Magic (
            magic_id SERIAL PRIMARY KEY,    -- 자동 증가하는 고유 식별자
            magic_name VARCHAR(100) NOT NULL,  -- 마법 이름 (필수)
            power INTEGER NOT NULL,         -- 마법의 공격력
            creator_id INTEGER REFERENCES Professor(professor_id)  -- 마법을 만든 교수 ID
        )
        """,
        # Course 테이블: 강의 정보 저장
        """
        CREATE TABLE IF NOT EXISTS Course (
            course_id INTEGER PRIMARY KEY REFERENCES Magic(magic_id),  -- Magic 테이블의 magic_id를 참조
            instructor_id INTEGER REFERENCES Professor(professor_id),  -- 강의 담당 교수 ID
            capacity INTEGER DEFAULT 30,     -- 수강 정원 (기본값: 30)
            current_enrollment INTEGER DEFAULT 0,  -- 현재 수강 인원
            opening_status BOOLEAN DEFAULT true   -- 수강신청 가능 여부
        )
        """,
        # Magic_NSentence 테이블: 학생들의 N행시 저장
        """
        CREATE TABLE IF NOT EXISTS Magic_NSentence (
            magic_id INTEGER REFERENCES Magic(magic_id),    -- 마법 ID
            student_id INTEGER REFERENCES Student(student_id),  -- 학생 ID
            content TEXT NOT NULL,          -- N행시 내용
            score INTEGER,                  -- 교수가 준 점수
            PRIMARY KEY (magic_id, student_id)  -- 마법과 학생의 조합이 고유해야 함
        )
        """,
        # Enrollment 테이블: 수강 신청 정보 저장
        """
        CREATE TABLE IF NOT EXISTS Enrollment (
            course_id INTEGER,              -- 강의 ID
            student_id INTEGER REFERENCES Student(student_id),  -- 학생 ID
            PRIMARY KEY (course_id, student_id),  -- 강의와 학생의 조합이 고유해야 함
            FOREIGN KEY (course_id) REFERENCES Magic(magic_id)  -- Magic 테이블의 magic_id를 참조
        )
        """,
        # Item 테이블: 상점에서 판매하는 아이템 정보 저장
        """
        CREATE TABLE IF NOT EXISTS Item (
            item_id SERIAL PRIMARY KEY,     -- 자동 증가하는 고유 식별자
            item_name VARCHAR(100) NOT NULL,  -- 아이템 이름 (필수)
            current_price DECIMAL(10,2) NOT NULL  -- 현재 가격
        )
        """,
        # ItemOwnership 테이블: 머글이 보유한 아이템 정보 저장
        """
        CREATE TABLE IF NOT EXISTS ItemOwnership (
            owner_id INTEGER REFERENCES Muggle(muggle_id),  -- 소유자(머글) ID
            item_id INTEGER REFERENCES Item(item_id),       -- 아이템 ID
            price DECIMAL(10,2) NOT NULL,   -- 구매 당시 가격
            amount INTEGER NOT NULL,        -- 보유 수량
            PRIMARY KEY (owner_id, item_id)  -- 소유자와 아이템의 조합이 고유해야 함
        )
        """,
        # Game 테이블: 미니게임 정보 저장
        """
        CREATE TABLE IF NOT EXISTS Game (
            game_id SERIAL PRIMARY KEY,     -- 자동 증가하는 고유 식별자
            game_name VARCHAR(100) NOT NULL,  -- 게임 이름 (필수)
            game_description TEXT NOT NULL,   -- 게임 설명
            difficulty INTEGER NOT NULL,      -- 난이도 (1: 쉬움, 2: 보통, 3: 어려움)
            reward INTEGER NOT NULL,          -- 성공 시 공격력 증가량
            route_name VARCHAR(100) NOT NULL  -- Flask 라우트 이름
        )
        """,
        # GameAttempt 테이블: 게임 시도 기록 저장
        """
        CREATE TABLE IF NOT EXISTS GameAttempt (
            game_id INTEGER REFERENCES Game(game_id),    -- 게임 ID
            villain_id INTEGER REFERENCES Villain(villain_id),  -- 악당 ID
            result BOOLEAN NOT NULL,        -- 성공 여부
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 시도 시간
            PRIMARY KEY (game_id, villain_id, attempt_time)  -- 게임, 악당, 시간의 조합이 고유해야 함
        )
        """,
        # MagicShop 테이블: 판매중인 마법 정보 저장
        """
        CREATE TABLE IF NOT EXISTS MagicShop (
            magic_id INTEGER PRIMARY KEY REFERENCES Magic(magic_id),  -- Magic 테이블의 magic_id를 참조
            price DECIMAL(10,2) NOT NULL    -- 마법의 판매 가격
        )
        """,
        # Admin 테이블: 관리자
        """
        CREATE TABLE IF NOT EXISTS Admin (
            admin_id INTEGER PRIMARY KEY REFERENCES Person(id)
        )
        """,
        # dead_users View
        """
        CREATE OR REPLACE VIEW dead_users AS
        SELECT 
            p.id,
            p.name,
            p.email,
            CASE 
                WHEN s.student_id IS NOT NULL THEN 'Student'
                WHEN v.villain_id IS NOT NULL THEN 'Villain'
                WHEN m.muggle_id IS NOT NULL THEN 'Muggle'
            END as role,
            COALESCE(s.heart, v.heart, m.heart) as heart
        FROM Person p
        LEFT JOIN Student s ON p.id = s.student_id
        LEFT JOIN Villain v ON p.id = v.villain_id
        LEFT JOIN Muggle m ON p.id = m.muggle_id
        WHERE COALESCE(s.heart, v.heart, m.heart) <= 0;
        """
    ]

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        for command in commands:
            cur.execute(command)
            
        cur.close()
        conn.commit()
        print("Tables created successfully")
        
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

def drop_all_tables():
    commands = [
        # 먼저 트리거 제거
        "DROP TRIGGER IF EXISTS check_players_trigger ON Match;",
        "DROP FUNCTION IF EXISTS check_valid_players();",
        
        # 외래 키를 가진 테이블부터 순서대로 제거
        "DROP TABLE IF EXISTS Match CASCADE;",
        "DROP TABLE IF EXISTS GameAttempt CASCADE;",
        "DROP TABLE IF EXISTS Game CASCADE;",
        "DROP TABLE IF EXISTS ItemOwnership CASCADE;",
        "DROP TABLE IF EXISTS Item CASCADE;",
        "DROP TABLE IF EXISTS MagicShop CASCADE;",
        "DROP TABLE IF EXISTS Enrollment CASCADE;",
        "DROP TABLE IF EXISTS Magic_NSentence CASCADE;",
        "DROP TABLE IF EXISTS Course CASCADE;",
        "DROP TABLE IF EXISTS Magic CASCADE;",
        "DROP TABLE IF EXISTS Student CASCADE;",
        "DROP TABLE IF EXISTS Professor CASCADE;",
        "DROP TABLE IF EXISTS Villain CASCADE;",
        "DROP TABLE IF EXISTS Muggle CASCADE;",
        "DROP TABLE IF EXISTS Person CASCADE;"
    ]

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        for command in commands:
            cur.execute(command)
            
        cur.close()
        conn.commit()
        print("All tables dropped successfully")
        
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
    finally:
        if conn is not None:
            conn.close()

def insert_test_data():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Person 테이블에 데이터 삽입
        cur.execute("""
            INSERT INTO Person (name, email, password) VALUES
            ('Harry Potter', 'harry@hogwarts.edu', %s),
            ('Albus Dumbledore', 'albus@hogwarts.edu', %s),
            ('Voldemort', 'voldemort@dark.magic', %s),
            ('Vernon Dursley', 'vernon@muggle.com', %s)
            RETURNING id;
        """, (
            generate_password_hash('gryffindor'),
            generate_password_hash('phoenix'),
            generate_password_hash('horcrux'),
            generate_password_hash('normal')
        ))
        
        ids = cur.fetchall()
        harry_id, dumbledore_id, voldemort_id, vernon_id = [id[0] for id in ids]

        # Student 테이블에 데이터 삽입
        cur.execute("""
            INSERT INTO Student (student_id, heart, attack_power) VALUES
            (%s, 3, 15);
        """, (harry_id,))

        # Professor 테이블에 데이터 삽입
        cur.execute("""
            INSERT INTO Professor (professor_id) VALUES (%s);
        """, (dumbledore_id,))

        # Villain 테이블에 데이터 삽입
        cur.execute("""
            INSERT INTO Villain (villain_id, heart, attack_power) VALUES
            (%s, 3, 20);
        """, (voldemort_id,))

        # Muggle 테이블에 데이터 삽입
        cur.execute("""
            INSERT INTO Muggle (muggle_id, heart, attack_power, money) VALUES
            (%s, 3, 5, 1000.00);
        """, (vernon_id,))

        # Magic 테이블에 데이터 삽입
        cur.execute("""
            INSERT INTO Magic (magic_name, power, creator_id) VALUES
            ('Expelliarmus', 10, %s),
            ('Lumos', 5, %s)
            RETURNING magic_id;
        """, (dumbledore_id, dumbledore_id))

        magic_ids = cur.fetchall()
        expelliarmus_id, lumos_id = [id[0] for id in magic_ids]

        # MagicShop 테이블에 데이터 삽입
        cur.execute("""
            INSERT INTO MagicShop (magic_id, price) VALUES
            (%s, 100.00),
            (%s, 50.00);
        """, (expelliarmus_id, lumos_id))

        # Game 테이블에 기본 게임 데이터 삽입
        cur.execute("""
            INSERT INTO Game (game_name, game_description, difficulty, reward, route_name) VALUES
            ('✌️ 가위바위보', '컴퓨터와 가위바위보 대결을 펼쳐보세요!', 1, 3, 'rock_paper_scissors'),
            ('⚾ 숫자야구', '4자리 숫자를 맞추는 두뇌 게임에 도전하세요!', 2, 5, 'number_baseball'),
            ('🎓 상식 퀴즈', '다양한 상식 문제를 풀어보세요!', 3, 7, 'quiz_game')
        """)

        conn.commit()
        print("Test data inserted successfully")
        
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
    finally:
        if conn is not None:
            conn.close()

def view_test_data():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Person 테이블 조회
        print("\n=== Person 테이블 ===")
        cur.execute("SELECT id, name, email FROM Person;")
        for record in cur.fetchall():
            print(record)

        # Student 테이블 조회
        print("\n=== Student 테이블 ===")
        cur.execute("""
            SELECT p.name, s.heart, s.attack_power 
            FROM Student s 
            JOIN Person p ON s.student_id = p.id;
        """)
        for record in cur.fetchall():
            print(record)

        # Professor 테이블 조회
        print("\n=== Professor 테이블 ===")
        cur.execute("""
            SELECT p.name 
            FROM Professor prof 
            JOIN Person p ON prof.professor_id = p.id;
        """)
        for record in cur.fetchall():
            print(record)

        # Villain 테이블 조회
        print("\n=== Villain 테이블 ===")
        cur.execute("""
            SELECT p.name, v.heart, v.attack_power 
            FROM Villain v 
            JOIN Person p ON v.villain_id = p.id;
        """)
        for record in cur.fetchall():
            print(record)

        # Magic 테이블 조회
        print("\n=== Magic 테이블 ===")
        cur.execute("""
            SELECT m.magic_name, m.power, p.name as creator 
            FROM Magic m 
            JOIN Professor prof ON m.creator_id = prof.professor_id
            JOIN Person p ON prof.professor_id = p.id;
        """)
        for record in cur.fetchall():
            print(record)

        # MagicShop 테이블 조회
        print("\n=== MagicShop 테이블 ===")
        cur.execute("""
            SELECT m.magic_name, ms.price 
            FROM MagicShop ms 
            JOIN Magic m ON ms.magic_id = m.magic_id;
        """)
        for record in cur.fetchall():
            print(record)

        cur.close()
        
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
    finally:
        if conn is not None:
            conn.close()
def delete_all_data():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 모든 테이블의 데이터 삭제
        tables = [
            'Match', 'GameAttempt', 'Game', 'ItemOwnership', 'Item',
            'MagicShop', 'Enrollment', 'Magic_NSentence', 'Course',
            'Magic', 'Student', 'Professor', 'Villain', 'Muggle', 'Person'
        ]

        for table in tables:
            cur.execute(f"DELETE FROM {table};")

        conn.commit()
        print("All data deleted successfully")
        
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
    finally:
        if conn is not None:
            conn.close()
def drop_match_table():
    command = "DROP TABLE IF EXISTS Match CASCADE;"
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(command)
        cur.close()
        conn.commit()
        print("Match table dropped successfully")
        
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
    finally:
        if conn is not None:
            conn.close()

def make_admin():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # admin 역할 생성
        cur.execute("CREATE ROLE admin;")

        cur.execute("GRANT SELECT ON dead_users TO admin;")
        cur.execute("GRANT SELECT, DELETE ON Magic_NSentence TO admin;")
        cur.execute("GRANT SELECT, DELETE ON Enrollment TO admin;")
        cur.execute("GRANT SELECT, DELETE ON Student TO admin;")
        cur.execute("GRANT SELECT, DELETE ON ItemOwnership TO admin;")
        cur.execute("GRANT SELECT, DELETE ON Muggle TO admin;")
        cur.execute("GRANT SELECT, DELETE ON Villain TO admin;")
        cur.execute("GRANT SELECT, DELETE ON Person TO admin;")

        # admin@admin 사용자 생성
        cur.execute("CREATE USER \"admin@admin\" WITH PASSWORD 'admin';")

        # 사용자에게 admin 역할 부여
        cur.execute("GRANT admin TO \"admin@admin\";")

        conn.commit()
        print("Admin role and user created successfully")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error creating admin role and user: {error}")
    finally:
        if conn is not None:
            conn.close()

def insert_admin():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 관리자 계정이 이미 존재하는지 확인
        cur.execute("SELECT * FROM Person WHERE email = 'admin@admin'")
        if cur.fetchone() is None:
            # Person 테이블에 관리자 추가
            cur.execute(
                "INSERT INTO Person (name, email, password) VALUES (%s, %s, %s) RETURNING id",
                ('관리자', 'admin@admin', generate_password_hash('admin'))
            )
            admin_id = cur.fetchone()[0]
            
            # Admin 테이블에 추가
            cur.execute("INSERT INTO Admin (admin_id) VALUES (%s)", (admin_id,))
            
            conn.commit()
            print("Admin account created successfully")
    except Exception as e:
        conn.rollback()
        print(f"Error creating admin account: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    create_tables()
    make_admin()
    insert_admin()
    insert_test_data()
    #view_test_data()
    #drop_all_tables()
    #view_test_data()
    #delete_all_data()
    