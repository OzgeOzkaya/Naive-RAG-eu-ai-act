import re
from pypdf import PdfReader
import statistics

reader = PdfReader("documents/EU AI Act.pdf")

# Step 1: footer/header lines to drop
footer_patterns = [
    re.compile(r"^(EN )?OJ L, 12\.7\.2024( EN)?$"),   # "EN OJ L, 12.7.2024" and "OJ L, 12.7.2024 EN"
    re.compile(r"^ELI: .*\d+/144$"),                   # "ELI: http://... 61/144"
]

# Step 2: read page by page, keep (page number, line), drop footers and empty lines
lines = []
for page_number, page in enumerate(reader.pages, start=1):
    for line in page.extract_text().split("\n"):
        line = line.strip()
        if not line or any(p.match(line) for p in footer_patterns):
            continue
        lines.append((page_number, line))

print("Lines kept:", len(lines))

# Step 3: split into articles and annexes by heading lines
article_heading = re.compile(r"^Article (\d+)$")
annex_heading = re.compile(r"^ANNEX ([IVX]+)$")
chapter_heading = re.compile(r"^(CHAPTER|SECTION) [IVX\d]+$")

sections = []
current = None
skipping = False
in_annexes = False   # once the first annex starts, no more real articles
for page_number, line in lines:
    article_match = article_heading.match(line)
    annex_match = annex_heading.match(line)

    if article_match and not in_annexes:
        skipping = False
        current = {"id": f"Article {article_match.group(1)}", "page": page_number, "lines": []}
        sections.append(current)
    elif annex_match:
        skipping = False
        in_annexes = True
        current = {"id": f"Annex {annex_match.group(1)}", "page": page_number, "lines": []}
        sections.append(current)
    elif chapter_heading.match(line):
        skipping = True
    elif current and not skipping:
        current["lines"].append(line)

# Step 4: turn each section's lines into clean text
# (join wrapped lines with a space, but start a new line at list items like "(a)" or "5.")
list_item = re.compile(r"^(\(\w{1,4}\)|\d+\.)\s")
for section in sections:
    text = ""
    for line in section["lines"]:
        text += ("\n" if list_item.match(line) else " ") + line
    section["text"] = text.strip()

# Step 5: sanity checks
articles = [s for s in sections if s["id"].startswith("Article")]
found = {int(s["id"].split()[1]) for s in articles}
print("Articles found:", len(articles), "| Annexes found:", len(sections) - len(articles))
print("First article:", articles[0]["id"], "page", articles[0]["page"])
print("Last article:", articles[-1]["id"], "page", articles[-1]["page"])
print("Missing numbers (1-113):", sorted(set(range(1, 114)) - found))

sample = next(s for s in sections if s["id"] == "Article 14")
print("\n", sample["id"], "page", sample["page"])
print(sample["text"][:600])

leaked = [s["id"] for s in sections if re.search(r"\b(CHAPTER|SECTION) [IVX\d]+\b", s["text"])]
print("Sections still containing chapter/section headings:", leaked)

# to understand section sizes against model limit (256)
word_counts = [len(s["text"].split()) for s in sections]
print("Sections:", len(sections))
print("Min / median / max words:", min(word_counts), "/", statistics.median(word_counts), "/", max(word_counts))
print("Over 150 words:", sum(c > 150 for c in word_counts))
print("Over 300 words:", sum(c > 300 for c in word_counts))

longest = sorted(sections, key=lambda s: len(s["text"].split()), reverse=True)[:5]
for s in longest:
    print(s["id"], "|", len(s["text"].split()), "words")

# Step 6: chunk every section
max_words = 150
overlap_words = 30

chunks = []
for section in sections:
    title = section["lines"][0] if section["lines"] else ""
    body = section["text"].removeprefix(title).strip()
    label = f"{section['id']} - {title}"

    # 6a: split the body into pieces (paragraphs / list items); cut very long ones into windows
    pieces = []
    for item in body.split("\n"):
        words = item.split()
        if len(words) <= max_words:
            pieces.append(item)
            continue
        start = 0
        while start < len(words):
            pieces.append(" ".join(words[start:start + max_words]))
            if start + max_words >= len(words):
                break
            start += max_words - overlap_words

    # 6b: pack pieces into chunks of at most max_words
    current_text = ""
    for piece in pieces:
        if current_text and len(current_text.split()) + len(piece.split()) > max_words:
            chunks.append({"article": section["id"], "title": title, "page": section["page"],
                           "text": f"{label}\n{current_text}"})
            current_text = piece
        else:
            current_text = (current_text + "\n" + piece).strip()
    if current_text:
        chunks.append({"article": section["id"], "title": title, "page": section["page"],
                       "text": f"{label}\n{current_text}"})

chunk_words = [len(c["text"].split()) for c in chunks]
print("\nChunks:", len(chunks))
print("Min / median / max words:", min(chunk_words), "/", statistics.median(chunk_words), "/", max(chunk_words))

for c in [c for c in chunks if c["article"] == "Article 14"][:2]:
    print("\n---", c["article"], "| page", c["page"])
    print(c["text"])

# Strucre-based + recursive +Fixed-size fallback
import json
import os

os.makedirs("outputs", exist_ok=True)

with open("outputs/chunks.json", "w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False, indent=2)
print("Saved outputs/chunks.json")