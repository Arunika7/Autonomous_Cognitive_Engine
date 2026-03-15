import os
import logging
from pathlib import Path
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# Basic paths
DB_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "chroma_db"
os.makedirs(DB_DIR, exist_ok=True)

# Using simple local local embedding model (lightweight and free)
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

vector_store = Chroma(
    collection_name="agent_documents",
    embedding_function=embeddings,
    persist_directory=str(DB_DIR)
)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
    is_separator_regex=False,
)

def ingest_document(filename: str, content: str):
    """Chunks the content and adds it to ChromaDB with the filename metadata."""
    try:
        if not content.strip():
            return
            
        chunks = text_splitter.split_text(content)
        docs = [Document(page_content=chunk, metadata={"source": filename}) for chunk in chunks]
        
        # Adding to vector DB
        vector_store.add_documents(documents=docs)
        logger.info(f"Successfully ingrained {len(docs)} chunks from {filename} into Vector Store")
    except Exception as e:
        logger.error(f"Error ingesting document {filename} to Vector Store: {e}")

def search_documents(query: str, k: int = 4) -> list[dict]:
    """Retrieves top k semantically relevant chunks."""
    try:
        results = vector_store.similarity_search(query, k=k)
        formatted = []
        for doc in results:
            formatted.append({
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown")
            })
        return formatted
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        return []
