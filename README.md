# Landed

Landed is a local-first immigration document assistant for Canadian temporary residents. It ingests permits, visas, passports, and IRCC scans, extracts structured facts from noisy documents, cross-references them across the full upload set, and turns that into deadlines, risks, action items, and grounded Q&A.

## Repository

`https://github.com/absolute-xero7/landed`

## Inspiration

In August 2025, my Temporary Resident Visa expired while I was visiting India. I missed the start of my Winter 2026 semester at the University of Toronto. For three weeks I wrote letters to IRCC officers, university officials, and my MP trying to resolve a situation that started with one line in one document I had not understood.

The frustrating part was not the bureaucracy itself — it was that the information I needed existed. It was printed on my documents. I just did not know how to read them together, what the deadlines meant, or what would happen if I missed them. A licensed immigration consultant would have caught it in minutes. Most people cannot afford one.

Landed was built so that never happens to someone else. It reads your documents the way a consultant would — across all of them at once — and tells you exactly what your situation is, what you need to do, and what happens if you don't.

## Product Summary

Landed lets a user upload immigration documents into a single session and then:
- parses both native PDFs and low-quality scanned documents
- extracts structured facts like names, issue dates, expiry dates, document types, reference numbers, and conditions
- cross-references older and newer documents to determine the most current status
- separates stay authorization, work authorization, and travel authorization
- surfaces deadlines, processing windows, consequences, implied-status guidance, and missing-document warnings
- answers questions in grounded plain English with explicit source labels

The key product value is that Landed does not treat each document in isolation. It reasons across the uploaded set, so an expired work permit does not override a newer valid study permit, and an expired TRV becomes a travel warning rather than a false claim that the user must leave Canada.

## AI Use

More than 70% of the code was AI-assisted during development: `Yes`

The application itself also uses AI at runtime for OCR-assisted extraction, multilingual translation, and fallback Q&A when deterministic extraction is insufficient. When AI output is uncertain, the app falls back to deterministic parsing and field-level evidence instead of silently trusting hallucinated values.

## Technology Stack

### Languages
- Python
- TypeScript

### Frameworks and Libraries
- FastAPI
- Pydantic
- Next.js 14
- React
- Tailwind CSS
- Framer Motion
- Zustand
- react-dropzone
- sse-starlette

### Platforms
- Local-first runtime
- OpenAI-compatible endpoint for GPT-OSS extraction and translation when configured

### Tools
- Railtracks for flow orchestration and tracing (RailtracksPM2)
- PyMuPDF for PDF parsing and rasterization
- local macOS Vision OCR for scanned documents
- reportlab for demo document generation

## Current Feature Set

### Document ingestion and extraction
- Uploads `PDF`, `PNG`, `JPG`, and `JPEG` documents
- Supports multi-document sessions with up to 10 files per upload
- Accepts additional uploads after the first submission and reprocesses the same session with the combined document set
- Extracts data from native-text PDFs, scanned PDFs rendered to images, and image uploads
- Uses deterministic parsing, regex fallback, local macOS Vision OCR, and GPT-OSS structured extraction when `OPENAI_API_KEY` is configured
- Includes deterministic IRCC permit parsing and OCR-tolerant TRV extraction
- Stores per-field evidence, confidence, and low-confidence flags

### Cross-document reasoning
- Builds a cross-document immigration profile from all uploaded files
- Selects the active status document when older permits are superseded
- Separates stay status, work authorization, and travel/re-entry authorization
- Detects expired TRVs independently from permit validity
- Adds processing windows, consequence text, implied-status guidance, and completeness warnings

### Q&A and multilingual support
- Answers grounded questions against the uploaded session
- Uses deterministic answer branches for status, expiry, work rules, travel, implied status, missed-deadline consequences, and missing documents
- Sanitizes fallback model answers to remove markdown junk and OCR leakage
- Supports multilingual answers for new chat responses

### Visualizer and debugging
- Runs the upload pipeline through Railtracks
- Exposes the Railtracks visualizer for trace inspection
- Includes a standalone OCR/parser debug script for single-document inspection

## Implemented UI Surfaces

- Landing page upload zone
- Processing stream with live parse/reasoning/planning updates
- Session dashboard
- Status summary card
- Deadline timeline
- Action plan accordion
- Document evidence cards
- Grounded Q&A chat
- Language selector
- In-session “Add documents” uploader

## Architecture

```text
+------------------------ Frontend (Next.js 14) ------------------------+
| Upload | Processing Stream | Dashboard | Documents | QA | Add Docs   |
+--------------------------------+--------------------------------------+
                                 |
                           REST + SSE
                                 |
+---------------- Backend (FastAPI + Railtracks Flow) ------------------+
| parse_document x N -> synthesize_status -> generate_action_plan       |
|                               |                                       |
|                 deterministic parser + OCR + GPT-OSS                  |
+--------------------------------+--------------------------------------+
                                 |
                        Railtracks Visualizer
```

Flow: `parse_document × N -> synthesize_status -> generate_action_plan`

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# set OPENAI_API_KEY if you want GPT-OSS responses
# leave it blank to use deterministic fallback mode
.venv/bin/python demo/generate_demo_docs.py
.venv/bin/uvicorn main:app --reload --port 8000
```

### 2. Railtracks visualizer

In a separate terminal:

```bash
cd backend
.venv/bin/railtracks viz
```

### 3. Frontend

```bash
cd frontend
npm install
printf 'NEXT_PUBLIC_API_BASE_URL=http://localhost:8000\n' > .env.local
npm run dev
```

### 4. One-command startup

After backend dependencies and frontend `npm install` are done:

```bash
chmod +x start.sh
./start.sh
```

This starts:
- App on `http://localhost:3000`
- API on `http://localhost:8000`
- Railtracks visualizer on `http://localhost:3030`

## Demo Flow

Recommended demo order:
1. Upload the demo document set from [backend/demo](backend/demo)
2. Watch the processing stream detect document types and deadlines
3. Confirm the dashboard picks the active study permit as the current status
4. Confirm the expired TRV appears as a travel/re-entry warning, not a false leave-Canada status
5. Ask grounded questions such as:
   - `Can I work while studying?`
   - `Can I travel and come back to Canada?`
   - `What documents are missing?`

## Demo Documents

Current demo documents in [backend/demo](backend/demo):
- [Passport_compressed.pdf](backend/demo/Passport.pdf)
- [Study Permit_compressed.pdf](backend/demo/Study%20Permit.pdf)
- [TRV.pdf](backend/demo/TRV.pdf)
- [Work Permit_compressed.pdf](backend/demo/Work%20Permit.pdf)

Generate or refresh the standard synthetic samples with:

```bash
cd backend
.venv/bin/python demo/generate_demo_docs.py
```

## Environment Variables

### backend/.env

- `OPENAI_API_KEY`
  - Optional for local demo mode
  - Required for GPT-OSS extraction, translation, and non-fallback Q&A
- `ALLOWED_ORIGINS`
  - Optional
  - Defaults to `http://localhost:3000`
- `MAX_FILE_SIZE_MB`
  - Optional
  - Defaults to `10`
- `MAX_FILES_PER_UPLOAD`
  - Optional
  - Defaults to `10`

### frontend/.env.local

- `NEXT_PUBLIC_API_BASE_URL`
  - Defaults to `http://localhost:8000`

## Local Demo Mode

If `OPENAI_API_KEY` is not configured, Landed still runs end to end using deterministic parsing, local OCR paths, fallback reasoning, and fallback Q&A. This is sufficient for local development, tests, and demos, but GPT-backed extraction and translation will be limited.

## Debugging Tools

Standalone OCR/parser test:

```bash
cd backend
.venv/bin/python utils/test_ocr_gpt.py "demo/TRV (expired).pdf"
```

OCR-only mode:

```bash
cd backend
.venv/bin/python utils/test_ocr_gpt.py "demo/TRV (expired).pdf" --ocr-only
```

## Privacy and Runtime Model

- Uploaded files are processed in memory
- Sessions are stored in memory only and cleaned up after 2 hours
- No account system is required
- Designed for local/demo use rather than durable storage

## Known Local Caveat

`npm run build` can fail in restricted-network environments because [frontend/app/layout.tsx](frontend/app/layout.tsx) pulls Google Fonts at build time. `npm run dev` works for local development.
