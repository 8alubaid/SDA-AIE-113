"""Wiring happens HERE and only here - this is the 'composition root' idea
from lecture. Every other file only knows about protocols/interfaces."""
import time

import pandas as pd

from fraud_service.adapters.sklearn_model import SklearnModel
from fraud_service.domain.entities import Transaction
from fraud_service.service.scorer import FraudScorer


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


if __name__ == "__main__":
    main()