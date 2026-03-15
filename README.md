# Landed

Landed is a local-first immigration document assistant for Canadian temporary resident documents. It ingests permits, visas, letters, and scans, extracts structured facts, synthesizes the user’s current status from the uploaded set, and turns that into deadlines, action items, and grounded Q&A.

## Current Feature Set

### Document ingestion and extraction
- Uploads `PDF`, `PNG`, `JPG`, and `JPEG` documents.
- Supports multi-document sessions with up to 10 files per upload.
- Accepts additional uploads after the first submission and reprocesses the same session with the combined document set.
- Extracts data from:
  - native-text PDFs
  - scanned PDFs rendered to images
  - image uploads
- Uses multiple extraction paths:
  - deterministic parsing and regex fallback
  - local macOS Vision OCR for scanned/image-heavy documents
  - GPT-OSS structured extraction when `OPENAI_API_KEY` is configured
- Includes deterministic IRCC work-permit parsing for fields like:
  - person name
  - DOB
  - issue date
  - expiry date
  - employer
  - occupation
  - application and travel document numbers
- Stores per-field evidence with source and confidence.

### Session analysis
- Streams upload progress over SSE while documents are being parsed and reasoned over.
- Synthesizes a cross-document immigration profile from all uploaded documents.
- Produces:
  - current status summary
  - nearest expiry and days remaining
  - merged deadlines
  - risks
  - authorized activities
  - required action items
- Generates structured action plans with normalized sub-steps.
- Prevents blank action-plan bullets by normalizing malformed step payloads.

### Q&A and multilingual support
- Answers grounded questions against the uploaded session.
- Prefers document-grounded answers with explicit source labels.
- Supports multilingual responses and profile translation while preserving:
  - dates
  - form numbers
  - URLs
  - official identifiers and terms

### Visualizer and debugging
- Runs the real upload pipeline through Railtracks.
- Exposes the Railtracks visualizer for trace inspection.
- Includes a standalone OCR/parser debug script for single-document inspection.

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
|                     deterministic parser + OCR + GPT-OSS              |
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
python demo/generate_demo_docs.py
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

## Demo Documents

Generated in [backend/demo](/Users/prahladranjit/Documents/Projects/landed/backend/demo):
- [study_permit_sample.pdf](/Users/prahladranjit/Documents/Projects/landed/backend/demo/study_permit_sample.pdf)
- [trv_letter_sample.pdf](/Users/prahladranjit/Documents/Projects/landed/backend/demo/trv_letter_sample.pdf)
- [ircc_correspondence_sample.pdf](/Users/prahladranjit/Documents/Projects/landed/backend/demo/ircc_correspondence_sample.pdf)
- [work_permit.pdf](/Users/prahladranjit/Documents/Projects/landed/backend/demo/work_permit.pdf)

Generate or refresh them with:

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

If `OPENAI_API_KEY` is not configured, Landed still runs end to end using deterministic parsing, local OCR paths, fallback reasoning, and fallback Q&A. This is good enough for local development, tests, and demos, but GPT-backed extraction and translation will be limited.

## Debugging Tools

Standalone OCR/parser test:

```bash
cd backend
.venv/bin/python utils/test_ocr_gpt.py demo/work_permit.pdf
```

OCR-only mode:

```bash
cd backend
.venv/bin/python utils/test_ocr_gpt.py demo/work_permit.pdf --ocr-only
```

## Privacy and Runtime Model

- Uploaded files are processed in memory.
- Sessions are stored in memory only and cleaned up after 2 hours.
- No account system is required.
- Designed for local/demo use rather than durable storage.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, Framer Motion, react-dropzone, Zustand |
| Backend | FastAPI, Pydantic, sse-starlette |
| Flow Orchestration | Railtracks |
| LLM | GPT-OSS 120B via OpenAI-compatible endpoint |
| OCR / Parsing | PyMuPDF, local macOS Vision OCR, deterministic IRCC parsers |
| Demo generation | reportlab |

## Known Local Caveat

`npm run build` can fail in restricted-network environments because [frontend/app/layout.tsx](/Users/prahladranjit/Documents/Projects/landed/frontend/app/layout.tsx) pulls Google Fonts at build time. `npm run dev` works for local development.
