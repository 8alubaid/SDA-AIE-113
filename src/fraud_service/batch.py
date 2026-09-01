import os

import pandas as pd

from fraud_service.adapters.sklearn_model import SklearnModel
from fraud_service.domain.entities import Transaction
from fraud_service.service.scorer import FraudScorer

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


if __name__ == "__main__":
    main()