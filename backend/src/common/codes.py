"""Structural validators: tariff code shape, ISO countries, ISO currencies.

Pure functions and static sets - no network, no AWS.
Unknown-but-well-formed values return UNCERTAIN instead of FAIL, so a gap in
our static sets never hard-blocks a declaration.
"""

import re

from .models import CheckStatus

# ISO 3166-1 alpha-2 (officially assigned) + XK (Kosovo, common in trade docs)
ISO_COUNTRIES = set(
    "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI "
    "BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN "
    "CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK "
    "FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM "
    "HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN "
    "KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK "
    "ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP "
    "NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW "
    "SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF "
    "TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI "
    "VN VU WF WS YE YT ZA ZM ZW XK".split()
)

# ISO 4217 - the currencies realistically seen on MD import/export docs.
ISO_CURRENCIES = set(
    "MDL EUR USD RON UAH RUB GBP CHF JPY CNY TRY PLN HUF CZK BGN SEK NOK DKK "
    "CAD AUD NZD INR BRL MXN ZAR KRW SGD HKD ILS AED SAR EGP GEL AMD AZN KZT "
    "BYN RSD MKD ALL BAM ISK THB VND IDR MYR PHP TWD CLP COP PEN ARS UYU MAD "
    "TND DZD NGN KES GHS XOF XAF QAR KWD BHD OMR JOD IQD PKR BDT LKR UZS KGS "
    "TJS TMT MNT ETB TZS UGX ZMW MZN AOA BWP NAD MUR".split()
)

_TARIFF_LINE = re.compile(r"^\d{8,9}$")


def normalize_code(code) -> str:
    """'8471.30 00' -> '84713000'. Tariff PKs are digits-only."""
    return re.sub(r"\D", "", str(code or ""))


def is_tariff_line(code: str) -> bool:
    """True for an 8-9 digit tariff line (CN 8 digits / national 9)."""
    return bool(_TARIFF_LINE.match(code or ""))


def check_country(value) -> dict:
    """ISO 3166 alpha-2 check. Missing -> UNCERTAIN; malformed/unknown -> FAIL."""
    if not value:
        return {"status": CheckStatus.UNCERTAIN, "reason": "country not extracted"}
    code = str(value).strip().upper()
    if code in ISO_COUNTRIES:
        return {"status": CheckStatus.PASS, "value": code}
    return {"status": CheckStatus.FAIL, "value": code,
            "reason": f"'{code}' is not an ISO 3166 country code"}


def check_currency(value) -> dict:
    """ISO 4217 check. Well-formed but outside our set -> UNCERTAIN."""
    if not value:
        return {"status": CheckStatus.UNCERTAIN, "reason": "currency not extracted"}
    code = str(value).strip().upper()
    if code in ISO_CURRENCIES:
        return {"status": CheckStatus.PASS, "value": code}
    if re.fullmatch(r"[A-Z]{3}", code):
        return {"status": CheckStatus.UNCERTAIN, "value": code,
                "reason": f"'{code}' not in the known currency set"}
    return {"status": CheckStatus.FAIL, "value": code,
            "reason": f"'{code}' is not an ISO 4217 currency code"}
