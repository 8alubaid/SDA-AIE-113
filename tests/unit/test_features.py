import pytest


@pytest.mark.unit
def test_feature_names_are_stable(sample_txn):
    assert set(sample_txn.to_features().values) == {
        "amount_log", "channel", "mcc", "hour_of_day", "is_night"
    }

@pytest.mark.unit
def test_night_flag(sample_txn):
    assert sample_txn.to_features().values["is_night"] == 1   # 03:30 is night


@pytest.mark.unit
def test_mcc_normalised_from_messy_input(sample_txn):
    data = {**sample_txn.model_dump(), "merchant_category": " electronics "}
    txn = sample_txn.__class__(**data)
    assert txn.to_features().values["mcc"] == "ELECTRONICS"