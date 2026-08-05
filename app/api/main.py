from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, HTTPException, UploadFile

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

retriever: HybridRetriever | None = None
workflow = None
startup_error: str | None = None
stt_engine = SpeechToText(model_name="base")


def _cached_index_matches(chunks_json_path: Path, db_chunks_count: int) -> bool:
    if not chunks_json_path.exists():
        return False
    payload = json.loads(chunks_json_path.read_text(encoding="utf-8"))
    return len(payload) == db_chunks_count


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

    transcript = stt_engine.transcribe_file(tmp_path)
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
