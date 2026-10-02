from celery.signals import worker_process_init
from sentence_transformers import (
    SentenceTransformer,
)

_model = None


# I was going to quantize the model and run it with onnx but there is already one that is optimized on huggingface
# so using it
def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2",
            device="cpu",
            backend="onnx",
            model_kwargs={
                "file_name": "onnx/model_O3.onnx",  # Uses pre-optimized ONNX graph from HF
            },
            local_files_only=True,
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
