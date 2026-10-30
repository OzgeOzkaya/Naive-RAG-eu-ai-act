from pypdf import PdfReader

reader = PdfReader("documents/EU AI Act.pdf")
print(len(reader.pages))

from collections import Counter

# last 200 characters for footers
for n in (0, 30, 60):
    print(f"--- end of page {n + 1} ---")
    print(reader.pages[n].extract_text()[-200:])

# lines that repeat on many pages are probably headers/footers
line_counts = Counter()
for page in reader.pages:
    for line in set(page.extract_text().split("\n")):
        line_counts[line.strip()] += 1

for line, count in line_counts.most_common(8):
    print(count, "|", line)