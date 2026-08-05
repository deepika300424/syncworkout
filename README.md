# Workout Voice RAG Agent

A LangGraph-based workout assistant that ingests Puma workout manifests, stores structured metadata in SQLite, builds a hybrid retrieval index with FAISS + BM25, and answers user queries using a local Ollama LLM for testing or Gemini in production.

## What this project does

- Loads workout manifests from a local dataset folder.
- Stores workout metadata in SQLite tables:
  - `workouts`
  - `sections`
  - `exercises`
  - `audio_cues`
- Builds retrieval chunks from the database.
- Creates a hybrid search index using:
  - Sentence Transformers embeddings
  - FAISS vector search
  - BM25 lexical search
  - Reciprocal Rank Fusion (RRF)
- Uses LangGraph to route queries through a simple multi-step workflow.
- Supports LLM switching via an LLM factory:
  - `ollama` for local testing
  - `gemini` for production

## Tech stack

- Python 3.10+
- FastAPI
- LangGraph
- LangChain
- FAISS
- Sentence Transformers
- SQLite
- Ollama (local testing)
- Gemini (optional production)

## Project structure

- [app/api](C:/syncworkout/app/api) – FastAPI endpoints
- [app/agents](C:/syncworkout/app/agents) – router, retrieval, response agents
- [app/core](C:/syncworkout/app/core) – settings, schema, LLM factory
- [app/data](C:/syncworkout/app/data) – manifest loading, DB ingestion, bootstrap
- [app/graph](C:/syncworkout/app/graph) – LangGraph workflow
- [app/index](C:/syncworkout/app/index) – hybrid retrieval index
- [app/voice](C:/syncworkout/app/voice) – speech-to-text and text-to-speech

## Prerequisites

1. Python 3.10+ installed
2. A virtual environment (recommended)
3. Ollama installed and running for local testing
4. A dataset folder containing your Puma workout manifest JSON files

## 1) Create and activate a virtual environment

On Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

## 2) Install dependencies

```powershell
pip install -r requirements.txt
```

## 3) Create environment file

Copy the example file:

```powershell
Copy-Item .env.example .env
```

Then edit [.env](C:/syncworkout/.env) and set values such as:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen3.5:3b
OLLAMA_BASE_URL=http://localhost:11434
PUMA_DATA_ROOT=puma_workout_data
SQLITE_DB_PATH=storage/workouts.db
FAISS_INDEX_PATH=storage/faiss.index
CHUNKS_JSON_PATH=storage/chunks.json
```

## 4) Start Ollama locally

If you do not already have Ollama installed:

- Install from: https://ollama.com/

Then pull the model and start the server:

```powershell
ollama pull qwen3.5:3b
ollama serve
```

Keep `ollama serve` running in a separate terminal.

## 5) Ingest your workout data into SQLite

Make sure your Puma dataset exists under the folder pointed to by `PUMA_DATA_ROOT`.

Run:

```powershell
python -m app.data.bootstrap
```

This will:
- read your manifest JSON files,
- insert the data into SQLite,
- create the retrieval chunks.

## 6) Run the API server

### Optional: Transcribe audio cues (recommended)

The dataset contains many MP3 audio cues that describe posture and benefits. To improve retrieval relevance, transcribe MP3 files to text and include those transcripts in the retrieval index. A helper script is provided:

```powershell
python -m app.data.transcribe_audio
```

This will create `.txt` transcripts next to each `.mp3` file (e.g. `cue.mp3` -> `cue.txt`). After producing transcripts, rebuild the index by re-running:

```powershell
python -m app.data.bootstrap
```

Then start the API server as described below.

```powershell
uvicorn app.api.main:app --reload
```

The API will be available at:

- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/docs

## 7) Test the API

### Health check

```powershell
curl http://127.0.0.1:8000/health
```

### Text query

```powershell
curl -X POST http://127.0.0.1:8000/query ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"Find a workout about strength\"}"
```

`/query` and `/voice-query` now return:

- `answer` — a user-facing natural-language response (UX text)
- `intent` — detected intent category
- `citations` — raw retrieved chunks for traceability/debugging
- `render_payload` — structured workout/section/exercise JSON with IDs and media paths for frontend rendering

### Voice query

You can upload an audio file to `/voice-query`.

## Using Gemini in production

To use Gemini instead of local Ollama:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash
```

Then restart the API server.

## Notes

- If no manifest files are found under `PUMA_DATA_ROOT`, startup will report a missing-data error.
- The FAISS index and chunk metadata are stored under `storage/` and reused on next startup when available.
- If you add new manifests later, re-run:

```powershell
python -m app.data.bootstrap
```

## Troubleshooting

### Ollama connection issues

- Ensure `ollama serve` is running.
- Check that `OLLAMA_BASE_URL` points to your local server.
- Confirm the model exists:

```powershell
ollama list
```

### Missing dependency errors

Reinstall dependencies:

```powershell
pip install -r requirements.txt
```

### No data found

Make sure your manifest JSON files are present under the configured data root.
