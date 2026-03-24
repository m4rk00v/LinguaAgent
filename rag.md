# RAG Pipeline — Files

## What is RAG?

RAG stands for **Retrieval Augmented Generation**. It solves a key problem: you can't pass all your course content to the LLM on every question (context limits + cost). Instead:

1. **Retrieval** — The student asks something. The question is converted into an embedding and pgvector finds the most similar chunks from the course content.
2. **Augmented** — Those relevant chunks are injected into the LLM prompt as context.
3. **Generation** — The LLM (llama3) responds using that context.

```
Student: "How do I use present perfect?"
        │
        ▼
   ┌─────────────────────────────────────┐
   │ 1. RETRIEVAL                        │
   │    Question → embedding → pgvector  │
   │    finds top-K similar chunks       │
   └──────────┬──────────────────────────┘
              │ relevant chunks
              ▼
   ┌─────────────────────────────────────┐
   │ 2. AUGMENTED                        │
   │    Chunks injected into LLM prompt: │
   │    "You are an English teacher...   │
   │     Course Material: {chunks}"      │
   └──────────┬──────────────────────────┘
              │
              ▼
   ┌─────────────────────────────────────┐
   │ 3. GENERATION                       │
   │    LLM (llama3) responds using      │
   │    the context, not from memory     │
   └─────────────────────────────────────┘
```

Embeddings act as a **semantic index**. In a traditional database you index by exact values (ID, email, date). With embeddings you index by **meaning**, so the system finds relevant content even if the student uses different words than the course material.

---

## Course Content (`backend/data/courses/`)

Educational material ingested into pgvector so agents can use it as context.

### Beginner
| File | Content |
|------|---------|
| `greetings.md` | Greetings, introductions, common mistakes ("I have 25 years") |
| `basic_verbs.md` | Present simple: structure, don't/doesn't, conjugation errors |
| `daily_routines.md` | Daily routine vocabulary, time expressions |

### Intermediate
| File | Content |
|------|---------|
| `present_perfect.md` | Have/has + past participle, difference with simple past, key words (ever, never, yet) |
| `conditionals.md` | First, second and third conditional with examples and common mistakes |
| `phrasal_verbs.md` | Phrasal verbs for daily life, work and social contexts |

### Advanced
| File | Content |
|------|---------|
| `idiomatic_expressions.md` | Business and everyday idiomatic expressions |
| `formal_writing.md` | Formal vs informal register, email structure, contractions |

## RAG Scripts (`backend/rag/`)

| File | Purpose |
|------|---------|
| `ingest.py` | Reads course `.md` files, splits them into chunks (~500 tokens), generates embeddings with Ollama (`nomic-embed-text`) and inserts them into the `documents` table in Supabase |
| `retriever.py` | Takes a text query, generates its embedding and searches for the most similar chunks in pgvector using the `match_documents` function |
| `test_rag.py` | Tests the full pipeline: runs sample queries and displays results with their similarity score |

## What is an Embedding?

An embedding is a numerical representation of the meaning of a text. The model `nomic-embed-text` takes a text like "How do I introduce myself?" and converts it into an array of 768 numbers, e.g. `[0.023, -0.145, 0.087, ...]`.

Texts with similar meaning produce vectors that are close to each other in this 768-dimensional space. So "How do I introduce myself?" will be closer to "Greetings and Introductions" than to "Present Perfect".

This enables **semantic search**: instead of matching exact keywords, you search by meaning. pgvector calculates the cosine distance between the query vector and the stored vectors, and returns the closest matches.

```
"How do I introduce myself?"
        │
        ▼
  nomic-embed-text (Ollama)
        │
        ▼
  [0.023, -0.145, 0.087, ... ] (768 numbers)
        │
        ▼
  pgvector: compare against all stored embeddings
        │
        ▼
  Top-K most similar chunks returned
```

### How Vector Comparison Works

The 768 numbers in an embedding are **not probabilities** — they are **coordinates in a 768-dimensional space**. Each text becomes a point in this space. Texts with similar meaning land as nearby points.

pgvector calculates the **cosine similarity** between vectors: the cosine of the angle between two points. A score of 1.0 means identical meaning, 0.0 means completely unrelated.

```
768-dim space (simplified to 2D):

        "greetings"  ← score 0.674 (close)
           •
          /
         / 28°
        /
       • ← "I have 25 years" (query)
        \
         \ 58°
          \
           •
        "present perfect" ← score 0.459 (farther)
```

### Interpreting Similarity Scores

| Score | Meaning | Example |
|-------|---------|---------|
| >= 0.7 | Very relevant | Query about greetings → greetings chunk |
| 0.5 - 0.7 | Relevant | Query about greetings → daily routines chunk (some overlap) |
| < 0.5 | Low relevance | Query about greetings → present perfect chunk (different topic) |

The retriever returns the top-K results sorted by similarity. The agent uses all of them as context, but the most similar chunks have the most influence on the LLM response.

## How to Run

```bash
cd /data/users/engineer/projects/LinguaAgent/backend
source venv/bin/activate

# Ingest course content into pgvector
python3 rag/ingest.py

# Test semantic search
cd rag
python3 test_rag.py
```

**Important:** Always run `ingest.py` from the `backend/` directory (not from `rag/`), because the path `data/courses/` is relative to `backend/`.

## Ingestion Results (2026-03-23)

8 markdown files → 15 chunks ingested into Supabase `documents` table.

| Source | Chunks |
|--------|--------|
| `beginner/greetings.md` | 1 |
| `beginner/basic_verbs.md` | 1 |
| `beginner/daily_routines.md` | 1 |
| `intermediate/present_perfect.md` | 2 |
| `intermediate/conditionals.md` | 2 |
| `intermediate/phrasal_verbs.md` | 3 |
| `advanced/idiomatic_expressions.md` | 2 |
| `advanced/formal_writing.md` | 3 |
| **Total** | **15** |

Each chunk has a 768-dimension embedding generated by Ollama `nomic-embed-text`, stored in the `embedding` column of the `documents` table. The `match_documents` function in Supabase can now perform semantic search over these chunks.
