import psycopg2



if __name__ == "__main__":
    print("Connected to PostgreSQL")
    conn = psycopg2.connect(
        database="postgres",
        user="postgres",
        password="postgres",
        host="localhost",
        port="5432",)

