"""Runtime configuration, read once at startup.

Env-var names stay compatible with Lab 1's batch entrypoint, so `THRESHOLD`
means the same thing whether you run the batch job or the API.
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        protected_namespaces=(),
    )

    model_path: str = Field(
        default="models/fraud_xgb_v3.joblib",
        validation_alias="MODEL_PATH",
    )
    block_threshold: float = Field(
        default=0.85,
        validation_alias="THRESHOLD",
        gt=0.0,
        le=1.0,
    )
    warmup: bool = Field(
        default=True,
        validation_alias="WARMUP",
    )
    log_level: str = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
    )
