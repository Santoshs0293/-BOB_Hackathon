#  CAI-Powered UEBA (Fraud Detection Platform)

This project implements a **CPU-friendly prototype** of a CAI-Powered User & Entity Behavior Analytics (UEBA) system.  
It integrates **rule-based detection, anomaly ML (IsolationForest), graph heuristics, causal analysis stubs, and analyst feedback loops**.  


##  Features

- **FastAPI Backend** (`src/app/main.py`)
  - REST APIs for transactions, investigators, and explanations
- **Transaction Scoring**
  - Rules (amount thresholds, time anomalies, device/card checks)
  - Machine Learning (Isolation Forest, retrains from feedback)
  - Graph Analysis (NetworkX-based device-account relationships)
  - Causal AI stub (using DoWhy/EconML placeholders)
  - Explanations (why a transaction was flagged, causal summary)
- **Feedback Loop**
  - Analyst labels (`fraud` / `legit`) are stored
  - Redis queue for asynchronous retraining
  - Background worker retrains IsolationForest when enough data
- **Investigator Dashboard API**
  - View suspicious/review cases
  - Analyst labels + notes visible
- **Client Script (`client.py`)**
  - Runs an end-to-end test
  - Ingests transactions
  - Queries recent transactions
  - Explains individual transactions
  - Submits feedback
  - Runs batch tests with multiple conditions


## 📂 Project Structure

```
backend/
│── src/app/
│   ├── main.py              # FastAPI entrypoint
│   ├── database.py          # Mongo connection
│   ├── config.py            # Settings (Mongo, Redis, etc.)
│   ├── routers/
│   │   ├── transactions.py  # Ingest, recent, explain, feedback
│   │   ├── investigators.py # Investigator case APIs
│   │   └── auth.py          # (stub for future user auth)
│   ├── scoring.py           # Rules, ML, Graph, causal analysis
│   ├── graph_store.py       # Graph (NetworkX)
│   ├── graph_detector.py    # Suspicious account detection
│   ├── causal_ai.py         # Stub for causal effect estimation
│   ├── explainability.py    # Human-readable explanation synthesis
│   ├── worker_feedback.py   # Background retrainer (CPU only)
│   └── assistant.py         # Natural language explainer stub
│
├── client.py                # End-to-end test client
├── requirements.txt         # Python dependencies
└── README.md                # This file
```


## ⚙️ Requirements

- **Python 3.10+**
- **MongoDB** (running locally or remote)
- **Redis** (for feedback queue)
- **Virtual environment recommended**

---
## 🔧 Setup

1. Clone repo:
   ```bash
   git clone https://github.com/your-org/ueba-fraud.git
   cd backend
   ```

2. Create venv & install deps:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install -r requirements.txt --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host=files.pythonhosted.org
   ```

3. Configure `.env` file:

   ```ini
   MONGODB_URL=mongodb://localhost:27017
   MONGO_DB_NAME=ueba_db
   REDIS_URL=redis://localhost:6379
   ```

4. Run MongoDB & Redis locally (e.g. via Docker):

   ```bash
   docker run -d -p 27017:27017 mongo
   docker run -d -p 6379:6379 redis
   ```

---

## ▶️ Running the System

### 1. Start backend (FastAPI):

```bash
uvicorn src.app.main:app --reload
```

Server runs on: `http://127.0.0.1:8000`

---

### 2. Run client test:

```bash
python3 client.py
```

This will:

* ✅ Health check
* ✅ Ingest transactions
* ✅ Query recent transactions
* ✅ Explain decisions
* ✅ Send feedback
* ✅ Run batch scenarios

---

### 3. Run background feedback worker:

```bash
python3 -m src.app.worker_feedback
```

This will:

* Listen on `ueba:feedback_queue`
* Consume analyst feedback
* Update training data
* Retrain `IsolationForest` when enough samples

---

## 📡 API Endpoints

### Health

* `GET /` → Backend running status

### Transactions

* `POST /transactions/ingest` → Ingest new transaction
* `GET /transactions/recent?limit=5` → Recent transactions
* `GET /transactions/explain/{tx_id}` → Full explanation of decision
* `POST /transactions/feedback?tx_id=...&analyst=...&label=fraud&notes=...`

### Investigator

* `GET /investigators/cases` → Analyst cases

---

## 🧪 Example Workflow

1. **Ingest a suspicious transaction**

   ```bash
   curl -X POST http://127.0.0.1:8000/transactions/ingest    -H "Content-Type: application/json"    -d '{"account_number":"123456789","amount":120000,"currency":"INR","merchant":"Flipkart","device":{"device_id":"dev-1"},"metadata":{"geo":"india"}}'
   ```

2. **Check recent transactions**

   ```bash
   curl "http://127.0.0.1:8000/transactions/recent?limit=5"
   ```

3. **Explain why it was flagged**

   ```bash
   curl "http://127.0.0.1:8000/transactions/explain/{tx_id}"
   ```

4. **Submit analyst feedback**

   ```bash
   curl -X POST "http://127.0.0.1:8000/transactions/feedback?tx_id={tx_id}&analyst=santosh&label=fraud&notes=confirmed"
   ```

5. **Worker retrains model**

   ```
   🚀 Feedback worker started. Listening on ueba:feedback_queue ...
   📥 Feedback received: tx_id=..., label=fraud
   ✅ Retrained IsolationForest on 50 samples.
   ```

---

## 📊 Scoring Pipeline

* **Rules** → amount thresholds, odd-hour checks, card presence
* **ML (IsolationForest)** → anomaly detection on `log(amount), hour`
* **Graph Heuristics** → suspicious account-device clusters
* **Causal Stub** → `not enough data` (future: DoWhy/EconML)
* **Explanation** → Natural language breakdown

---

## 🛠️ Next Steps

* [ ] Persist training data in MongoDB (not just memory)
* [ ] Replace heuristic graph with node2vec/DeepWalk embeddings
* [ ] Integrate DoWhy/EconML for causal effect estimation
* [ ] Add natural-language Analyst Assistant (LLM)
* [ ] Build dashboard frontend (React/Next.js)

---

## 🤝 Contributors

* **Santosh Kumar Singh** – PhD Scholar, IIT Kanpur