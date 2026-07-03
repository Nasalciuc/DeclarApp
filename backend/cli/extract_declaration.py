"""Local dev CLI: send a declaration (PDF/image) to Bedrock, print the JSON.

Usage:
    python extract_declaration.py path/to/declaration.pdf
    python extract_declaration.py scan.png -o result.json

Requires AWS credentials (`aws configure`) and env:
    BEDROCK_MODEL_ID  e.g. eu.anthropic.claude-sonnet-4-6
    AWS_REGION        e.g. eu-central-1

Cost: a few US cents per declaration.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common.bedrock import converse_raw  # noqa: E402
from prompts.extraction import content_blocks, parse_output  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract a customs declaration to JSON via AWS Bedrock.")
    parser.add_argument("file", help="Path to the declaration (PDF or image).")
    parser.add_argument("-o", "--output", help="Write JSON here, not stdout.")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        sys.exit(f"File not found: {path}")
    if not os.environ.get("BEDROCK_MODEL_ID"):
        sys.exit("Set BEDROCK_MODEL_ID (see Bedrock console > Model access).")

    try:
        response = converse_raw(content_blocks(path.read_bytes(), path.suffix))
        text = response["output"]["message"]["content"][0]["text"]
        usage = response.get("usage", {})
        print(f"[tokens] in={usage.get('inputTokens')} "
              f"out={usage.get('outputTokens')}", file=sys.stderr)
        data = parse_output(text)
    except Exception as err:  # noqa: BLE001
        sys.exit(f"Extraction failed: {err}")

    output = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
