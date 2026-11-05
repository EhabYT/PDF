"""Transparent local rules: only visible OCR evidence, never generated facts."""
from pathlib import Path
import re
import unicodedata

CATEGORIES = ["Official Documents", "Government Documents", "Immigration Documents", "Naturalization Documents", "School Documents", "University Documents", "Employment Documents", "Contracts", "Rental Agreements", "Invoices", "Receipts", "Bank Statements", "Insurance Documents", "Medical Documents", "Legal Documents", "Letters", "Certificates", "Applications", "Other Documents"]
RULES = [
    ("rental", "Rental Agreements", r"mietvertrag|wohnraummietvertrag|rental agreement|tenancy agreement|عقد إيجار", {"de": "Mietvertrag", "en": "Rental_Agreement", "ar": "عقد_إيجار"}, "Rental agreement identified from visible text."),
    ("employment", "Employment Documents", r"arbeitsvertrag|employment contract|employment agreement|عقد عمل", {"de": "Arbeitsvertrag", "en": "Employment_Contract", "ar": "عقد_عمل"}, "Employment contract identified from visible text."),
    ("naturalization", "Naturalization Documents", r"einbürgerung|einbuergerung|naturalization|naturalisation|تجنيس|الجنسية", {"de": "Einbuergerung_Unterlagen", "en": "Naturalization_Documents", "ar": "وثائق_التجنيس"}, "Naturalization-related document identified from visible text."),
    ("bank", "Bank Statements", r"kontoauszug|bank statement|account statement|كشف حساب", {"de": "Kontoauszug", "en": "Bank_Statement", "ar": "كشف_حساب"}, "Bank statement identified from visible text."),
    ("electricity", "Invoices", r"stromrechnung|electricity bill|electricity invoice|فاتورة كهرباء", {"de": "Stromrechnung", "en": "Electricity_Bill", "ar": "فاتورة_كهرباء"}, "Electricity invoice identified from visible text."),
    ("university", "University Documents", r"universität|universitaet|university|hochschule|جامعة", {"de": "Universitaet_Dokument", "en": "University_Document", "ar": "وثيقة_جامعية"}, "University document identified from visible text."),
    ("school", "School Documents", r"schulbescheinigung|school certificate|schulzeugnis|report card|شهادة مدرسية", {"de": "Schulbescheinigung", "en": "School_Certificate", "ar": "شهادة_مدرسية"}, "School document identified from visible text."),
    ("insurance", "Insurance Documents", r"versicherungsschein|insurance policy|versicherung|تأمين", {"de": "Versicherung", "en": "Insurance_Document", "ar": "وثيقة_تأمين"}, "Insurance document identified from visible text."),
    ("medical", "Medical Documents", r"ärztliche bescheinigung|medical certificate|krankenhaus|ärztlicher bericht|تقرير طبي", {"de": "Medizinisches_Dokument", "en": "Medical_Document", "ar": "وثيقة_طبية"}, "Medical document identified from visible text."),
    ("immigration", "Immigration Documents", r"aufenthaltstitel|residence permit|visa|إقامة", {"de": "Aufenthalt_Dokument", "en": "Immigration_Document", "ar": "وثيقة_إقامة"}, "Immigration document identified from visible text."),
    ("invoice", "Invoices", r"\brechnung\b|\binvoice\b|rechnungsnummer|invoice number|فاتورة", {"de": "Rechnung", "en": "Invoice", "ar": "فاتورة"}, "Invoice identified from visible text."),
    ("receipt", "Receipts", r"\bquittung\b|\breceipt\b|kassenbon|إيصال", {"de": "Quittung", "en": "Receipt", "ar": "إيصال"}, "Receipt identified from visible text."),
    ("certificate", "Certificates", r"\bbescheinigung\b|\bcertificate\b|zertifikat|شهادة", {"de": "Bescheinigung", "en": "Certificate", "ar": "شهادة"}, "Certificate identified from visible text."),
    ("application", "Applications", r"\bantrag\b|\bapplication\b|bewerbung|طلب", {"de": "Antrag", "en": "Application", "ar": "طلب"}, "Application identified from visible text."),
    ("contract", "Contracts", r"\bvertrag\b|\bcontract\b|اتفاقية|عقد", {"de": "Vertrag", "en": "Contract", "ar": "عقد"}, "Contract identified from visible text."),
    ("letter", "Letters", r"sehr geehrte|dear sir|dear madam|mit freundlichen grüßen|sincerely|بسم الله|السادة", {"de": "Brief", "en": "Letter", "ar": "رسالة"}, "Correspondence identified from visible text."),
]
AR_MAP = str.maketrans({"ا":"a","أ":"a","إ":"i","آ":"a","ب":"b","ت":"t","ث":"th","ج":"j","ح":"h","خ":"kh","د":"d","ذ":"dh","ر":"r","ز":"z","س":"s","ش":"sh","ص":"s","ض":"d","ط":"t","ظ":"z","ع":"a","غ":"gh","ف":"f","ق":"q","ك":"k","ل":"l","م":"m","ن":"n","ه":"h","و":"w","ي":"y","ى":"a","ة":"h","ء":"a","ؤ":"o","ئ":"i","٠":"0","١":"1","٢":"2","٣":"3","٤":"4","٥":"5","٦":"6","٧":"7","٨":"8","٩":"9"})


def safe_filename(name: str, extension: str = ".pdf", transliterate: bool = True) -> str:
    name = unicodedata.normalize("NFC", name).translate(AR_MAP) if transliterate else unicodedata.normalize("NFC", name)
    name = re.sub(r"\.(pdf|jpe?g|png|webp|tiff?)$", "", name, flags=re.I)
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", name)
    name = re.sub(r"[\s_]+", "_", name).strip("._- ")
    name = name[:112].rstrip("._-") or "Unbekanntes_Dokument"
    return name + extension


def extract_date(text: str) -> tuple[str, str]:
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    numeric = re.search(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](20\d{2}|19\d{2})(?!\d)", text)
    if numeric:
        d, m, y = numeric.groups()
        if 1 <= int(d) <= 31 and 1 <= int(m) <= 12:
            return f"{int(m):02d}-{y}", "document"
    iso = re.search(r"(?<!\d)(20\d{2}|19\d{2})-(\d{2})-(\d{2})(?!\d)", text)
    if iso and 1 <= int(iso[2]) <= 12 and 1 <= int(iso[3]) <= 31:
        return f"{iso[2]}-{iso[1]}", "document"
    years = re.findall(r"\b(20\d{2}|19\d{2})\b", text)
    if years:
        return years[0], "document"
    return "", ""


def extract_organization(text: str) -> str:
    lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines() if x.strip()]
    for line in lines[:35]:
        match = re.search(r"((?:Stadt|Stadtverwaltung|Gemeinde|Universität|Sparkasse|Volksbank|Deutsche Bank|Commerzbank|AOK|TK|Barmer|Bundesamt für|Finanzamt|Jobcenter)\s+[A-ZÄÖÜ][\wäöüß-]+(?:\s+[A-ZÄÖÜ][\wäöüß-]+)?)", line)
        if match:
            return match.group(1)[:70]
        match = re.search(r"([A-ZÄÖÜ][\wäöüß&.-]*(?:\s+[A-ZÄÖÜ][\wäöüß&.-]*){0,3}\s+(?:GmbH|AG|SE|KG))", line)
        if match:
            return match.group(1)[:70]
    for line in lines[:20]:
        if re.match(r"^(Stadt|Finanzamt|Jobcenter|Bundesamt|Universität|Sparkasse|AOK|Barmer)\b", line) and len(line) < 80:
            return line
    return ""


def extract_subject(text: str, kind: str) -> str:
    if kind in ("rental", "employment", "university"):
        match = re.search(r"\b(?:in|Standort|Wohnort)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?)", text)
        if match:
            return match.group(1)
    if kind == "university" and re.search(r"informatik|computer science", text, re.I):
        return "Informatik"
    return ""


def classify(texts: list[str], upload_year: int, language: str = "de", transliterate: bool = True, ocr_available: bool = True) -> dict:
    text = "\n".join(texts)
    lang = language if language in ("de", "en", "ar") else "de"
    matched = None
    evidence = []
    for kind, category, pattern, names, description in RULES:
        hits = re.findall(pattern, text, re.I)
        if hits:
            evidence.extend(hits[:3])
            if matched is None:
                matched = (kind, category, names[lang], description)
    date, source = extract_date(text)
    org = extract_organization(text)
    if not matched:
        kind, category, name, description = "unknown", "Other Documents", {"de": "Unbekanntes_Dokument", "en": "Unknown_Document", "ar": "وثيقة_غير_معروفة"}[lang], "Document type could not be determined reliably. Review before exporting."
        if not date:
            date, source = str(upload_year), "upload"
    else:
        kind, category, name, description = matched
    subject = extract_subject(text, kind)
    org_part = re.sub(r"^(Stadt|Stadtverwaltung|Universität|Sparkasse)\s+", "", org) if kind in ("rental", "school", "university") else org
    parts = [name]
    if kind == "bank" and org:
        parts = [safe_filename(org, ""), name]
    elif subject:
        parts.append(subject)
    elif org_part and kind not in ("letter",):
        parts.append(org_part)
    if date:
        parts.append(date)
    filename = safe_filename("_".join(parts), ".pdf", transliterate)
    return {"name": filename, "detected_type": name.replace("_", " "), "category": category, "organization": org, "subject": subject, "detected_date": date, "date_source": source, "description": description, "evidence": evidence[:8], "confidence": "high" if matched and len(evidence) >= 2 else "medium" if matched else "low", "language": lang, "method": "local_ocr_rules", "ocr_available": ocr_available}
