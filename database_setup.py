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
        # 트리거 제거
        "DROP TRIGGER IF EXISTS check_players_trigger ON Match;",
        "DROP FUNCTION IF EXISTS check_valid_players();",

        # Person 테이블
        """
        CREATE TABLE IF NOT EXISTS Person (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL
        )
        """,
        # Student 테이블
        """
        CREATE TABLE IF NOT EXISTS Student (
            student_id INTEGER PRIMARY KEY REFERENCES Person(id),
            heart INTEGER DEFAULT 3,
            attack_power INTEGER DEFAULT 10
        )
        """,
        # Professor 테이블
        """
        CREATE TABLE IF NOT EXISTS Professor (
            professor_id INTEGER PRIMARY KEY REFERENCES Person(id)
        )
        """,
        # Villain 테이블
        """
        CREATE TABLE IF NOT EXISTS Villain (
            villain_id INTEGER PRIMARY KEY REFERENCES Person(id),
            heart INTEGER DEFAULT 3,
            attack_power INTEGER DEFAULT 15
        )
        """,
        # Muggle 테이블
        """
        CREATE TABLE IF NOT EXISTS Muggle (
            muggle_id INTEGER PRIMARY KEY REFERENCES Person(id),
            heart INTEGER DEFAULT 3,
            attack_power INTEGER DEFAULT 5,
            money DECIMAL(10,2) DEFAULT 1000.00
        )
        """,
        # Magic 테이블
        """
        CREATE TABLE IF NOT EXISTS Magic (
            magic_id SERIAL PRIMARY KEY,
            magic_name VARCHAR(100) NOT NULL,
            power INTEGER NOT NULL,
            creator_id INTEGER REFERENCES Professor(professor_id)
        )
        """,
        # Course 테이블
        """
        CREATE TABLE IF NOT EXISTS Course (
            course_id INTEGER REFERENCES Magic(magic_id),
            instructor_id INTEGER REFERENCES Professor(professor_id),
            capacity INTEGER NOT NULL,
            current_enrollment INTEGER DEFAULT 0,
            opening_status BOOLEAN DEFAULT true,
            PRIMARY KEY (course_id, instructor_id)
        )
        """,
        # Magic_NSentence 테이블
        """
        CREATE TABLE IF NOT EXISTS Magic_NSentence (
            magic_id INTEGER REFERENCES Magic(magic_id),
            student_id INTEGER REFERENCES Student(student_id),
            content TEXT NOT NULL,
            score INTEGER,
            PRIMARY KEY (magic_id, student_id)
        )
        """,
        # Enrollment 테이블
        """
        CREATE TABLE IF NOT EXISTS Enrollment (
            course_id INTEGER,
            student_id INTEGER REFERENCES Student(student_id),
            PRIMARY KEY (course_id, student_id),
            FOREIGN KEY (course_id) REFERENCES Magic(magic_id)
        )
        """,
        # Item 테이블
        """
        CREATE TABLE IF NOT EXISTS Item (
            item_id SERIAL PRIMARY KEY,
            item_name VARCHAR(100) NOT NULL,
            current_price DECIMAL(10,2) NOT NULL
        )
        """,
        # ItemOwnership 테이블
        """
        CREATE TABLE IF NOT EXISTS ItemOwnership (
            owner_id INTEGER REFERENCES Muggle(muggle_id),
            item_id INTEGER REFERENCES Item(item_id),
            price DECIMAL(10,2) NOT NULL,
            amount INTEGER NOT NULL,
            PRIMARY KEY (owner_id, item_id)
        )
        """,
        # Game 테이블
        """
        CREATE TABLE IF NOT EXISTS Game (
            game_id SERIAL PRIMARY KEY,
            game_name VARCHAR(100) NOT NULL,
            game_description TEXT NOT NULL,
            difficulty INTEGER NOT NULL,  -- 1: 쉬움, 2: 보통, 3: 어려움
            reward INTEGER NOT NULL,      -- 공격력 증가량
            route_name VARCHAR(100) NOT NULL  -- Flask 라우트 이름 (예: 'rock_paper_scissors')
        )
        """,
        # GameAttempt 테이블
        """
        CREATE TABLE IF NOT EXISTS GameAttempt (
            game_id INTEGER REFERENCES Game(game_id),
            villain_id INTEGER REFERENCES Villain(villain_id),
            result BOOLEAN NOT NULL,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (game_id, villain_id, attempt_time)
        )
        """,
        # MagicShop 테이블
        """
        CREATE TABLE IF NOT EXISTS MagicShop (
            magic_id INTEGER PRIMARY KEY REFERENCES Magic(magic_id),
            price DECIMAL(10,2) NOT NULL
        )
        """,
        # Match 테이블
        """
        CREATE TABLE IF NOT EXISTS Match (
            match_id SERIAL PRIMARY KEY,
            challenger_id INTEGER NOT NULL,
            opponent_id INTEGER NOT NULL,
            result BOOLEAN,
            match_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        # 트리거 함수 생성
        """
        CREATE OR REPLACE FUNCTION check_valid_players()
        RETURNS TRIGGER AS $$
        BEGIN
            -- challenger_id 검증
            IF NOT EXISTS (
                SELECT 1 FROM Student WHERE student_id = NEW.challenger_id
                UNION
                SELECT 1 FROM Villain WHERE villain_id = NEW.challenger_id
                UNION
                SELECT 1 FROM Muggle WHERE muggle_id = NEW.challenger_id
            ) THEN
                RAISE EXCEPTION 'Invalid challenger_id';
            END IF;

            -- opponent_id 검증
            IF NOT EXISTS (
                SELECT 1 FROM Student WHERE student_id = NEW.opponent_id
                UNION
                SELECT 1 FROM Villain WHERE villain_id = NEW.opponent_id
                UNION
                SELECT 1 FROM Muggle WHERE muggle_id = NEW.opponent_id
            ) THEN
                RAISE EXCEPTION 'Invalid opponent_id';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """,
        # 트리거 생성
        """
        CREATE TRIGGER check_players_trigger
        BEFORE INSERT OR UPDATE ON Match
        FOR EACH ROW
        EXECUTE FUNCTION check_valid_players();
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


if __name__ == '__main__':
    #create_tables()
    insert_test_data()
    view_test_data()
    #drop_all_tables()
    #view_test_data()
    #delete_all_data()
    
    