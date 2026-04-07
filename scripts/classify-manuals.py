"""classify-manuals.py -- PDF manual batch classification and renaming.

Reads each PDF, extracts metadata (manufacturer, model, doc type, language),
assesses embedding value, then moves to ready/ or skipped/ folder.

Usage:
  python classify-manuals.py                    # all categories
  python classify-manuals.py --category 4_servo # specific category
  python classify-manuals.py --dry-run          # analysis only, no move
"""

import argparse
import json
import logging
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    import fitz
except ImportError:
    sys.exit("[classify] pymupdf required: pip install pymupdf")

# -- Config --
BASE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE_DIR = os.path.join(BASE_DIR, "data", "manuals-filtered")
READY_DIR = os.path.join(BASE_DIR, "data", "manuals-ready")
SKIPPED_DIR = os.path.join(BASE_DIR, "data", "manuals-skipped")
LOG_FILE = os.path.join(BASE_DIR, "data", "classification-log.jsonl")

# Embedding value thresholds
MIN_TEXT_CHARS = 500
MIN_TEXT_PAGES_RATIO = 0.3

logging.basicConfig(
    level=logging.INFO,
    format="[classify] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("classify")

# -- Manufacturer keywords --
MANUFACTURER_MAP = {
    "samsung": "Samsung", "csd5": "Samsung", "csd3": "Samsung", "csd7": "Samsung",
    "csvg": "Samsung", "csdp": "Samsung", "knx3": "Samsung",
    "oriental motor": "OrientalMotor", "orientalmotor": "OrientalMotor",
    "mitsubishi": "Mitsubishi", "melservo": "Mitsubishi", "melsec": "Mitsubishi",
    "mr-j": "Mitsubishi", "hg-kr": "Mitsubishi",
    "yaskawa": "Yaskawa", "sigma": "Yaskawa", "sgdv": "Yaskawa", "sgd7": "Yaskawa",
    "panasonic": "Panasonic", "minas": "Panasonic", "panaterm": "Panasonic",
    "omron": "Omron",
    "keyence": "Keyence",
    "abb": "ABB", "irb": "ABB",
    "kuka": "KUKA",
    "fanuc": "FANUC",
    "siemens": "Siemens",
    "beckhoff": "Beckhoff",
    "iai": "IAI",
    "smc": "SMC",
    "festo": "Festo",
    "sick": "SICK",
    "cognex": "Cognex",
    "ls ": "LS", "ls-": "LS",
    "delta": "Delta",
    "autonics": "Autonics",
    "pro-face": "ProFace", "proface": "ProFace",
    "weintek": "Weintek",
    "hiwin": "HIWIN",
    "thk": "THK",
    "nsk": "NSK",
    "schneider": "Schneider",
    "rockwell": "Rockwell", "allen-bradley": "Rockwell",
    "bosch": "Bosch", "rexroth": "BoschRexroth",
    "lenze": "Lenze",
    "sew": "SEW",
    "danfoss": "Danfoss",
    "eaton": "Eaton",
    "phoenix": "PhoenixContact",
    "wago": "WAGO",
    "balluff": "Balluff",
    "ifm": "IFM",
    "baumer": "Baumer",
    "crevis": "Crevis",
    "fastech": "Fastech", "ezi-servo": "Fastech", "eziservo": "Fastech",
    "ezi-step": "Fastech", "ezistep": "Fastech", "ezi-motionlink": "Fastech",
    "ezi-io": "Fastech",
    "wmx": "SoftServo", "softservo": "SoftServo",
    "sanmotion": "Sanyo",
    "leadshine": "Leadshine", "sv670": "Leadshine", "el7-ec": "Leadshine",
    "elm1": "Leadshine", "elm2": "Leadshine", "em3e": "Leadshine",
    "r3-io": "Leadshine", "r3ec": "Leadshine",
    "adax": "WTA", "ada2": "WTA", "adapi": "WTA",
    "hiragen": "Hiragen",
    "tsm": "Applied Motion",
    "spiiplus": "ACS",
    "rtx64": "IntervalZero", "rtx": "IntervalZero",
    "ethercat": "EtherCAT",
    "mezio": "Nexcom",
    "nda7000": "NDA",
    "dxp": "DX", "dx-series": "DX", "dx150": "DX",
}

# -- Doc type keywords --
DOC_TYPE_MAP = {
    "user manual": "UserManual", "user's manual": "UserManual",
    "users manual": "UserManual", "operation manual": "OperationManual",
    "operation guide": "OperationGuide", "install": "InstallGuide",
    "setup": "SetupGuide", "maintenance": "MaintenanceManual",
    "parameter": "ParameterManual", "communication": "CommManual",
    "protocol": "CommManual", "troubleshoot": "Troubleshooting",
    "quick start": "QuickStart", "catalog": "Catalog",
    "datasheet": "Datasheet", "specification": "Datasheet",
    "wiring": "WiringGuide", "programming": "ProgrammingManual",
    "firmware": "FirmwareNote", "release note": "ReleaseNote",
    "api reference": "APIReference", "reference": "Reference",
    "function": "FunctionsManual", "tutorial": "Tutorial",
    "introduction": "Introduction", "safety": "Safety",
    "ascii": "CommManual", "modbus": "CommManual",
    "ethercat": "CommManual",
    "technical": "TechnicalDoc",
    "brochure": "Brochure",
    "manual": "Manual",
}


@dataclass
class PdfClassification:
    original_path: str
    original_name: str
    category: str
    manufacturer: str = "Unknown"
    model: str = "Unknown"
    doc_type: str = "Manual"
    language: str = "KO"
    standardized_name: str = ""
    total_pages: int = 0
    total_text_chars: int = 0
    text_pages: int = 0
    text_ratio: float = 0.0
    is_embeddable: bool = True
    skip_reason: str = ""
    destination: str = ""
    error: str = ""


def extract_metadata(file_path: str) -> PdfClassification:
    """Extract metadata from PDF for classification."""
    result = PdfClassification(
        original_path=file_path,
        original_name=Path(file_path).name,
        category=Path(file_path).parent.name,
    )
    filename_lower = Path(file_path).stem.lower()

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        result.error = f"Cannot open: {e}"
        result.is_embeddable = False
        result.skip_reason = result.error
        return result

    result.total_pages = len(doc)
    if result.total_pages == 0:
        doc.close()
        result.is_embeddable = False
        result.skip_reason = "Empty PDF (0 pages)"
        return result

    # Read first 3 pages for metadata
    pages_text = ""
    for i in range(min(3, len(doc))):
        pages_text += doc[i].get_text("text").replace("\x00", "") + "\n"

    # Full text stats
    total_text = ""
    pages_with_text = 0
    for i in range(len(doc)):
        text = doc[i].get_text("text").replace("\x00", "").strip()
        total_text += text
        if len(text) > 50:
            pages_with_text += 1

    doc.close()

    result.total_text_chars = len(total_text)
    result.text_pages = pages_with_text
    result.text_ratio = pages_with_text / result.total_pages if result.total_pages > 0 else 0

    combined = (filename_lower + " " + pages_text.lower()).strip()

    # 1. Manufacturer
    for keyword, mfr in MANUFACTURER_MAP.items():
        if keyword in combined:
            result.manufacturer = mfr
            break

    # 2. Model name from filename
    model_patterns = [
        r'([A-Z]{2,}[\-]?[A-Z0-9]{1,}[\-]?[A-Z0-9]*)',
    ]
    filename_upper = Path(file_path).stem
    for pattern in model_patterns:
        m = re.search(pattern, filename_upper)
        if m:
            candidate = m.group(1)
            skip_words = {"PDF", "DOC", "KOR", "ENG", "ALL", "KO", "EN", "JP",
                          "Drive", "MAY", "Manual", "Ver", "REV", "NEW", "OLD",
                          "MINI", "PLUS", "SERVO", "MOTOR", "STEP"}
            if len(candidate) >= 3 and candidate not in skip_words:
                result.model = candidate
                break

    # 3. Doc type
    for keyword, dtype in DOC_TYPE_MAP.items():
        if keyword in combined:
            result.doc_type = dtype
            break

    # 4. Language
    ko_chars = len(re.findall(r'[가-힣]', pages_text))
    en_chars = len(re.findall(r'[a-zA-Z]', pages_text))
    jp_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', pages_text))
    if jp_chars > 50 and jp_chars > ko_chars:
        result.language = "JP"
    elif ko_chars > 50:
        result.language = "KO"
    elif en_chars > 100 and ko_chars < 10:
        result.language = "EN"
    else:
        result.language = "KO"

    # 5. Embedding value check
    if result.total_text_chars < MIN_TEXT_CHARS:
        result.is_embeddable = False
        result.skip_reason = f"Text insufficient ({result.total_text_chars} chars < {MIN_TEXT_CHARS})"
    elif result.text_ratio < MIN_TEXT_PAGES_RATIO:
        result.is_embeddable = False
        result.skip_reason = f"Text page ratio low ({result.text_ratio:.1%} < {MIN_TEXT_PAGES_RATIO:.0%})"

    # 6. Standardized name
    result.standardized_name = f"{result.manufacturer}_{result.model}_{result.doc_type}_{result.language}.pdf"

    return result


def safe_dest_path(dest_dir: str, filename: str) -> str:
    """Generate unique destination path (append _2, _3... if exists)."""
    dest = os.path.join(dest_dir, filename)
    if not os.path.exists(dest):
        return dest
    base, ext = os.path.splitext(filename)
    counter = 2
    while os.path.exists(dest):
        dest = os.path.join(dest_dir, f"{base}_{counter}{ext}")
        counter += 1
    return dest


def process_category(category_dir: str, dry_run: bool = False) -> list[PdfClassification]:
    """Process all PDFs in a category directory."""
    category = os.path.basename(category_dir)
    pdf_files = sorted([
        os.path.join(category_dir, f)
        for f in os.listdir(category_dir)
        if f.lower().endswith(".pdf")
    ])

    if not pdf_files:
        return []

    log.info(f"Category: {category} ({len(pdf_files)} PDFs)")

    ready_dir = os.path.join(READY_DIR, category)
    skipped_dir = os.path.join(SKIPPED_DIR, category)

    if not dry_run:
        os.makedirs(ready_dir, exist_ok=True)
        os.makedirs(skipped_dir, exist_ok=True)

    results = []
    ready_count = 0
    skip_count = 0
    error_count = 0

    for i, file_path in enumerate(pdf_files):
        cls = extract_metadata(file_path)

        if cls.error:
            error_count += 1
            cls.destination = "error"
            log.warning(f"  [{i+1}/{len(pdf_files)}] ERROR: {cls.original_name} -- {cls.error}")
        elif cls.is_embeddable:
            ready_count += 1
            if not dry_run:
                dest = safe_dest_path(ready_dir, cls.standardized_name)
                shutil.copy2(file_path, dest)
                cls.destination = dest
            else:
                cls.destination = f"ready/{category}/{cls.standardized_name}"
        else:
            skip_count += 1
            if not dry_run:
                dest = safe_dest_path(skipped_dir, cls.original_name)
                shutil.copy2(file_path, dest)
                cls.destination = dest
            else:
                cls.destination = f"skipped/{category}/{cls.original_name}"

        results.append(cls)

        # Progress logging every 20 files
        if (i + 1) % 20 == 0:
            log.info(f"  [{i+1}/{len(pdf_files)}] ready={ready_count} skip={skip_count} err={error_count}")

    log.info(f"  {category} done: ready={ready_count}, skip={skip_count}, error={error_count}")
    return results


def main():
    parser = argparse.ArgumentParser(description="PDF manual classification")
    parser.add_argument("--category", help="Process specific category only")
    parser.add_argument("--dry-run", action="store_true", help="Analysis only, no file moves")
    args = parser.parse_args()

    log.info(f"Source: {SOURCE_DIR}")
    log.info(f"Mode: {'DRY-RUN' if args.dry_run else 'CLASSIFY + MOVE'}")

    if not os.path.isdir(SOURCE_DIR):
        log.error(f"Source dir not found: {SOURCE_DIR}")
        return

    if not args.dry_run:
        os.makedirs(READY_DIR, exist_ok=True)
        os.makedirs(SKIPPED_DIR, exist_ok=True)

    # Get categories
    if args.category:
        categories = [os.path.join(SOURCE_DIR, args.category)]
    else:
        categories = sorted([
            os.path.join(SOURCE_DIR, d)
            for d in os.listdir(SOURCE_DIR)
            if os.path.isdir(os.path.join(SOURCE_DIR, d))
        ])

    all_results = []
    for cat_dir in categories:
        if not os.path.isdir(cat_dir):
            log.warning(f"Not found: {cat_dir}")
            continue
        results = process_category(cat_dir, dry_run=args.dry_run)
        all_results.extend(results)

    # Summary
    total = len(all_results)
    ready = sum(1 for r in all_results if r.is_embeddable and not r.error)
    skipped = sum(1 for r in all_results if not r.is_embeddable and not r.error)
    errors = sum(1 for r in all_results if r.error)

    log.info(f"\n=== Summary ===")
    log.info(f"Total: {total} PDFs")
    log.info(f"Ready: {ready}")
    log.info(f"Skipped: {skipped}")
    log.info(f"Errors: {errors}")

    # Manufacturer breakdown
    from collections import Counter
    mfr_counts = Counter(r.manufacturer for r in all_results if r.is_embeddable)
    log.info(f"\nManufacturer breakdown (ready):")
    for mfr, cnt in mfr_counts.most_common(20):
        log.info(f"  {mfr}: {cnt}")

    # Write classification log
    log.info(f"\nWriting log: {LOG_FILE}")
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        for r in all_results:
            record = {
                "original_name": r.original_name,
                "category": r.category,
                "manufacturer": r.manufacturer,
                "model": r.model,
                "doc_type": r.doc_type,
                "language": r.language,
                "standardized_name": r.standardized_name,
                "total_pages": r.total_pages,
                "total_text_chars": r.total_text_chars,
                "text_ratio": round(r.text_ratio, 3),
                "is_embeddable": r.is_embeddable,
                "skip_reason": r.skip_reason,
                "destination": r.destination,
                "error": r.error,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    log.info("Done!")


if __name__ == "__main__":
    main()
