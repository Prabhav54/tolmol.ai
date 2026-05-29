import requests
import time

BASE_URL = "http://127.0.0.1:8000"

def run_integration_test():
    print("🚀 Starting Hybrid RAG Platform Verification...\n")
    
    # 1. Test Ingestion Path (Scraping a Wikipedia page about shoes)
    ingest_payload = {
        "url": "https://en.wikipedia.org/wiki/Running_shoe",
        "product_id": 555
    }
    
    print(f"1. Sending Ingestion Request for Product ID {ingest_payload['product_id']}...")
    try:
        response = requests.post(f"{BASE_URL}/ingest", json=ingest_payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}\n")
    except Exception as e:
        print(f"❌ Ingestion Failed: {e}\n")
        return

    # Give the system a brief moment to stabilize the database insertion
    time.sleep(1)

    # 2. Test Vector Path (Contextual Question requiring Semantic Search)
    vector_query = {
        "prompt": "What materials or features are used in running shoes?",
        "product_id": 555
    }
    print("2. Testing Vector Engine Routing Path...")
    try:
        res = requests.post(f"{BASE_URL}/query", json=vector_query)
        print(f"Engine Selected: {res.json().get('engine')}")
        print(f"Response: {res.json().get('response')}\n")
    except Exception as e:
        print(f"❌ Vector Query Failed: {e}\n")

    # 3. Test SQL Path (Analytical/Count Question requiring Hard Math)
    sql_query = {
        "prompt": "How many total review chunks do we have stored for product 555?",
        "product_id": 555
    }
    print("3. Testing SQL Engine Routing Path...")
    try:
        res = requests.post(f"{BASE_URL}/query", json=sql_query)
        print(f"Engine Selected: {res.json().get('engine')}")
        print(f"SQL Executed: {res.json().get('query_executed')}")
        print(f"Response: {res.json().get('response')}\n")
    except Exception as e:
        print(f"❌ SQL Query Failed: {e}\n")

if __name__ == "__main__":
    run_integration_test()