from dotenv import load_dotenv
load_dotenv()

from retriever import retrieve_context

print("=== Query: How do I introduce myself in English? ===")
results = retrieve_context(
    query="How do I introduce myself in English?",
    source_type="course",
    level="beginner",
    k=3
)

for r in results:
    print(f"\n[{r['similarity']:.3f}] {r['content'][:150]}...")

print("\n=== Query: present perfect vs simple past ===")
results = retrieve_context(
    query="When should I use present perfect instead of simple past?",
    source_type="course",
    level="intermediate",
    k=3
)

for r in results:
    print(f"\n[{r['similarity']:.3f}] {r['content'][:150]}...")
