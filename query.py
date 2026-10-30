import os

import anthropic
import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

load_dotenv()
DB_URL = os.environ["DATABASE_URL"]
MODEL = "claude-haiku-5-5"
TOP_K = 4
THRESHOLD = 0.30   # starting guess, tune it with real questions

client = anthropic.Anthropic()
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# Step 1: take the question and embed it
question = input("Question: ")
query_embedding = embedder.encode([question], normalize_embeddings=True)[0]

# Step 2: find the closest chunks
conn = psycopg.connect(DB_URL)
register_vector(conn)

rows = conn.execute(
    """
    SELECT article, page, content, 1 - (embedding <=> %s) AS score
    FROM ai_act_chunks
    ORDER BY embedding <=> %s
    LIMIT %s
    """,
    (query_embedding, query_embedding, TOP_K),
).fetchall()

for article, page, _, score in rows:
    print(f"score={score:.2f} | {article} | page {page}")

# Step 3: refuse early if even the best chunk is not close enough
if rows[0][3] < THRESHOLD:
    print("\nAnswer: I cannot find this in the document.")
    raise SystemExit

# Step 4: build the context (each chunk starts with its "Article N - Title" label)
context = "\n\n".join(content for _, _, content, _ in rows)

system_prompt = (
    "Answer the question using ONLY the context below, which contains excerpts of the EU AI Act. "
    "Cite the article(s) you used in the form (Article N). "
    "If the answer is not in the context, say you cannot find it."
)

# Step 5: ask Claude
response = client.messages.create(
    model=MODEL,
    max_tokens=2500,
    system=system_prompt,
    messages=[{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
)

answer = "".join(b.text for b in response.content if b.type == "text")
print("\nAnswer:", answer)

usage = response.usage
thinking = usage.output_tokens_details.thinking_tokens or 0
print("Input token:", usage.input_tokens)
print(f"Total output token: {usage.output_tokens} (response: {usage.output_tokens - thinking}, thinking: {thinking})")