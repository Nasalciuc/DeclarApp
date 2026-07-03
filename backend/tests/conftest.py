"""Test bootstrap: put backend/src on the path, set fake AWS env."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("DECLARATIONS_TABLE", "declarations")
os.environ.setdefault("TARIFF_TABLE", "tariff_codes")
os.environ.setdefault("BUCKET", "customs-test-bucket")
os.environ.setdefault("REPORTS_BUCKET", "customs-test-bucket")
os.environ.setdefault("ENABLE_SEMANTIC", "0")
os.environ.setdefault("BEDROCK_MODEL_ID", "test-model")
