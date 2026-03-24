from langchain_ollama import OllamaEmbeddings
from supabase import create_client
import os

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

embeddings_model = OllamaEmbeddings(
    model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
)
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def retrieve_context(query: str, source_type: str = None, level: str = None, k: int = 5, verbose: bool = True):
    """Search for the most relevant chunks in pgvector."""

    if verbose:
        print(f"\n        {MAGENTA}╔══ RAG SEARCH ══════════════════════════════════{RESET}")
        print(f"        {MAGENTA}║{RESET} Query: {BOLD}\"{query}\"{RESET}")
        print(f"        {MAGENTA}║{RESET} Filters: source={source_type}, level={level}, k={k}")

    if verbose:
        print(f"        {MAGENTA}║{RESET}")
        print(f"        {MAGENTA}║{RESET} {CYAN}Generating embedding with nomic-embed-text...{RESET}")
    query_embedding = embeddings_model.embed_query(query)

    if verbose:
        # Show first and last 5 values of the 768-dim vector
        first5 = ", ".join([f"{v:.4f}" for v in query_embedding[:5]])
        last5 = ", ".join([f"{v:.4f}" for v in query_embedding[-5:]])
        print(f"        {MAGENTA}║{RESET} Vector ({len(query_embedding)} dims): [{first5}, ... , {last5}]")

    if verbose:
        print(f"        {MAGENTA}║{RESET}")
        print(f"        {MAGENTA}║{RESET} {CYAN}Searching pgvector (cosine similarity)...{RESET}")

    result = supabase.rpc("match_documents", {
        "query_embedding": query_embedding,
        "match_count": k,
        "filter_source": source_type,
        "filter_level": level
    }).execute()

    docs = [
        {"content": doc["content"], "metadata": doc["metadata"], "similarity": doc["similarity"]}
        for doc in result.data
        if doc["similarity"] is not None
    ]

    if verbose:
        print(f"        {MAGENTA}║{RESET} Found {len(docs)} results:")
        for i, doc in enumerate(docs):
            score = doc["similarity"] or 0.0
            # Color based on similarity score
            if score >= 0.7:
                score_color = GREEN
            elif score >= 0.5:
                score_color = YELLOW
            else:
                score_color = RED
            preview = doc["content"][:80].replace("\n", " ")
            level_info = doc["metadata"].get("level", "?")
            print(f"        {MAGENTA}║{RESET}   {score_color}[{score:.3f}]{RESET} ({level_info}) {DIM}{preview}...{RESET}")
        print(f"        {MAGENTA}╚══════════════════════════════════════════════════{RESET}\n")

    return docs
