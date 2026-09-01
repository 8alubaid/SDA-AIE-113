<<<<<<< HEAD
"""Wiring happens HERE and only here - this is the 'composition root' idea
from lecture. Every other file only knows about protocols/interfaces."""
import time
=======
import os
>>>>>>> personal/main

import pandas as pd

from fraud_service.adapters.sklearn_model import SklearnModel
from fraud_service.domain.entities import Transaction
from fraud_service.service.scorer import FraudScorer

<<<<<<< HEAD

def main() -> None:
    t0 = time.perf_counter()
    model = SklearnModel.load("models/fraud_xgb_v3.joblib")
    print(f"Loaded model fraud_xgb {model.model_version} in {time.perf_counter()-t0:.2f}s")

    scorer = FraudScorer(model=model, block_threshold=0.85)

    df = pd.read_csv("data/transactions_sample.csv")
    counts = {"block": 0, "review": 0, "allow": 0}
    rows = []
    for record in df.to_dict("records"):
        txn = Transaction(
            transaction_id=record["transaction_id"], amount_sar=record["amount_sar"],
            channel=record["channel"], merchant_category=record["merchant_category"],
            customer_id=record["customer_id"], timestamp=record["timestamp"])
        decision = scorer.score(txn)
        counts[decision.value] += 1
        rows.append({"transaction_id": txn.transaction_id, "decision": decision.value})

    pd.DataFrame(rows).to_csv("scored.csv", index=False)
    print(f"Scored {len(rows):,} transactions -> scored.csv "
          f"(block: {counts['block']}, review: {counts['review']}, allow: {counts['allow']})")
=======
DATA_PATH = "data/transactions_sample.csv"
MODEL_PATH = "models/fraud_xgb_v3.joblib"
OUTPUT_PATH = "scored.csv"


def main() -> None:
    model = SklearnModel.load(MODEL_PATH)

    block_threshold = float(
        os.environ.get("THRESHOLD", "0.85")
    )

    scorer = FraudScorer(
        model=model,
        block_threshold=block_threshold,
    )

    df = pd.read_csv(DATA_PATH)

    results = []

    for _, row in df.iterrows():
        txn = Transaction(
            transaction_id=str(row["transaction_id"]),
            amount_sar=float(row["amount_sar"]),
            channel=str(row["channel"]),
            merchant_category=str(row["merchant_category"]),
            timestamp=pd.to_datetime(row["timestamp"]).to_pydatetime(),
        )

        score = scorer.score(txn)

        results.append(
            {
                "transaction_id": score.transaction_id,
                "score": score.probability,
                "decision": score.decision.value,
            }
        )

    scored = pd.DataFrame(results)

    scored.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print(f"loaded {model.model_version}")
    print(scored["decision"].value_counts())
    print(f"wrote {OUTPUT_PATH}")
>>>>>>> personal/main


if __name__ == "__main__":
    main()