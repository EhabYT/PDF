# Smart Document Naming & Classification

## Flow
Upload → OmniFix processing → local Tesseract OCR on each page → combine text across pages → transparent multilingual rules → suggested filename/category/type/organization/date/purpose → owner review/edit → export/download/library/history use the approved name.

## Privacy
OCR runs locally (`deu+eng+ara`). No external OCR/AI provider. OCR text is stored privately under `storage/analysis/` and is never returned by the API or used to modify pixels.

## Classification
Purpose-first rules distinguish rental agreements, employment contracts, naturalization documents, bank statements, electricity invoices, university/school documents, insurance/medical/immigration documents, invoices, receipts, certificates, applications, contracts and letters. Categories map to the requested library taxonomy.

Only visible evidence is used:
- Type: matched multilingual keywords.
- Organization: visible lines such as Stadt/Gemeinde/Universität/Sparkasse/GmbH/AG etc.
- Date: visible numeric/ISO dates or year; Arabic-Indic digits normalized for date extraction.
- Subject: explicit location/program cues when present.
- Purpose: short description tied to the matched type.

## Filename rules
Format: `DocumentType_Subject_Organization_Date.pdf` using the most relevant available parts. Default language German; English and Arabic options. Safe Unicode filename characters, no path separators/control characters, no duplicate extensions, length capped. Arabic transliteration is enabled by default for filesystem compatibility and can be disabled.

Examples:
- `Mietvertrag_Essen_03-2026.pdf`
- `Schulbescheinigung_2026.pdf`
- `Sparkasse_Duesseldorf_Kontoauszug_11-2026.pdf`
- `Arbeitsvertrag_Firma_2026.pdf`

## Unknown / unclear
Conservative fallback: `Unbekanntes_Dokument_<upload-year>.pdf`. The upload year is labeled as upload metadata, not a detected document date. No institution, purpose or date is invented.

## Multi-page & unrelated documents
All pages of one document are analyzed together for one consistent name. Upload unrelated files as separate documents to classify/name them separately. The system does not silently split a multi-page PDF into unrelated documents.

## Review
The export page and document workspace show the suggestion and detected fields. The owner can accept, edit, rename or change category before export. Original uploaded filenames are preserved separately.
