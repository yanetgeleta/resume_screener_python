from celery.signals import worker_process_init
from huggingface_hub import snapshot_download
from sentence_transformers import (
    SentenceTransformer,
)

# I was going to quantize the model and run it with onnx but there is already one that is optimized on huggingface
# so using it
_model: SentenceTransformer | None = None
MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        try:
            # Resolves the cached folder path on disk without network access
            local_model_path = snapshot_download(
                repo_id=MODEL_ID,
                local_files_only=True,
            )
        except Exception:
            local_model_path = MODEL_ID
        _model = SentenceTransformer(
            local_model_path,
            device="cpu",
            backend="onnx",
            model_kwargs={
                "file_name": "onnx/model_O3.onnx",  # Uses pre-optimized ONNX graph from HF
            },
        )
    return _model


@worker_process_init.connect
def _init_worker(**kwargs):
    _get_model()


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    model = _get_model()
    embeddings = model.encode(chunks, normalize_embeddings=True)
    return embeddings.tolist()


def embed_text(text: str) -> list[float]:
    model = _get_model()
    embeddings = model.encode(text, normalize_embeddings=True)
    return embeddings.tolist()
