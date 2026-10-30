# Naive RAG on the EU AI Act

A small retrieval-augmented generation (RAG) project that answers questions about the EU AI Act
(Regulation (EU) 2024/1689) and cites the articles it used. Built from scratch, without an
orchestration framework, to understand every step of the pipeline.

> Not legal advice. Always check answers against the official text.

## How it works

```
PDF -> clean -> split by Article/Annex -> chunk -> embed -> pgvector
                                                              |
question -> embed -> nearest chunks -> threshold check -> Claude -> answer with (Article N)
```

1. **Parse:** read the PDF page by page, drop repeated headers/footers, split into articles and annexes with regex.
2. **Chunk:** inside each article, pack paragraphs and list items into chunks of up to 150 words
   (long paragraphs are cut into windows with 30 words overlap). Each chunk starts with an
   `Article N - Title` label so it keeps its context.
3. **Embed and store:** `all-MiniLM-L6-v2` (384 dimensions), stored in Postgres with pgvector.
4. **Retrieve:** cosine similarity search for the top 4 chunks.
5. **Refuse early:** if the best similarity is below a threshold, answer "I cannot find this in the document" without calling the LLM.
6. **Generate:** Claude answers using only the retrieved chunks and cites the articles.

## Stack

- Python, `pypdf`, `sentence-transformers`
- Postgres + `pgvector` (Docker)
- Anthropic API (Claude Haiku)

## Setup

1. Clone and create a virtual environment:

```bash
git clone https://github.com/OzgeOzkaya/Naive-RAG-eu-ai-act.git
cd Naive-RAG-eu-ai-act
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

2. Create a `.env` file (see `.env.example`):

```text
ANTHROPIC_API_KEY=your-key-here
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
```

3. Start Postgres with pgvector (needs Docker Desktop):

```bash
docker run -d --name pgvector-db -e POSTGRES_PASSWORD=postgres -p 5432:5432 -v pgdata:/var/lib/postgresql/data pgvector/pgvector:pg17
```

4. Download the AI Act PDF from the official source
   (http://data.europa.eu/eli/reg/2024/1689/oj) and save it as `documents/EU AI Act.pdf`.

## Run

```bash
python parse.py     # clean, split and chunk -> outputs/chunks.json
python index.py     # embed and store in pgvector
python query.py     # ask questions
```

Example question: `What are the penalties for non-compliance?`
The retrieved chunks come from Article 99, and the answer lists the fine levels with their paragraph citations.

## Design notes

- **Structure-based chunking:** articles are natural units in legal text, so chunks never mix two articles.
- **Token limit:** the embedding model reads at most 256 tokens, so chunks are kept around 150 words.
- **Similarity threshold:** scores are relative, so the threshold (default 0.30) must be tuned on real questions.
- **Thinking tokens count toward `max_tokens`:** with a small limit the answer can be cut off, check `stop_reason`.
- **Known limitation:** PDF extraction sometimes drops spaces (e.g. `up to3%`).
- `page` metadata is the page where the article starts, not necessarily where the chunk is.

## Possible next steps

- Hybrid search (BM25 + vector) and reranking
- FastAPI service (`/ask`, `/ingest`) and docker compose
- Evaluation set of questions with expected articles
- Compare parsers (PyMuPDF, Docling) on this PDF