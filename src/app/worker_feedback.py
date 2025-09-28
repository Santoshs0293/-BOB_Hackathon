import asyncio
import json
import redis
import numpy as np
from sklearn.ensemble import IsolationForest
from bson import ObjectId
from .config import settings
from .database import db
from . import scoring

# Redis client
r = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def process_feedback_loop():
    print("🚀 Feedback worker started. Listening on ueba:feedback_queue ...")

    while True:
        try:
            # Blocking pop with timeout
            item = r.brpop("ueba:feedback_queue", timeout=10)
            if not item:
                await asyncio.sleep(1)
                continue

            _, raw = item
            fb = json.loads(raw)
            tx_id = fb.get("tx_id")
            label = fb.get("label")
            analyst = fb.get("analyst", "unknown")
            notes = fb.get("notes", "")

            print(f"📥 Feedback received: tx_id={tx_id}, label={label}")

            # Save feedback into a dedicated collection
            await db.feedback.insert_one({
                "tx_id": ObjectId(tx_id),   # store as proper ObjectId
                "label": label,
                "analyst": analyst,
                "notes": notes,
                "timestamp": scoring.datetime.utcnow()
            })


            # Fetch transaction from Mongo
            tx = await db.transactions.find_one({"_id": ObjectId(tx_id)})
            if not tx:
                print(f"⚠️ Transaction {tx_id} not found in DB.")
                continue

            # Extract feature vector (log(amount), hour)
            hr = tx["timestamp"].hour if tx.get("timestamp") else 0
            val = [np.log1p(abs(tx.get("amount", 0))), float(hr)]
            scoring.ISOF_TRAIN_DATA.append(val)

            # Retrain if enough data
            if len(scoring.ISOF_TRAIN_DATA) >= 50:
                X = np.array(scoring.ISOF_TRAIN_DATA)
                scoring.ISOF_MODEL = IsolationForest(
                    n_estimators=100,
                    contamination=0.01,
                    random_state=42
                )
                scoring.ISOF_MODEL.fit(X)
                print(f"✅ Retrained IsolationForest on {len(scoring.ISOF_TRAIN_DATA)} samples.")

        except Exception as e:
            print(f"❌ Error in feedback loop: {e}")
            await asyncio.sleep(2)

# Entrypoint
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(process_feedback_loop())
