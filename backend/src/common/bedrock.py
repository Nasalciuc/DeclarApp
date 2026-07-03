"""Single Bedrock entry point (Converse API). Tests monkeypatch `converse`."""

import os

import boto3
from botocore.config import Config


_CLIENT = None


def _client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = boto3.client(
            "bedrock-runtime",
            config=Config(read_timeout=180, retries={"max_attempts": 3}))
    return _CLIENT


def converse_raw(content: list, max_tokens: int = 4000,
                 temperature: float = 0) -> dict:
    """Full Converse response (the CLI uses it to print token usage)."""
    return _client().converse(
        modelId=os.environ["BEDROCK_MODEL_ID"],
        messages=[{"role": "user", "content": content}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature})


def converse(content: list, max_tokens: int = 4000,
             temperature: float = 0) -> str:
    """Model text output for a single-turn request."""
    response = converse_raw(content, max_tokens, temperature)
    return response["output"]["message"]["content"][0]["text"]
