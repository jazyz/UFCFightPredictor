"""Name normalization helpers for joining fighter data from different sources."""

from __future__ import annotations

import re
import unicodedata


NAME_ALIASES = {
    "alatengheili alateng": "alatengheili",
    "asu almabaev": "assu almabayev",
    "asu almabayev": "assu almabayev",
    "beatriz mesquita": "bia mesquita",
    "carlos leal": "carlos leal miranda",
    "daria zheleznyakova": "daria zhelezniakova",
    "darya zheleznyakova": "daria zhelezniakova",
    "dennis buzukia": "dennis buzukja",
    "durko todorovir": "dusko todorovic",
    "ian machado garry": "ian garry",
    "ion curelaba": "ion cutelaba",
    "jan bachowicz": "jan blachowicz",
    "jeong yeong lee": "jeongyeong lee",
    "jose miguel delgado": "jose delgado",
    "king green": "bobby green",
    "lone er kavanagh": "loneer kavanagh",
    "lupita godinez": "loopy godinez",
    "maheshate hayisaer": "maheshate",
    "michael aswell jr": "michael aswell",
    "montserrat rendon": "montse rendon",
    "patricio pitbull": "patricio freire",
    "ronaldo bedoya": "rolando bedoya",
    "rukasz brzeski": "lukasz brzeski",
    "sean o malley": "sean omalley",
    "sergey spivak": "serghei spivac",
    "shara magomedov": "sharabutdin magomedov",
    "stephen erceg": "steve erceg",
    "timothy cuamba": "timmy cuamba",
}

NORMALIZATION_TRANSLATION = str.maketrans({
    "'": "",
    "`": "",
    "´": "",
    "‘": "",
    "’": "",
    "ʼ": "",
    "ʻ": "",
    "Ł": "L",
    "ł": "l",
    "Đ": "D",
    "đ": "d",
    "Ø": "O",
    "ø": "o",
    "ß": "ss",
    "Æ": "AE",
    "æ": "ae",
    "Œ": "OE",
    "œ": "oe",
})
SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


def normalize_name(name: object) -> str:
    translated_name = str(name).translate(NORMALIZATION_TRANSLATION)
    ascii_name = (
        unicodedata.normalize("NFKD", translated_name)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    cleaned = re.sub(r"[^a-z0-9]+", " ", ascii_name.strip().lower())
    parts = [
        part
        for part in cleaned.split()
        if part not in SUFFIXES
    ]
    return " ".join(parts)


def lookup_keys(name: object) -> list[str]:
    normalized = normalize_name(name)
    keys = [normalized]
    alias = NAME_ALIASES.get(normalized)
    if alias and alias not in keys:
        keys.append(alias)
    return keys


def canonical_name(name: object) -> str:
    keys = lookup_keys(name)
    return keys[-1] if keys else ""
