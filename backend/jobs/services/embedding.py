from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    embeddings = _model.encode(chunks)
    return embeddings.tolist()
