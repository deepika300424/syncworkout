# Workout Voice RAG + LangGraph + Gemini: Best Approach

## 1) Core objective
Build a voice-enabled multi-agent system that:
- understands spoken user workout queries,
- retrieves grounded results from Puma workout manifests/media metadata,
- responds with Gemini-generated answers plus explicit workout/exercise IDs,
- supports follow-up commands like "play intro", "show exercise video", or "next exercise".

## 2) Recommended architecture

### Agents (LangGraph nodes)
1. **Voice I/O Agent**
   - STT: audio -> text command
   - TTS: answer text -> optional spoken response
2. **Router Agent**
   - classify intent: search, explain, navigate, media-action, fallback
3. **RAG Retrieval Agent**
   - query rewriting + metadata filters
   - vector + keyword retrieval over workout/section/exercise chunks
4. **Workout Planner Agent**
   - transforms retrieved data into actionable workout guidance
5. **Response Agent (Gemini)**
   - grounded final response with citations/IDs
6. **Safety/Policy Agent**
   - enforces constraints (medical disclaimers, unsafe requests, hallucination guard)

## 3) Data modeling for your manifest
Create normalized records from each manifest:
- `workout`: workout_id, title, intro path, cover path
- `section`: section_id, workout_id, title
- `exercise`: exercise_id, section_id, workout_id, title, media paths
- `audio_cue`: exercise_id, cue index, path

Generate text chunks such as:
- "Workout: Fit and Strong (workout_id=...)"
- "Section: Circuit (section_id=...)"
- "Exercise: Curtsy Lunge To Squat (exercise_id=...)"
- include media links in metadata, not only plain text.

## 4) Retrieval strategy (hybrid RAG)
Use **hybrid retrieval** for best quality:
1. Dense retrieval (FAISS embeddings)
2. Lexical retrieval (keyword/BM25-style fallback)
3. Metadata filter (if user mentions workout title, section, or ID)
4. Re-rank top-k passages before generation

Recommended answer format:
- short answer,
- bullet list of matched items,
- include `workout_id`, `section_id`, `exercise_id`,
- include media paths (video/preview/audio) when relevant.

## 5) Voice command strategy
Command types:
- "Find a beginner leg workout"
- "Play intro for Fit and Strong"
- "Show exercise Curtsy Lunge To Squat"
- "Next exercise in Circuit"

Pipeline:
1. Voice capture + VAD
2. STT transcript
3. Router intent detection
4. RAG/tool call
5. Gemini response synthesis
6. Optional TTS output

## 6) LangGraph state design
Use a typed state with:
- `user_input_text`
- `user_audio_path`
- `intent`
- `filters` (workout/section/exercise)
- `retrieved_docs`
- `selected_entities`
- `final_answer`
- `citations`
- `action` (e.g., play_video, play_intro, none)
- `errors`

## 7) Hallucination control (must-have)
- Gemini must only answer from retrieved context for catalog questions.
- If confidence is low: respond with "not found in dataset" and suggest nearest matches.
- Always return IDs from source metadata.
- Keep raw manifests as source of truth for media paths.

## 8) Project structure
Suggested layout:
- `app/graph/` -> LangGraph nodes + edges
- `app/agents/` -> router, retrieval, planner, responder
- `app/data/` -> manifest loader, normalization, chunking
- `app/index/` -> embedding + vector store build/load
- `app/voice/` -> mic input, STT, TTS, command parser
- `app/api/` -> FastAPI endpoints (query, voice-query, media-action)
- `app/core/` -> settings, logging, schemas, utilities

## 9) Minimal API endpoints
- `POST /query` (text query)
- `POST /voice-query` (audio file)
- `POST /action` (play/show using IDs)
- `GET /health`

## 10) Implementation order (recommended)
1. Manifest loader + schema validation
2. Chunking + indexing + retrieval evaluation
3. LangGraph single-agent flow (query -> retrieve -> respond)
4. Router + multi-agent split
5. Voice input and voice output
6. Media action support using IDs
7. Guardrails + quality tests

## 11) Quality checks before production
- Retrieval recall on known queries
- Correct ID grounding in responses
- Latency for voice-to-answer
- No hallucinated exercises/workouts
- Stable behavior for ambiguous voice transcripts
