# RAG Visualizer Presentation — Run Script (2026-10-01)

Slide deck: https://claude.ai/artifact/PkrZk4AmXbjpwcnRuQKsj3 (8 slides, ~10 min, matches this script section-by-section)

## Before you walk in (do this tonight or early tomorrow, needs wifi)

1. Make sure the **Ollama app** is running (check the system tray — it runs as a background service once started). No manual `ollama serve` needed if it's already up.
2. Both models this project needs are already pulled: `nomic-embed-text` (embeddings) and `hf.co/openbmb/MiniCPM5-1B-GGUF:Q4_K_M` (generation). Nothing to download.
3. The local reranker model (`cross-encoder/ms-marco-MiniLM-L-6-v2`) was **not** cached on this machine before tonight — I ran the full pipeline once to force the download, and it's now cached (~90MB, confirmed present). This was the one thing that would have broken live on bad wifi; it's fixed.
4. The document library is empty — I cleared out old test uploads (from prior debugging sessions) so tomorrow starts clean. Nothing was deleted from disk, just removed from the app's library, so nothing is lost.
5. You do **not** need internet at the venue. I tested the full pipeline (ingest → retrieve → rerank → build context → generate) and the OCR path end-to-end tonight, all offline-safe.

**You need 3 things running, each in its own terminal:**

```powershell
# Terminal 1 — Backend
cd D:\Projects\rag-visualizer\backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

```powershell
# Terminal 2 — Frontend
cd D:\Projects\rag-visualizer\frontend
npm run dev
```

Then open **http://localhost:5173** in your browser. (Ollama is terminal 0 — already running in the background, nothing to start.)

Quick health check before you go on:
```powershell
curl http://localhost:8000/api/health
```
Should return `{"status":"ok"}`.

---

## Slide 1 — Cover

> "Today I'm talking about Retrieval-Augmented Generation — RAG — and specifically, a tool I built to make it *transparent*. Every stage of the pipeline — chunking, embeddings, retrieval, reranking, generation — is something you can actually watch happen, not just a black box that spits out an answer. Everything today runs entirely locally on this laptop, no cloud, no API keys, no internet needed."

---

## Slide 2 — The Problem: LLMs Don't Actually Know Your Documents

- A model's training data has a cutoff — it can't know about a PDF you just handed it.
- Left alone, it will often guess fluently rather than admit it doesn't know — hallucination.
- Most RAG demos you'll find online show one polished final answer and hide the actual retrieval mechanics that made it right (or wrong).
- This project's whole point: expose every stage, so you can see *why* an answer was given, not just trust that it was.

---

## Slide 3 — What is RAG?

- Core idea: before answering, retrieve real passages from your own documents and hand them to the LLM as evidence.
- **Open-book exam analogy**: an LLM alone is a closed-book exam — it answers from memory, which can be wrong or outdated. RAG is an open-book exam — it's handed the right pages first, then answers from what's actually in front of it.
- Flow: Your Documents → Retrieval → Grounded Answer.

---

## Slide 4 — Core Pipeline Stages

Four stages, narrate each briefly:
- **Chunking** — documents are split into parent chunks (larger, for context) and child chunks (smaller, for precise search) — "search small, retrieve big."
- **Embedding** — every child chunk becomes a vector using a local Ollama embedding model.
- **Retrieval** — cosine similarity search pulls the Top-K chunks closest to the query.
- **Reranking** — a cross-encoder rescoring pass reorders those candidates for precision before they reach the LLM.

> "These four stages are exactly what the live demo walks through, one button at a time."

---

## Slide 5 — Architecture & Flow

- Point at the 4-stage row: Ingestion → Structure → Retrieval Inspector → Final Answer — these are literally the four tabs in the app.
- Architecture: React frontend talks to a FastAPI backend, which talks to three local services — SQLite (holding the vectors), Ollama (embeddings + generation), and a local cross-encoder model (reranking).
- "Every box in this diagram runs on this laptop. That's why this works with no wifi."

---

## Slide 6 — Why Reranking Matters

- Vector search compares independently-computed embeddings — fast, scales well, but only approximate.
- Cross-encoder reranking scores the query and the chunk *together* — slower, so it only runs on the small Top-K set, but far more precise, and can reorder what vector search got wrong.
- Walk through the example table: a chunk ranked #4 by vector search jumps to #1 after reranking.
- "Similarity and rerank scores are on different scales — what matters is the *movement*, not the raw numbers. You're about to see this exact view live."

---

## Slide 7 — Live Demonstration *(switch to the running app)*

Open **http://localhost:5173**.

**01 — Ingest a document**
Click **Choose File**, pick `test-docs/01-text-report.pdf` (in the project root). Narrate while it processes: "It's extracting text, splitting into parent/child chunks, and embedding every child chunk — that round trip to Ollama is what takes the second or two."

**02 — Inspect Structure**
The view auto-advances to **2. Document Structure**. Point out the parent → child graph — click a parent node, then a child node, to show the modal with full text. Mention: "This is exactly what got embedded and searched — nothing hidden."

*(Optional, if time allows)*: go back to tab 1, upload `test-docs/02-scanned-invoice.pdf` too, then check its Structure tab — point out the **OCR badge** on the page, since that one has no real text layer and had to be read with Tesseract.

**03 — Retrieval Inspector**
Click **3. Retrieval Inspector**. Type a specific question — tested and reliable tonight:
> **"How does the retrieval pipeline rerank candidates?"**

Click the stage buttons one at a time (not "Run All Stages" — the point is to show each stage's output):
- **1. Retrieve** → top candidates by vector similarity appear.
- **2. Rerank** → before/after comparison, with movement arrows — this is slide 6's table, live.
- **3. Build Context** → selected children resolve back to parent chunks, deduplicated.
- **4. Generate Answer** → the final LLM answer appears, grounded in exactly the context shown above it.

**04 — Final View**
Click **View Full Pipeline Summary** to show the one-screen recap of the whole run.

*(Avoid vague questions like "what is this about" — tested tonight, the small 1B generation model gives a noticeably weaker answer to open-ended questions. A specific question like the one above gives a clean, correct answer.)*

---

## Slide 8 — Conclusion & Key Takeaways

> "Three takeaways: answers here are grounded in retrieved evidence, not guessed from memory. Every stage — chunking, embedding, retrieval, reranking, generation — is inspectable, nothing is a black box. And this exact pipeline shape is what production RAG systems use — swap Ollama for OpenAI or Bedrock, swap SQLite for pgvector or Pinecone, and the architecture doesn't change."

Thank you / Q&A.

---

## Likely Questions & Answers

### Fundamentals

**Q: What's the difference between RAG and fine-tuning?**
A: Fine-tuning changes the model's weights to bake in new knowledge or behavior — expensive, slow, and the knowledge is frozen again the moment training ends. RAG doesn't touch the model at all; it just retrieves relevant text at query time and hands it over as context. You can update your documents and the next query sees it instantly — no retraining.

**Q: Why split into parent and child chunks instead of just one chunk size?**
A: It's a tradeoff. Small chunks embed and search precisely — a tightly focused chunk matches a specific query well. But small chunks lack surrounding context for the LLM to actually answer from. So we search on the small "child" chunks for precision, then hand the LLM the larger "parent" chunk it belongs to for context — "search small, retrieve big."

**Q: What is an embedding, actually?**
A: A vector — a list of numbers — that represents the meaning of a piece of text, produced by a model trained so that semantically similar text ends up as nearby vectors. Comparing two embeddings with cosine similarity tells you roughly how related two pieces of text are, without either containing the other's exact words.

**Q: Why does reranking need a different model than embedding?**
A: The embedding model encodes the query and every chunk independently, ahead of time — that's what makes vector search fast, since you're just comparing pre-computed vectors. A cross-encoder instead looks at the query and one chunk together in a single pass, which is far more accurate but too slow to run over an entire corpus — so it only reranks the small Top-K shortlist vector search already narrowed down.

**Q: Why SQLite instead of a real vector database?**
A: At this scale — one demo, a few hundred chunks — brute-force cosine similarity in SQLite is fast enough, has zero moving parts to keep alive during a live demo, and is debuggable with a text editor. A dedicated vector database (Pinecone, Qdrant, pgvector) becomes worth the operational overhead once you're at real scale — millions of chunks, multiple concurrent users.

### Project-specific

**Q: Why build a visualizer instead of just a chatbot on top of RAG?**
A: Because RAG quality lives entirely in the retrieval step, and a chatbot UI hides exactly that. If the final answer is wrong, a plain chatbot gives you no way to tell whether retrieval found the wrong chunks, reranking demoted the right one, or the LLM just answered badly despite good context. Exposing each stage turns "the AI got it wrong" into an actual debuggable pipeline.

**Q: How does OCR work here, and when does it kick in?**
A: Every page is first checked for a real embedded text layer (most PDFs have one). If a page has no usable text layer — a scanned image, basically a photo of a document — Tesseract OCR runs on it instead. The Structure tab shows exactly which pages were OCR'd, so it's never silently guessing.

**Q: Why a 1B-parameter model for generation instead of something bigger?**
A: Mainly resource/speed tradeoffs for a live, local demo — and it doubles as a demonstration that RAG lifts even a small model's answer quality by handing it the right context, instead of relying on a huge model's memorized knowledge. It performs noticeably better on specific questions than vague ones, which is itself a useful thing to point out live.

**Q: What happens if I ask a question with no good answer in the documents?**
A: The system prompt explicitly tells the model to say so rather than guess, if the retrieved context doesn't contain enough information. That's a deliberate design choice — a RAG system that hallucinates when retrieval comes up empty defeats the whole purpose.

**Q: Could this scale to many documents / production traffic?**
A: The pipeline shape would stay the same, but the storage layer wouldn't — SQLite's brute-force search is fine for a demo, but you'd move to a proper vector database at scale. The rest — chunking, embedding, reranking, generation — scales pretty directly, it's mostly a matter of running it as a service instead of a single local process.

---

## Quick recovery notes (just in case, don't need to show these)

- If ingestion fails at `embed_children`: Ollama isn't running — check the system tray / `curl http://localhost:11434/api/tags`.
- If reranking is slow the first time you run it *tomorrow*: it shouldn't be — the model is already cached from tonight's test. If it does hang, check for a wifi prompt; there shouldn't be one.
- If you want a guaranteed-good demo question and don't want to think of one live, use exactly: **"How does the retrieval pipeline rerank candidates?"** — tested tonight, gives a clean, correct answer.
- Everything in this script — ingestion, OCR, retrieve, rerank, build-context, generate, and the frontend UI — was tested end-to-end tonight and worked offline.
