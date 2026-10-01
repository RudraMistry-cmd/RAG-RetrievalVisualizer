# Data Retrieval in RAG — Presentation Script

Slide deck: https://claude.ai/artifact/PkrZk4AmXbjpwcnRuQKsj3 (10 slides, ~10 min). The talk is about the **concept** of retrieval. The demo app is a bonus for the audience and is not on any slide.

## Slide 1 — Cover

> "Today's topic is retrieval in RAG: how a document is stored so it can be searched, and how a question finds its way back to the few passages worth showing a language model."

## Slide 2 — Why Retrieval?

- Frozen knowledge: a model can't know your PDF or today's numbers.
- Hallucination: it guesses fluently instead of admitting it doesn't know.
- Too much to paste: a model can only read so much per prompt; you can't give it a whole library.
- The fix: at question time, fetch only the few passages that matter and give them as evidence.

## Slide 3 — What is RAG?

- Open-book vs closed-book exam. An LLM alone answers from memory; RAG hands it the right pages first.
- Flow: Your Documents → Retrieval → Grounded Answer. "This talk is the middle box."

## Slide 4 — The Pipeline at a Glance

Five steps. Steps 01–02 happen once, when a document is added. Steps 03–05 happen on every question.
01 Chunking → 02 Embedding → 03 Similarity Search (top 5) → 04 Reranking (top 3) → 05 Context Building.

## Slide 5 — Step 1: Chunking (search small, retrieve big)

- The document is split two ways at once: parent chunks (~1200 characters) and child chunks (~300 characters).
- Small children hold one focused idea, so their vectors match specific questions. But a small piece is too thin to answer from, so the model later gets the larger parent.
- Chunks overlap slightly (50–100 characters) so a sentence cut at a boundary still appears whole somewhere.
- Trade-off to say out loud: too big blurs several topics into one vector; too small loses context.

## Slide 6 — Step 2: Embeddings (meaning as numbers)

- An embedding model turns each chunk into a vector, a fixed-length list of numbers (hundreds long).
- Similar meaning → similar numbers, whatever the wording. "Reset my password" and "forgot my login credentials" share no words but land next to each other; "best pizza nearby" lands far away.
- Each child chunk is embedded once, then stored with its text, parent and page. Later, search only compares numbers.

## Slide 7 — Step 3: Similarity Search (top 5)

- The question is embedded with the same model, so it lands in the same vector space.
- Cosine similarity: how closely two vectors point in the same direction, from -1 to 1. Higher = closer in meaning.
- Score every stored chunk, sort, keep the top 5 (K = 5).
- Point at the diagram: green dots inside the ring are the kept ones, gray are not. The ring is illustrative; real spaces have hundreds of dimensions.

## Slide 8 — Step 4: Reranking (top 3)

- Similarity search compared query and chunk **independently**. Fast, but approximate.
- A cross-encoder reads the query and one chunk **together** in a single pass. Much more precise, but too slow to run on everything, so it only runs on the 5 candidates.
- Walk through the table: the chunk ranked #4 by similarity jumps to #1 after reranking. That is the whole argument for reranking.
- The two scores are on different scales; only the movement in rank matters.

## Slide 9 — Step 5: Building the Context

- The children did the searching. Now each is swapped for its parent, so the model gets surrounding text.
- Deduplicate: 3 children can resolve to 2 parents if two came from the same parent. Each parent is included once, labelled with its source.
- This block plus the question goes to the LLM with the instruction "answer only from this context." That is where retrieval ends and generation begins.

## Slide 10 — Takeaways + Q&A

1. Meaning becomes numbers (chunk + embed).
2. Fast first, precise second (5 → 3).
3. Small to search, big to answer (child finds, parent answers).

> "Chunk, embed, compare, rerank, build context. That whole chain is what retrieval means in RAG."

---

## Bonus demo (not on slides, only if you want visuals)

Do this after slide 9 or during Q&A, briefly. Start it BEFORE you present:

```powershell
# Terminal 1
cd D:\Projects\rag-visualizer\backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

```powershell
# Terminal 2
cd D:\Projects\rag-visualizer\frontend
npm run dev
```

Ollama must be running (system tray). Open http://localhost:5173.

1. Ingestion tab: upload `test-docs/01-text-report.pdf`.
2. Structure tab: click a parent, then a child (this is slide 5 live).
3. Retrieval Inspector: type **"How does the retrieval pipeline rerank candidates?"** and click Retrieve, Rerank, Build Context, Generate one at a time (slides 7, 8, 9 live).
4. Avoid vague questions like "what is this about": the small 1B model answers those poorly. Specific questions work.

Everything the demo needs is local and already cached (embedding model, generation model, reranker model), tested end-to-end. If it misbehaves, skip it; the talk stands without it.

---

## Likely Questions & Answers

**Q: Why not just paste the whole document into the prompt?**
A: Models have a limit on how much they can read per prompt, longer prompts cost more and are slower, and models tend to miss details buried in the middle of long inputs. Retrieval sends only the few relevant passages.

**Q: What is an embedding, actually?**
A: A vector: a list of numbers from a model trained so text with similar meaning gets nearby vectors. Comparing vectors tells you how related two texts are without needing shared words.

**Q: What is cosine similarity, and why use it?**
A: It measures the angle between two vectors, ignoring their length. Two chunks pointing the same direction are similar in meaning even if one is longer. Scores run from -1 to 1.

**Q: Why parent and child chunks instead of one size?**
A: Trade-off. Small chunks embed precisely but lack context to answer from. Large chunks have context but their vectors blur several topics. Searching small and returning large gets both.

**Q: Why retrieve 5 and then keep only 3?**
A: The first pass is cheap but approximate, so it casts a wider net (5) to avoid missing the right chunk. The reranker is precise but slow, so it only runs on those 5 and keeps the best 3. Those numbers are tunable: bigger K raises recall, more candidates cost more time.

**Q: Why does reranking need a different model from embedding?**
A: The embedding model encodes query and chunk separately, ahead of time, which makes search fast. A cross-encoder reads the pair together, so it catches interactions between the exact question and the exact passage, but that costs one model run per pair.

**Q: Isn't reranking redundant if embeddings are good?**
A: Embeddings compress a whole chunk into one vector, which loses detail. Reranking re-checks the shortlist with the full text of both sides. It fixes cases where a chunk is topically close but doesn't actually answer the question.

**Q: What if the answer isn't in the documents?**
A: Retrieval always returns the closest chunks, even if none are good. So the prompt tells the model to say so when the context doesn't contain the answer, instead of guessing.

**Q: Is this how production systems do it?**
A: The shape is the same. At scale the brute-force comparison is replaced by a vector database with approximate nearest-neighbour indexes (pgvector, Pinecone, Qdrant), and many systems add keyword search alongside vector search. The concepts don't change.

**Q: How does a scanned PDF work?**
A: Text is extracted first. If a page has no text layer (it's an image), OCR reads it. After that the pipeline is identical.

---

## Recovery notes

- Ingestion fails at the embedding stage: Ollama isn't running. Check `curl http://localhost:11434/api/tags`.
- Reranker model is already cached on this laptop; no wifi needed.
- If anything about the demo breaks, skip it and go straight to Q&A.
