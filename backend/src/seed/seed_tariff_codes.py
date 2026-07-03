"""Seed `tariff_codes` from a CSV export of the integrated customs tariff.

Expected CSV columns (header row required):
  code, description_ro, description_ru, unit, duty_rate, vat_rate,
  excise_rate, excise_amount_per_kg, chapter, notes

Usage:
  python seed_tariff_codes.py --csv seed/sample_tariff.csv
  python seed_tariff_codes.py --csv tarif_integrat.csv --chapters 84,85
  python seed_tariff_codes.py --csv ... --dry-run

The bundled sample_tariff.csv is DIDACTIC data, not the official tariff.
Replace it with the real export from Serviciul Vamal before any real use.
"""

import argparse
import csv
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

# Windows consoles often default to cp1252, which cannot print the Romanian
# diacritics in tariff descriptions; degrade gracefully instead of crashing.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/src

from common.codes import is_tariff_line, normalize_code  # noqa: E402
from common.dynamo import tariff_table  # noqa: E402


def _dec(value: str) -> Decimal | None:
    value = (value or "").strip().replace(",", ".")
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def build_item(row: dict) -> dict | None:
    code = normalize_code(row.get("code"))
    if not is_tariff_line(code):
        print(f"  skip: '{row.get('code')}' is not an 8-9 digit tariff line")
        return None
    item: dict = {"code": code}
    for field in ("description_ro", "description_ru", "unit", "chapter", "notes"):
        value = (row.get(field) or "").strip()
        if value:
            item[field] = value
    for field in ("duty_rate", "vat_rate"):
        value = _dec(row.get(field))
        if value is not None:
            item[field] = value
    excise: dict = {}
    rate = _dec(row.get("excise_rate"))
    amount = _dec(row.get("excise_amount_per_kg"))
    if rate is not None:
        excise["rate"] = rate
    elif amount is not None:
        excise.update({"amount": amount, "per": "kg"})
    if excise:
        item["excise"] = excise
    return item


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Tariff CSV path")
    parser.add_argument("--chapters",
                        help="Comma-separated chapter filter, e.g. 84,85")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and report, write nothing")
    args = parser.parse_args()

    chapters = ({c.strip().zfill(2) for c in args.chapters.split(",")}
                if args.chapters else None)

    items = []
    with open(args.csv, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            item = build_item(row)
            if item is None:
                continue
            if chapters and item["code"][:2] not in chapters:
                continue
            items.append(item)

    print(f"parsed {len(items)} tariff lines"
          + (f" (chapters {sorted(chapters)})" if chapters else ""))
    if args.dry_run:
        for item in items[:5]:
            print(" ", item)
        return

    table = tariff_table()
    with table.batch_writer(overwrite_by_pkeys=["code"]) as batch:
        for item in items:
            batch.put_item(Item=item)
    print(f"wrote {len(items)} items to {table.name}")
    print("NOTE: sample data is didactic - load the official tariff export "
          "from Serviciul Vamal before real use.")


if __name__ == "__main__":
    main()
