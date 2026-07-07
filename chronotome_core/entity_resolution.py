"""Institutional and geographic entity resolution from the Chronotome notebook."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pycountry


COUNTRY_ALIASES = {
    "PEOPLES R CHINA": "China", "PEOPLES R. CHINA": "China", "PEOPLES REP CHINA": "China",
    "PEOPLES REPUBLIC CHINA": "China", "UNITED STATES OF AMERICA": "United States",
    "USA": "United States", "U.S.A.": "United States", "UNITED KINGDOM": "United Kingdom",
    "ENGLAND": "United Kingdom", "SCOTLAND": "United Kingdom", "NORTHERN IRELAND": "United Kingdom",
    "UK": "United Kingdom", "U.K.": "United Kingdom", "WALES": "United Kingdom",
    "NORTH IRELAND": "United Kingdom", "TURKEY": "Republic of Türkiye",
    "TURKIYE": "Republic of Türkiye", "U ARAB EMIRATES": "United Arab Emirates",
    "RUSSIA": "Russia", "RUSSIAN FEDERATION": "Russia", "VATICAN": "Vatican",
    "BOSNIA & HERCEG": "Bosnia and Herzegovina", "BOSNIA & HERCEGOVINA": "Bosnia and Herzegovina",
    "BRUNEI": "Brunei", "DOMINICAN REP": "Dominican Republic", "SOUTH KOREA": "South Korea",
    "KOREA": "South Korea", "REP OF KOREA": "South Korea",
}

INSTITUTION_ALIASES_BACKUP = {
    "California Institute of Technology": ["caltech", "california institute technology"],
    "Chinese Academy of Sciences": ["chinese academy science", "university chinese academy science", "ucas"],
    "University of California System": ["university california"],
    "University of California Berkeley": ["university calif berkeley", "uc berkeley"],
    "University of California Los Angeles": ["ucla"], "University of California Irvine": ["uc irvine"],
    "Johns Hopkins University": ["johns hopkins university", "johns hopkins univ"],
    "Leiden University": ["leiden university", "leiden univ"], "NASA": ["nasa"],
    "NASA Ames Research Center": ["nasa ames research center"], "INAF": ["inaf"],
    "University of Arizona": ["university arizona", "univ arizona"],
    "Cornell University": ["cornell university", "cornell univ"],
    "University Paris Saclay": ["university paris saclay"], "MIT": ["mit"],
    "ETH Zurich": ["eth zurich", "eth zuerich", "eidgenossische technische hochschule zurich"],
    "KU Leuven": ["ku leuven", "katholieke universiteit leuven"],
    "DLR": ["dlr", "german aerospace center", "deutsches zentrum fur luft und raumfahrt"],
    "European Space Agency (ESA)": ["esa", "european space agency"], "CNRS": ["cnrs"],
    "CNR": ["cnr"], "UFMG": ["ufmg", "federal university of minas gerais"],
    "Sternberg Astronomical Institute": ["sternberg astron inst"],
    "Toulouse School of Economics": ["toulouse sch econ"],
    "Institute of Planetology and Astrophysics of Grenoble": ["inst planetol & astrophys grenoble osug a"],
    "American Museum of Natural History": ["american museum natural history"],
    "Natural History Museum": ["natural history museum"],
    "University of Munster": ["westfalische wilhelms universitat"],
    "Academy of Sciences of the Czech Republic": ["academy of sciences cr"],
    "National Autonomous University of Mexico": ["univ nacl autonoma mexico"],
    "European Space Operations Centre": ["esoc", "european space operat ctr esa esoc"],
    "University of La Laguna": ["university la laguna"],
    "Instituto de Astrofísica de Canarias": ["institute astrofis canarias"],
    "Beihang University": ["beihang university"],
    "Center for Astrophysics | Harvard & Smithsonian": ["center astrophys harvard & smithsonian"],
    "Chalmers University of Technology": ["chalmers university technology"],
    "Delft University of Technology": ["delft university technology"],
    "Austrian Academy of Sciences": ["austrian academy science"],
    "Dublin Institute for Advanced Studies": ["dublin institute adv studies"],
    "European Space Astronomy Centre (ESAC)": ["esac campus"],
    "Complutense University of Madrid": ["university complutense madrid"],
    "Carnegie Institution for Science": ["carnegie institute science"],
    "Aristotle University of Thessaloniki": ["aristotle university thessaloniki"],
    "Eötvös Loránd University": ["eotvos lorand university"],
    "European Southern Observatory (ESO)": ["european southern observatory"],
}

ABBREV_REPLACEMENTS = {
    r"\bEngn\b": "Engineering", r"\bSci\b": "Science", r"\bTech\b": "Technology",
    r"\bTechnol\b": "Technology", r"\bTecnol\b": "Tecnologia", r"\bColl\b": "College",
    r"\bAcad\b": "Academy", r"\bInst\b": "Institute", r"\bUniv\b": "University",
    r"\bHosp\b": "Hospital", r"\bDist\b": "District", r"\bGen\b": "General",
    r"\bNatl\b": "National", r"\bPolytech\b": "Polytechnic", r"\bProv\b": "Provincial",
    r"\bDept\b": "Department", r"\bLab\b": "Laboratory", r"\bPolitecn\b": "Politecnico",
    r"\bRes\b": "Research", r"\bFed\b": "Federal", r"\bAerosp\b": "Aerospace",
    r"\bAgcy\b": "Agency", r"\bCtr\b": "Center", r"\bInt\b": "International",
    r"\bEduc\b": "Education", r"\bNacl\b": "Nacional", r"\bNazl\b": "Nazionale",
    r"\bGeofis\b": "Geofisica", r"\bVulcanol\b": "Vulcanologia", r"\bObsv\b": "Observatory",
    r"\bObserv\b": "Observatory", r"\bOperat\b": "Operations", r"\bIst\b": "Istituto",
    r"\bSez\b": "Sezione", r"\bDef\b": "Defense", r"\bGeosci\b": "Geoscience",
    r"\bGeol\b": "Geology", r"\bFis\b": "Fisica", r"\bSch\b": "School",
    r"\bEcon\b": "Economics", r"\bAppl\b": "Applied", r"\bNat\b": "Natural",
    r"\bHist\b": "History", r"\bAssoc\b": "Association", r"\bAstrobiol\b": "Astrobiology",
    r"\bMed\b": "Medicine", r"\bMin\b": "Ministry", r"\bEnvironm\b": "Environmental",
    r"\bAstrofis\b": "Astrofisica",
}

ACRONYM_FIXES = {
    "Nasa": "NASA", "Cnrs": "CNRS", "Esa": "ESA", "Jaxa": "JAXA", "Cnr": "CNR",
    "Csic": "CSIC", "Inaf": "INAF", "Unesp": "UNESP", "Unifesp": "UNIFESP", "Mit": "MIT",
    "Inta": "INTA", "Isas": "ISAS", "Cnes": "CNES", "Ukri": "UKRI", "Stfc": "STFC",
    "Ucl": "UCL", "Eth": "ETH", "Ku": "KU", "Osug": "OSUG", "Ufmg": "UFMG",
    "Ucla": "UCLA", "Dlr": "DLR", "Kfki": "KFKI", "Cicese": "CICESE",
    "Esac": "ESAC", "Eso": "ESO", "Asi": "ASI",
}

MAX_PLANCK_PATTERN = re.compile(r"\bmax\s*(?:planck)?\s*(?:institute|inst)?\b", re.I)
CSIC_PATTERN = re.compile(r"\b(?:csic|inta|consejo superior de investigaciones|centro de astrobiologia)\b", re.I)


@dataclass
class ResolutionStats:
    abbreviations: Counter = field(default_factory=Counter)
    aliases: Counter = field(default_factory=Counter)
    complex_patterns: Counter = field(default_factory=Counter)
    unresolved_countries: Counter = field(default_factory=Counter)


def create_lookup_key(text) -> str:
    """Create the article-insensitive lookup key used by the notebook."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"\b(of|the|for|and|an|a)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _canonicalize_display_name(name: str) -> str:
    clean = name.strip()
    if clean.islower():
        return clean.upper() if len(clean) <= 4 else clean.title()
    return clean


def _read_json_bytes(uploaded_file) -> tuple[str, bytes]:
    if uploaded_file is None:
        path = Path(__file__).with_name("institutions.json")
        if path.exists():
            return "Bundled Zenodo institutions.json", path.read_bytes()
        return "Embedded backup aliases", json.dumps(
            INSTITUTION_ALIASES_BACKUP, ensure_ascii=False, indent=2
        ).encode("utf-8")
    name = getattr(uploaded_file, "name", "institutions.json")
    if hasattr(uploaded_file, "getvalue"):
        return name, uploaded_file.getvalue()
    return name, uploaded_file.read()


def validate_institution_alias_json(uploaded_file=None) -> dict:
    """Validate a canonical-name → alias-list JSON and return its active lookup."""
    name, content = _read_json_bytes(uploaded_file)
    try:
        data = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"'{name}' is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(data, dict) or not data:
        raise ValueError("institutions.json must be a non-empty object mapping canonical names to alias lists.")
    invalid = []
    for canonical, aliases in data.items():
        if not isinstance(canonical, str) or not canonical.strip():
            invalid.append(f"Invalid canonical name: {canonical!r}")
        if not isinstance(aliases, list) or any(not isinstance(alias, str) for alias in aliases):
            invalid.append(f"'{canonical}' must map to a list of strings.")
    if invalid:
        raise ValueError("Invalid institutions.json structure. " + " ".join(invalid[:5]))

    flattened: dict[str, str] = {}
    collisions: list[dict] = []

    def safe_put(key: str, canonical: str, origin: str):
        if not key:
            return
        if key in flattened and flattened[key] != canonical:
            collisions.append({"Lookup key": key, "Kept canonical": flattened[key],
                               "Conflicting canonical": canonical, "Origin": origin})
            return
        flattened[key] = canonical

    json_canonicals = set()
    alias_count = 0
    blank_aliases = 0
    for official_name, aliases in data.items():
        canonical = _canonicalize_display_name(official_name)
        json_canonicals.add(canonical)
        safe_put(create_lookup_key(canonical), canonical, "JSON canonical")
        for alias in aliases:
            if not alias.strip():
                blank_aliases += 1
                continue
            safe_put(create_lookup_key(alias), canonical, "JSON alias")
            alias_count += 1

    backup_added = 0
    backup_ignored = []
    for backup_canonical, aliases in INSTITUTION_ALIASES_BACKUP.items():
        backup_key = create_lookup_key(backup_canonical)
        if backup_key not in flattened:
            backup_ignored.append(backup_canonical)
            continue
        true_canonical = flattened[backup_key]
        for alias in aliases:
            key = create_lookup_key(alias)
            if key not in flattened:
                flattened[key] = true_canonical
                backup_added += 1
            elif flattened[key] != true_canonical:
                collisions.append({"Lookup key": key, "Kept canonical": flattened[key],
                                   "Conflicting canonical": true_canonical, "Origin": "Backup enrichment"})
    return {
        "name": name, "content": content, "data": data, "lookup": flattened,
        "summary": {
            "Alias source": name, "Canonical institutions": len(json_canonicals),
            "JSON aliases": alias_count, "Active lookup entries": len(flattened),
            "Blank aliases ignored": blank_aliases, "Backup aliases added": backup_added,
            "Backup canonicals ignored": len(backup_ignored), "Alias collisions": len(collisions),
        },
        "collisions": pd.DataFrame(collisions),
        "backup_ignored": pd.DataFrame({"Backup canonical ignored": backup_ignored}),
    }


def normalize_diacritics(text: str) -> str:
    if not isinstance(text, str):
        return text
    return "".join(char for char in unicodedata.normalize("NFD", text) if not unicodedata.combining(char))


def remove_random_punctuation(text: str) -> str:
    if not isinstance(text, str):
        return text
    text = re.sub(r"\.\s+(of|the|a|an)\b", r" \1", text, flags=re.I)
    text = re.sub(r"\.+", ".", text)
    text = re.sub(r"\s+\.", ".", text)
    text = re.sub(r"\.(\s+|$)", "", text)
    text = re.sub(r"^\)|\($", "", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def apply_abbrev_replacements(text: str, stats: ResolutionStats) -> str:
    for pattern, replacement in ABBREV_REPLACEMENTS.items():
        text, count = re.subn(pattern, replacement, text, flags=re.I)
        if count:
            clean_pattern = pattern.replace("\\b", "")
            stats.abbreviations[f"{clean_pattern} → {replacement}"] += count
    return text


def standardize_institution_name(institution, lookup: dict[str, str], stats: ResolutionStats):
    """Standardize an extracted institution using notebook rules and aliases."""
    if pd.isna(institution) or not str(institution).strip():
        return None
    clean = normalize_diacritics(str(institution))
    clean = apply_abbrev_replacements(remove_random_punctuation(clean), stats)
    lower = clean.lower()
    if "eth" in lower and "zurich" in lower:
        return "ETH Zurich"
    if "ku leuven" in lower or "katholieke universiteit leuven" in lower:
        return "KU Leuven"
    if "academy of sciences cr" in lower:
        return "Academy of Sciences of the Czech Republic"
    if "esoc" in lower or "european space operat" in lower:
        return "European Space Operations Centre"
    if MAX_PLANCK_PATTERN.search(lower):
        stats.complex_patterns["Max Planck Pattern"] += 1
        return "Max Planck Institute"
    if CSIC_PATTERN.search(lower):
        stats.complex_patterns["CSIC/INTA Pattern"] += 1
        return "CSIC"
    if "ucla" in lower:
        return "University of California Los Angeles"
    if "dlr" in lower:
        return "DLR"
    key = create_lookup_key(lower)
    if key in lookup:
        canonical = lookup[key]
        stats.aliases[f"{key} → {canonical}"] += 1
        return canonical
    final = re.sub(r"\s{2,}", " ", clean.title()).strip()
    non_acronyms = {"The", "And", "For", "New", "Los", "San", "Via", "Rue", "Des", "Les", "Der",
                    "Und", "Fur", "Univ", "Inst", "Coll", "Dept", "Lab", "Cent", "Sect", "Unit",
                    "Area", "City", "Town", "Park", "Road", "Lane", "Blvd", "Pkwy", "East", "West",
                    "Main", "High"}
    words = []
    for word in final.split():
        plain = re.sub(r"[^\w]", "", word)
        words.append(word.upper() if 3 <= len(plain) <= 4 and word not in non_acronyms else word)
    final = " ".join(words)
    for wrong, right in ACRONYM_FIXES.items():
        final = re.sub(r"\b" + wrong + r"\b", right, final)
    return final or None


def clean_affiliations(affiliation):
    if pd.isna(affiliation):
        return None
    text = str(affiliation).replace("&amp;", "&")
    text = re.sub(r"\[.*?\]", "", text)
    text = remove_random_punctuation(normalize_diacritics(text))
    return re.sub(r"\s*,\s*", ", ", text.strip())


def extract_institution_custom(affiliation):
    """Select the most institution-like comma component using notebook weights."""
    if pd.isna(affiliation) or not str(affiliation).strip():
        return None
    parts = [re.sub(r"\s*\(.*?\)", "", part.strip()) for part in str(affiliation).split(",") if part.strip()]
    if not parts:
        return None
    institution_keywords = ["university", "college", "institute", "polytechnic", "academy", "ecole",
        "school", "universidad", "universitas", "universiti", "company", "center", "hospital", "agency",
        "universidade", "universitat", "universita", "universite", "unesp", "centro", "observatory",
        "observatorio", "systems", "instituto", "institution", "politecnico", "minister", "ministero",
        "museum", "museo", "zentrum"]
    high_confidence = ["eth zurich", "dlr", "ucla", "ufmg", "cicese", "kfki", "uc irvine",
                       "ku leuven", "caltech", "mit"]

    def score(part):
        lower = part.lower()
        value = -50 if re.match(r"^\s*\d+", lower) else 0
        for indicator in ["boulevard", "street", "avenue", "box", "blvd", "pkwy", "hwy", "road", "rd",
                          "drive", "dr", "suite", "floor", "ste", "rue", "way", "viale", "esp", "pr",
                          "str", "strasse", "ave", "av", "avenida", "allee"]:
            if re.search(r"\b" + indicator + r"\b", lower): value -= 20
        weighted = {"nasa": 20, "cnrs": 15, "unifesp": 15, "museum": 15, "museo": 15,
                    "zentrum": 10, "dlr": 15, "ucla": 15, "ufmg": 15, "cicese": 15, "kfki": 15,
                    "uc irvine": 15, "ministero": 15, "eth zurich": 35, "esa": 20, "jaxa": 20}
        for term, weight in weighted.items():
            if term in lower: value += weight
        if re.search(r"\bcnr\b", lower) and len(part) < 10: value += 15
        if (re.search(r"\beth\b", lower) and "zurich" in lower) or "ku leuven" in lower: value += 15
        for term in ["university", "universidad", "universitas", "universidade", "universiti",
                     "universitat", "universita", "universite"]:
            if re.search(r"\b" + term + r"\b", lower): value += 40
        if re.search(r"\buniv\b", lower) and value > -15: value += 40
        for term, weight in {"college": 2, "institute": 2, "instituto": 2, "polytechnic": 2,
                             "politecnico": 2, "academy": 2, "ecole": 2, "school": 3, "center": 1.5,
                             "centro": 1.5, "observatory": 1.5, "observatorio": 1.5, "institution": .5,
                             "hospital": 1, "company": .5, "agency": .5, "systems": .5,
                             "technology": .1, "minister": 2, "ministero": 2}.items():
            if term in lower: value += weight
        departments = ["department", "faculty", "division", "research", "lab", "group", "laboratory",
                       "departamento", "dipartimento", "grupo", "section", "sezione", "unité", "unidad"]
        if any(lower.startswith(term) for term in departments): value -= 3
        value -= sum(.5 for term in departments if term in lower)
        return value + len(part) / 100

    candidates = []
    for position, part in enumerate(parts):
        lower = part.lower()
        if (any(term in lower for term in institution_keywords) or any(term in lower for term in high_confidence)
                or any(term in lower for term in ("nasa", "esa", "jaxa", "univ"))):
            candidates.append((position, part, score(part)))
    return max(candidates, key=lambda item: item[2])[1] if candidates else parts[0]


def extract_country(affiliation):
    if pd.isna(affiliation) or not str(affiliation).strip():
        return None
    parts = [part.strip() for part in str(affiliation).split(",") if part.strip()]
    return parts[-1] if len(parts) > 1 else None


def unify_country_alias(raw_string, stats: ResolutionStats):
    if not raw_string:
        return None
    candidate = str(raw_string).upper().strip()
    candidate = re.sub(r"^(?:[A-Z]{2}\s+)+", "", candidate)
    candidate = re.sub(r"\b\d{5}(?:-\d{4})?\b", "", candidate)
    candidate = re.sub(r"[,\-]", " ", candidate)
    candidate = re.sub(r"\s{2,}", " ", candidate).strip()
    if candidate in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[candidate]
    try:
        return pycountry.countries.lookup(candidate).name
    except LookupError:
        cleaned = re.sub(r"[^A-Z ]", "", candidate.replace("&", "AND")).strip()
        try:
            return pycountry.countries.lookup(cleaned).name
        except LookupError:
            if cleaned in COUNTRY_ALIASES:
                return COUNTRY_ALIASES[cleaned]
            stats.unresolved_countries[str(raw_string).strip()] += 1
            return None


def _counter_table(counter: Counter, item_name: str, limit=None) -> pd.DataFrame:
    rows = counter.most_common(limit)
    return pd.DataFrame(rows, columns=[item_name, "Occurrences"])


def resolve_entities(data: pd.DataFrame, alias_json_file=None) -> dict:
    """Create affiliation-level and article-level standardized entity tables."""
    if "Affiliations" not in data.columns:
        raise ValueError("The dataset is missing the required 'Affiliations' column.")
    if data.empty:
        raise ValueError("The dataset contains no records to resolve.")
    alias_info = validate_institution_alias_json(alias_json_file)
    stats = ResolutionStats()
    articles = data.copy().reset_index(drop=True)
    articles["Article_Index"] = articles.index
    articles["Affiliations_Cleaned"] = articles["Affiliations"].apply(clean_affiliations)
    exploded = articles.assign(
        Affiliations_Cleaned=articles["Affiliations_Cleaned"].fillna("").str.split(";")
    ).explode("Affiliations_Cleaned")
    exploded["Affiliations_Cleaned"] = exploded["Affiliations_Cleaned"].astype(str).str.strip()
    exploded = exploded[exploded["Affiliations_Cleaned"].ne("")].copy()
    exploded["Institution_Raw"] = exploded["Affiliations_Cleaned"].apply(extract_institution_custom)
    exploded["Country_Raw"] = exploded["Affiliations_Cleaned"].apply(extract_country)
    exploded["Institution_Extracted"] = exploded["Institution_Raw"].apply(
        lambda value: standardize_institution_name(value, alias_info["lookup"], stats)
    )
    exploded["Country_Standardized"] = exploded["Country_Raw"].apply(
        lambda value: unify_country_alias(value, stats)
    )
    keep = [column for column in ["Article_Index", "Title", "Publication Year", "DOI",
        "Affiliations_Cleaned", "Institution_Raw", "Institution_Extracted", "Country_Raw",
        "Country_Standardized"] if column in exploded]
    affiliation_table = exploded[keep].copy().dropna(subset=["Institution_Extracted"])
    countries = exploded.groupby("Article_Index")["Country_Standardized"].apply(
        lambda values: sorted(set(values.dropna()))
    )
    institutions = exploded.groupby("Article_Index")["Institution_Extracted"].apply(
        lambda values: sorted(set(values.dropna()))
    )
    article_summary = data.copy().reset_index(drop=True)
    article_summary["Countries_Extracted"] = article_summary.index.to_series().map(countries).apply(
        lambda value: value if isinstance(value, list) else []
    )
    article_summary["Institutions_Extracted"] = article_summary.index.to_series().map(institutions).apply(
        lambda value: value if isinstance(value, list) else []
    )
    article_summary["Country_Count"] = article_summary["Countries_Extracted"].apply(len)
    article_summary["Collaboration_Type"] = article_summary["Country_Count"].map(
        lambda count: "International" if count > 1 else ("National" if count == 1 else "Undefined")
    )
    article_summary["Country_Classification"] = article_summary["Country_Count"].map(
        lambda count: "MCP" if count > 1 else ("SCP" if count == 1 else "Unknown")
    )
    summary = pd.DataFrame([
        ("Input articles", len(data)),
        ("Articles with affiliation metadata", int(data["Affiliations"].notna().sum())),
        ("Exploded affiliation rows", len(exploded)),
        ("Affiliations with an extracted institution", int(exploded["Institution_Extracted"].notna().sum())),
        ("Affiliations with a standardized country", int(exploded["Country_Standardized"].notna().sum())),
        ("Unique standardized institutions", exploded["Institution_Extracted"].nunique(dropna=True)),
        ("Unique standardized countries", exploded["Country_Standardized"].nunique(dropna=True)),
        ("International articles", int((article_summary["Collaboration_Type"] == "International").sum())),
        ("National articles", int((article_summary["Collaboration_Type"] == "National").sum())),
        ("Articles with undefined geography", int((article_summary["Collaboration_Type"] == "Undefined").sum())),
    ], columns=["Entity-resolution measure", "Value"])
    return {
        "article_summary": article_summary, "affiliations": affiliation_table,
        "all_exploded_affiliations": exploded, "alias_info": alias_info,
        "audit": {
            "summary": summary,
            "abbreviations": _counter_table(stats.abbreviations, "Abbreviation expansion"),
            "aliases": _counter_table(stats.aliases, "Institution alias mapping"),
            "complex_patterns": _counter_table(stats.complex_patterns, "Complex pattern"),
            "unresolved_countries": _counter_table(stats.unresolved_countries, "Unresolved country fragment"),
            "institution_frequencies": exploded["Institution_Extracted"].value_counts().rename_axis("Institution").reset_index(name="Affiliations"),
            "country_frequencies": exploded["Country_Standardized"].value_counts().rename_axis("Country").reset_index(name="Affiliations"),
        },
        "warnings": (["Some affiliation country fragments could not be standardized; review the unresolved-country table."]
                     if stats.unresolved_countries else []),
    }
