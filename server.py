import psycopg2

if __name__ == "__main__":
    print("Connected to PostgreSQL")
    
    con = psycopg2.connect(
        database="sample2024",
        user="db2024",
        password="db2024",
        host="::1", # 127.0.0.1 과 같음
        port="5432"
    )

    cursor = con.cursor()

    # 테이블 조회
    # cursor.execute("SELECT * FROM classroom")
    #result = cursor.fetchall()
    #print(result)

    cursor.execute("INSERT INTO customers (customer_id, customer_name, phone, birth_date, balance) VALUES (1234, 'Cho', '12345678', '2024-01-01', 78.56)")
    con.commit()    # psycopg2는 manual commit 이 기본값임
                    # auto commit 을 하려면 con.autocommit=True 로 설정
    
    cursor.execute("SELECT * FROM customers")
    result = cursor.fetchall()

    for r in result:
        print(r)
