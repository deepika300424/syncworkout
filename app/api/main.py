from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.llm_factory import build_llm
from app.core.schemas import QueryRequest, QueryResponse
from app.core.settings import get_settings
from app.data.db import connect_db, has_workout_data, ingest_manifests, init_db_schema, load_chunks_from_db
from app.data.manifest_loader import load_workout_manifests
from app.graph.workflow import build_workflow
from app.index.hybrid_index import HybridRetriever
from app.voice.stt import SpeechToText

settings = get_settings()
app = FastAPI(title="Workout Voice RAG API", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
INDEX_CACHE_VERSION = "3"

retriever: HybridRetriever | None = None
workflow = None
startup_error: str | None = None
stt_engine: SpeechToText | None = None


@app.get("/", response_class=FileResponse)
def ui() -> FileResponse:
    return FileResponse("app/static/index.html")


def get_stt_engine() -> SpeechToText:
    global stt_engine
    if stt_engine is None:
        stt_engine = SpeechToText(model_name="base")
    return stt_engine


@app.get("/media/{media_path:path}")
def media(media_path: str) -> FileResponse:
    media_root = settings.puma_data_root.resolve()
    requested_path = (media_root / media_path).resolve()
    if media_root not in requested_path.parents or not requested_path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found.")
    return FileResponse(requested_path)


def _cached_index_matches(chunks_json_path: Path, db_chunks_count: int) -> bool:
    version_path = chunks_json_path.with_name("index.version")
    if not version_path.exists() or version_path.read_text(encoding="utf-8").strip() != INDEX_CACHE_VERSION:
        return False
    total_cached_chunks = 0
    for suffix in ("", "_audio", "_video"):
        cache_path = chunks_json_path.with_name(f"{chunks_json_path.stem}{suffix}{chunks_json_path.suffix}")
        if cache_path.exists():
            total_cached_chunks += len(json.loads(cache_path.read_text(encoding="utf-8")))
    return total_cached_chunks == db_chunks_count


@app.on_event("startup")
def startup_event() -> None:
    global retriever, workflow, startup_error
    startup_error = None

    connection = connect_db(settings.sqlite_db_path)
    try:
        init_db_schema(connection)
        if not has_workout_data(connection):
            manifests = load_workout_manifests(Path(settings.puma_data_root))
            if not manifests:
                startup_error = f"No manifest files found under: {settings.puma_data_root}"
                return
            ingest_manifests(connection, manifests)
        chunks = load_chunks_from_db(connection)
    finally:
        connection.close()

    if not chunks:
        startup_error = "No chunks could be built from database records."
        return

    retriever = HybridRetriever(
        embedding_model_name=settings.embedding_model_name,
        rrf_k=settings.rrf_k,
    )
    if settings.faiss_index_path.exists() and _cached_index_matches(settings.chunks_json_path, len(chunks)):
        retriever.load(settings.faiss_index_path, settings.chunks_json_path)
    else:
        retriever.build(chunks)
        retriever.save(settings.faiss_index_path, settings.chunks_json_path)
        settings.chunks_json_path.with_name("index.version").write_text(INDEX_CACHE_VERSION, encoding="utf-8")

    try:
        llm = build_llm(settings)
    except (ValueError, RuntimeError) as error:
        startup_error = str(error)
        return
    workflow = build_workflow(
        retriever=retriever,
        llm=llm,
        faiss_top_k=settings.faiss_top_k,
        bm25_top_k=settings.bm25_top_k,
    )


@app.get("/health")
def health() -> dict[str, str | None]:
    return {"status": "ok" if workflow is not None else "degraded", "error": startup_error}


@app.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    if workflow is None:
        raise HTTPException(
            status_code=503,
            detail=startup_error or "Workflow is not initialized.",
        )

    try:
        result = workflow.invoke({"query": payload.query})
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return QueryResponse(
        answer=result["answer"],
        intent=result["intent"],
        citations=result["retrieved_items"],
        render_payload=result["render_payload"],
    )


@app.post("/voice-query", response_model=QueryResponse)
def voice_query(audio: UploadFile = File(...)) -> QueryResponse:
    if workflow is None:
        raise HTTPException(
            status_code=503,
            detail=startup_error or "Workflow is not initialized.",
        )

    suffix = Path(audio.filename or "query.wav").suffix or ".wav"
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio.file.read())
        tmp_path = tmp.name

    transcript = get_stt_engine().transcribe_file(tmp_path)
    try:
        result = workflow.invoke({"query": transcript})
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return QueryResponse(
        answer=result["answer"],
        intent=result["intent"],
        citations=result["retrieved_items"],
        render_payload=result["render_payload"],
    )
