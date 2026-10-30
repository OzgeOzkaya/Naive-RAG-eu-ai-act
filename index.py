import json
import os

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

load_dotenv()
DB_URL = os.environ["DATABASE_URL"]

# Step 1: load the chunks written by parse.py
with open("./outputs/chunks.json", encoding="utf-8") as f:
    chunks = json.load(f)
texts = [c["text"] for c in chunks]
print("Chunks:", len(chunks))

# Step 2: check how many chunks are longer than the model limit
model = SentenceTransformer("all-MiniLM-L6-v2")
token_counts = [len(model.tokenizer.tokenize(t)) for t in texts]
print("Model limit:", model.max_seq_length, "tokens")
print("Max tokens in a chunk:", max(token_counts), "| over the limit:", sum(c > model.max_seq_length - 2 for c in token_counts))

# Step 3: embed
embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)

# Step 4: create the table and store
conn = psycopg.connect(DB_URL, autocommit=True)
conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
register_vector(conn)

conn.execute("DROP TABLE IF EXISTS ai_act_chunks")
conn.execute("""
    CREATE TABLE ai_act_chunks (
        id SERIAL PRIMARY KEY,
        article TEXT,
        title TEXT,
        page INT,
        content TEXT,
        embedding vector(384)
    )
""")

for chunk, emb in zip(chunks, embeddings):
    conn.execute(
        "INSERT INTO ai_act_chunks (article, title, page, content, embedding) VALUES (%s, %s, %s, %s, %s)",
        (chunk["article"], chunk["title"], chunk["page"], chunk["text"], emb),
    )

print("Rows stored:", conn.execute("SELECT count(*) FROM ai_act_chunks").fetchone()[0])