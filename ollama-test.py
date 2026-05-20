from ollama import chat
import time
import textwrap
import json

def pretty_print(text, width=90):
    print("\n".join(textwrap.wrap(text, width=width)))

start_time = time.perf_counter()

res = chat(
    model='qwen2.5vl:3b',
    messages=[
        {
            'role': 'user',
            'content': 'Extract all text from this document image exactly as it appears. Preserve the original layout, line breaks, and paragraph structure. Return only the extracted text with no additional commentary.',
            'images': ['data/processed_images/0005/0005_page_001.jpeg']
        }
    ]
)

end_time = time.perf_counter()
duration = end_time - start_time

# Extract response
output = res['message']['content']

# Pretty UI-style output
print("\n" + "="*80)
print("🧠 QWEN2.5-VL IMAGE ANALYSIS RESULT")
print("="*80)

pretty_print(output)

print("\n" + "-"*80)
print(f"⏱ Generation time: {duration:.2f} seconds")
print(f"📦 Model: qwen2.5vl:3b")
print("="*80 + "\n")