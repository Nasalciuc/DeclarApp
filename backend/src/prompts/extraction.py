"""SAD extraction prompt: schema, content blocks and robust output parsing.

Kept separate from handlers so prompt changes produce clean, reviewable diffs.
"""

import json
import re

IMAGE_FORMATS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg",
                 ".gif": "gif", ".webp": "webp"}
DOC_FORMATS = {".pdf": "pdf"}

OUTPUT_SCHEMA = """
{
  "declaratie":  { "tip": str|null, "numar_referinta": str|null, "data": str|null },
  "parti": {
    "exportator": { "nume": str|null, "adresa": str|null, "cod_fiscal": str|null },
    "importator": { "nume": str|null, "adresa": str|null, "cod_fiscal": str|null }
  },
  "transport": { "tara_expediere": str|null, "tara_destinatie": str|null, "mod_transport": str|null },
  "financiar": { "valuta": str|null, "suma_totala_facturata": number|null, "curs_valutar": number|null },
  "marfuri": [
    {
      "numar_articol": number|null,
      "descriere": str|null,
      "cod_marfa": str|null,
      "tara_origine": str|null,
      "masa_bruta_kg": number|null,
      "masa_neta_kg": number|null,
      "cod_procedura": str|null,
      "valoare_statistica": number|null,
      "pret_articol": number|null,
      "taxe": [ { "tip": str|null, "baza": number|null, "cota": str|null, "suma": number|null } ]
    }
  ]
}
""".strip()

PROMPT = f"""You are extracting data from a customs declaration (Declaratie Vamala / SAD).
The document may be written in Romanian or Russian. Extract every field you can read.

Return ONLY a JSON object with EXACTLY this shape - no markdown, no commentary:

{OUTPUT_SCHEMA}

Rules:
- One entry in "marfuri" per goods item (box 31/32). A declaration may have several.
- "cod_marfa" is the commodity/tariff code (box 33). Digits only.
- Use null for any field you cannot read. Do NOT invent values.
- Numbers must be plain numbers: no thousands separators, dot as decimal.
"""


def content_blocks(raw: bytes, ext: str) -> list:
    """Bedrock Converse content: the document/image block + the prompt."""
    ext = ext.lower()
    if ext in IMAGE_FORMATS:
        block = {"image": {"format": IMAGE_FORMATS[ext],
                           "source": {"bytes": raw}}}
    elif ext in DOC_FORMATS:
        block = {"document": {"format": DOC_FORMATS[ext], "name": "declaration",
                              "source": {"bytes": raw}}}
    else:
        raise ValueError(f"unsupported file type: {ext}; use a PDF or an image")
    return [block, {"text": PROMPT}]


def parse_output(text: str) -> dict:
    """Robustly pull the JSON object out of the model's text output."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return json.loads(text)
