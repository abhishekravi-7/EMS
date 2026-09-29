import psycopg

try:
    conn = psycopg.connect("postgresql://postgres:1234%40@localhost:5436/java_apex_db")
    cur = conn.cursor()
    cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'llm_token_usage')")
    exists = cur.fetchone()[0]
    print(f"Table llm_token_usage exists: {exists}")
    if exists:
        cur.execute("SELECT COUNT(*) FROM llm_token_usage")
        print(f"Count: {cur.fetchone()[0]}")
    conn.close()
except Exception as e:  # noqa: BLE001
    print(f"Error: {e}")
