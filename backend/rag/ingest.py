from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_ollama import OllamaEmbeddings
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
embeddings_model = OllamaEmbeddings(
    model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
)

# 1. Load documents
loader = DirectoryLoader(
    "data/courses/",
    glob="**/*.md",
    loader_cls=TextLoader
)
docs = loader.load()

# 2. Chunking
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n## ", "\n### ", "\n\n", "\n", " "]
)
chunks = splitter.split_documents(docs)

# 3. Generate embeddings and insert into Supabase
for i, chunk in enumerate(chunks):
    embedding = embeddings_model.embed_query(chunk.page_content)

    # Extract level from file path (beginner/intermediate/advanced)
    source_path = chunk.metadata.get("source", "")
    level = "all"
    for lvl in ["beginner", "intermediate", "advanced"]:
        if lvl in source_path:
            level = lvl
            break

    supabase.table("documents").insert({
        "content": chunk.page_content,
        "embedding": embedding,
        "metadata": {
            "source": source_path,
            "level": level
        },
        "source_type": "course"
    }).execute()

    print(f"  [{i+1}/{len(chunks)}] Ingested chunk from {source_path}")

print(f"\nDone. Ingested {len(chunks)} chunks.")
