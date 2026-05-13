import re

with open('paper.txt', 'r') as f:
    text = f.read()

# Split by newlines and find headings or paragraphs mentioning architecture
lines = text.split('\n')
for i, line in enumerate(lines):
    if re.search(r'(?i)^(3|4)\.?\s+(Proposed Method|Architecture|Network|Model)', line):
        print(f"--- Section Found at {i} ---")
        print("\n".join(lines[i:i+50]))
        print("----------------------------")

