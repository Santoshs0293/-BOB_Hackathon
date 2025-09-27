import requests
import time
import random
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:8000"

def health_check():
    resp = requests.get(f"{BASE_URL}/")
    print("Health Check:", resp.json())

def ingest_transaction(account_number, amount, merchant, device_id=None, geo="india", back_hours=0):
    payload = {
        "account_number": account_number,
        "amount": amount,
        "currency": "INR",
        "merchant": merchant,
        "device": {"device_id": device_id} if device_id else None,
        "metadata": {"geo": geo, "back_hours": back_hours}
    }
    resp = requests.post(f"{BASE_URL}/transactions/ingest", json=payload)
    data = resp.json()
    print("Ingest Transaction Response:", data)
    return data["id"]

def get_recent_transactions():
    resp = requests.get(f"{BASE_URL}/transactions/recent?limit=5")
    print("Recent Transactions:", resp.json())

def get_investigator_cases():
    resp = requests.get(f"{BASE_URL}/investigators/cases")
    print("Investigator Cases:", resp.json())

def get_explanation(tx_id):
    resp = requests.get(f"{BASE_URL}/transactions/explain/{tx_id}")
    print(f"Explanation for {tx_id}:", resp.json())

def give_feedback(tx_id, analyst, label, notes=None):
    url = f"{BASE_URL}/transactions/feedback"
    resp = requests.post(url, params={"tx_id": tx_id, "analyst": analyst, "label": label, "notes": notes})
    print(f"Feedback Response for {tx_id}:", resp.json())

def run_batch_test():
    print("\n=== Running Batch Transaction Test ===")
    merchants = ["Flipkart", "Amazon", "Paytm", "Swiggy"]
    device_ids = ["dev-1", "dev-2", "dev-3"]

    tx_ids = []
    for i in range(5):
        account = str(100000000 + i)
        amount = random.choice([500, 12000, 55000, 200000])
        merchant = random.choice(merchants)
        device = random.choice(device_ids)
        geo = random.choice(["india", "us", "eu"])
        tx_id = ingest_transaction(account, amount, merchant, device_id=device, geo=geo)
        tx_ids.append(tx_id)
        time.sleep(1)

    print("\n=== Checking recent transactions ===")
    get_recent_transactions()

    print("\n=== Checking explanations for ingested transactions ===")
    for tx in tx_ids:
        get_explanation(tx)
        time.sleep(0.5)

    print("\n=== Giving feedback on first 2 transactions ===")
    if tx_ids:
        give_feedback(tx_ids[0], analyst="santosh", label="fraud", notes="confirmed mule account")
        give_feedback(tx_ids[1], analyst="santosh", label="legit", notes="normal purchase")

    print("\n=== Investigator Cases (after feedback) ===")
    get_investigator_cases()


if __name__ == "__main__":
    print("=== CAI-UEBA Client Test (Extended) ===")

    # 1. Health check
    health_check()

    # 2. Ingest single transaction (high-value)
    tx_id = ingest_transaction("123456789", 120000, "Flipkart", device_id="dev-1")

    # 3. Wait for scoring
    time.sleep(2)

    # 4. Get recent transactions
    get_recent_transactions()

    # 5. Get investigator cases
    get_investigator_cases()

    # 6. Get explanation for the transaction
    get_explanation(tx_id)

    # 7. Give feedback
    give_feedback(tx_id, analyst="santosh", label="fraud", notes="suspicious pattern detected")

    # 8. Run batch test for robustness
    run_batch_test()
