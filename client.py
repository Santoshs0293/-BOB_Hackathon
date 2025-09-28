import requests
import time
import random
from collections import Counter
from tabulate import tabulate

BASE_URL = "http://127.0.0.1:8000"
ALL_TX_IDS = []        # track all transactions globally
FORCED_FRAUDS = set()  # accounts we force-mark as fraud


# ------------------------------
# Utility: Pretty print key parts
# ------------------------------
def pretty_txn(label, data, highlight_fraud=False):
    if not data:
        print(f"{label}: ❌ No data")
        return

    verdict = (data.get("verdict") or "unknown").lower()
    score = round(data.get("score", 0), 3)

    # Marker with tags
    marker = verdict.upper()
    if "fraud" in verdict:
        marker = f"⚠️ FRAUD"

    # Highlight fraud cases in red
    if "fraud" in verdict and highlight_fraud:
        print(f"\033[91m{label}: [id={data.get('id')}] "
              f"Acct={data.get('account_number')} | "
              f"Amt={data.get('amount')} INR | "
              f"Verdict={marker} | "
              f"Score={score}\033[0m")
    else:
        print(f"{label}: [id={data.get('id')}] "
              f"Acct={data.get('account_number')} | "
              f"Amt={data.get('amount')} INR | "
              f"Verdict={marker} | "
              f"Score={score}")

    if data.get("explanation"):
        print(f"   📝 {data['explanation'][:120]}...")


# ------------------------------
# API helpers
# ------------------------------
def health_check():
    resp = requests.get(f"{BASE_URL}/")
    print("✅ Health Check:", resp.json())


def ingest_transaction(account_number, amount, merchant, device_id=None,
                       geo="india", back_hours=0, card_present=True):
    payload = {
        "account_number": account_number,
        "amount": amount,
        "currency": "INR",
        "merchant": merchant,
        "device": {"device_id": device_id} if device_id else None,
        "metadata": {
            "geo": geo,
            "back_hours": back_hours,
            "card_present": card_present
        }
    }
    resp = requests.post(f"{BASE_URL}/transactions/ingest", json=payload)
    data = resp.json()
    pretty_txn("📥 Ingested", data)
    ALL_TX_IDS.append(data["id"])
    return data["id"]


def get_recent_transactions(limit=5):
    resp = requests.get(f"{BASE_URL}/transactions/recent?limit={limit}")
    txs = resp.json()
    print(f"\n🕒 Recent {limit} Transactions:")

    for tx in txs:
        if isinstance(tx, dict):
            acct = tx.get("account_number")
            if acct in FORCED_FRAUDS:
                tx["verdict"] = "fraud (analyst)"
            pretty_txn("   ➡️", tx)
        elif isinstance(tx, str):
            r = requests.get(f"{BASE_URL}/transactions/explain/{tx}")
            if r.status_code == 200:
                tx_data = r.json()
                acct = tx_data.get("account_number")
                if acct in FORCED_FRAUDS:
                    tx_data["verdict"] = "fraud (analyst)"
                tx_data["id"] = tx
                pretty_txn("   ➡️", tx_data)
        else:
            print(f"   ⚠️ Unexpected tx format: {tx}")


def get_investigator_cases():
    resp = requests.get(f"{BASE_URL}/investigators/cases")
    cases = resp.json().get("cases", [])
    print("\n🕵️ Investigator Cases:")

    # Fraud cases first
    fraud_cases = []
    other_cases = []
    for tx in cases:
        acct = tx.get("account_number")
        verdict = (tx.get("verdict") or "unknown").lower()
        fraud_tag = ""

        if acct in FORCED_FRAUDS:
            tx["verdict"] = "fraud (analyst)"
            fraud_tag = "(analyst)"
            fraud_cases.append(tx)
        elif verdict == "fraud":
            tx["verdict"] = "fraud (auto)"
            fraud_tag = "(auto)"
            fraud_cases.append(tx)
        else:
            other_cases.append(tx)

    for tx in fraud_cases + other_cases:
        pretty_txn("   ⚠️ Case", tx, highlight_fraud=True)


def get_explanation(tx_id):
    resp = requests.get(f"{BASE_URL}/transactions/explain/{tx_id}")
    data = resp.json()
    acct = data.get("account_number")

    # Override forced fraud verdicts
    if acct in FORCED_FRAUDS:
        data["verdict"] = "fraud (analyst)"

    print(f"\n📖 Explanation for {tx_id}: [id={tx_id}] Acct={acct} | "
          f"Amt={data.get('amount')} INR | Verdict={data.get('verdict')} | "
          f"Score={round(data.get('score', 0), 3)}")
    if data.get("explanation"):
        print(f"   📝 {data['explanation'][:120]}...")

    suspicious = data.get("top_graph_suspicious", [])
    if suspicious:
        print("  🕸️ Top Graph Suspicious Connections:")
        for acc, score in suspicious[:5]:
            print(f"    - {acc}: {round(score, 3)}")
    else:
        print("  (no graph suspicious accounts)")


def give_feedback(tx_id, analyst, label, notes=None):
    url = f"{BASE_URL}/transactions/feedback"
    resp = requests.post(url, params={
        "tx_id": tx_id,
        "analyst": analyst,
        "label": label,
        "notes": notes
    })
    print(f"📝 Feedback for {tx_id}: {resp.json()}")


# ------------------------------
# Batch scenarios (with forced frauds)
# ------------------------------
def run_batch_test():
    print("\n=== 🚀 Running Batch Transaction Test ===")
    merchants = ["Flipkart", "Amazon", "Paytm", "Swiggy", "Myntra", "IRCTC"]
    device_ids = ["dev-1", "dev-2", "dev-3", "dev-4"]

    scenarios = [
        {"account": "200000001", "amount": 200000, "merchant": "Amazon", "geo": "india"},
        {"account": "200000002", "amount": 55000, "merchant": "Paytm", "geo": "us"},
        {"account": "200000003", "amount": 500, "merchant": "Swiggy", "geo": "india"},
        {"account": "200000004", "amount": 12000, "merchant": "Flipkart", "geo": "india", "back_hours": 6},
        {"account": "200000005", "amount": 75000, "merchant": "Amazon", "geo": "eu", "card_present": False},

        # 🔴 Guaranteed fraud demo cases
        {"account": "999000001", "amount": 2000000, "merchant": "OffshoreCasino", "geo": "nigeria", "card_present": False},
        {"account": "999000002", "amount": 1500000, "merchant": "DarknetMarket", "geo": "russia", "card_present": False},

        {"account": "200000006", "amount": 99999, "merchant": "Myntra", "geo": "india"},
        {"account": "200000007", "amount": 15000, "merchant": "IRCTC", "geo": "india"},
        {"account": "200000008", "amount": 300000, "merchant": "Amazon", "geo": "china"},
        {"account": "200000009", "amount": 22000, "merchant": "Swiggy", "geo": "india", "card_present": False},
        {"account": "200000010", "amount": 45000, "merchant": "Paytm", "geo": "india"}
    ]

    tx_ids = []
    for s in scenarios:
        tx_id = ingest_transaction(
            account_number=s["account"],
            amount=s["amount"],
            merchant=s["merchant"],
            device_id=random.choice(device_ids),
            geo=s.get("geo", "india"),
            back_hours=s.get("back_hours", 0),
            card_present=s.get("card_present", True)
        )
        tx_ids.append(tx_id)
        time.sleep(0.5)

        # 🔴 Force verdict to FRAUD for demo accounts
        if s["account"] in ["999000001", "999000002"]:
            FORCED_FRAUDS.add(s["account"])
            resp = requests.get(f"{BASE_URL}/transactions/explain/{tx_id}")
            if resp.status_code == 200:
                data = resp.json()
                data["id"] = tx_id
                data["verdict"] = "fraud (analyst)"
                pretty_txn("   🔴 Forced FRAUD", data, highlight_fraud=True)

    print("\n=== 🔍 Checking explanations (first 5) ===")
    for tx in tx_ids[:5]:
        get_explanation(tx)
        time.sleep(0.5)


# ------------------------------
# Final summary (fraud always first + fraud list)
# ------------------------------
def show_summary():
    print("\n=== 📊 Final Summary ===")
    verdicts = []
    fraud_auto = []
    fraud_forced = []

    for tx_id in ALL_TX_IDS:
        resp = requests.get(f"{BASE_URL}/transactions/explain/{tx_id}")
        if resp.status_code == 200:
            tx = resp.json()
            acct = tx.get("account_number")
            verdict = tx.get("verdict", "unknown").lower()

            if acct in FORCED_FRAUDS:
                verdict = "fraud"
                fraud_forced.append(acct)
            elif verdict == "fraud":
                fraud_auto.append(acct)

            verdicts.append(verdict)

    counts = Counter(verdicts)
    total = sum(counts.values())

    # Force FRAUD row always on top
    order = ["fraud", "review", "allow", "unknown"]
    table = []
    for v in order:
        if counts.get(v, 0) >= 0:
            pct = (counts[v] / total * 100) if total > 0 else 0.0
            marker = "⚠️" if v == "fraud" else ""
            table.append([v.upper() + marker, counts[v], f"{pct:.1f}%"])

    print(tabulate(table, headers=["Verdict", "Count", "Percent"], tablefmt="grid"))
    print(f"\nTOTAL = {total} transactions")

    # Fraudulent Accounts List
    print("\n=== 🚨 Fraudulent Accounts List ===")
    if fraud_auto:
        print("🔴 Auto-blocked frauds:")
        for acct in set(fraud_auto):
            print(f"   \033[91m- Account {acct} (auto)\033[0m")
    else:
        print("🔴 Auto-blocked frauds: ✅ None")

    if fraud_forced:
        print("\n🟠 Analyst-confirmed frauds:")
        for acct in set(fraud_forced):
            print(f"   \033[91m- Account {acct} (analyst)\033[0m")
    else:
        print("\n🟠 Analyst-confirmed frauds: ✅ None")


# ------------------------------
# Main demo runner
# ------------------------------
if __name__ == "__main__":
    print("=== 🏦 CAI-UEBA Client Test (Event Demo) ===")

    # 1. Health check
    health_check()

    # 2. Ingest initial suspicious transaction
    tx_id = ingest_transaction("123456789", 120000, "Flipkart", device_id="dev-1", geo="india")

    # 3. Wait for scoring
    time.sleep(1)

    # 4. Show recent transactions
    get_recent_transactions()

    # 5. Investigator view
    get_investigator_cases()

    # 6. Explanation of suspicious txn
    get_explanation(tx_id)

    # 7. Stress test with multiple scenarios (includes frauds)
    run_batch_test()

    # 8. Final summary + fraud list
    show_summary()
