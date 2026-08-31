import psycopg

try:
    conn = psycopg.connect("postgresql://postgres:1234%40@localhost:5436/java_apex_db")
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'llm_token_usage'")
    columns = [row[0] for row in cur.fetchall()]
    print(f"Columns: {columns}")
    conn.close()
except Exception as e:  # noqa: BLE001
    print(f"Error: {e}")
