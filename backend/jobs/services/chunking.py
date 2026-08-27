from celery.signals import worker_process_init
from transformers import AutoTokenizer

_tokenizer = None


def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained(
            "sentence-transformers/all-MiniLM-L6-v2"
        )
    return _tokenizer


@worker_process_init.connect
def _init_worker(**kwargs):
    _get_tokenizer()


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 20) -> list[str]:
    if not text.strip():
        raise ValueError(
            "Cannot chunk empty text - PDF may be image-based or unreadable"
        )
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    tokenizer = _get_tokenizer()
    input_ids = tokenizer(text, add_special_tokens=False, truncation=False)["input_ids"]

    step = chunk_size - overlap
    chunks: list[str] = []
    for i in range(0, len(input_ids), step):
        window = input_ids[i : i + chunk_size]
        chunks.append(tokenizer.decode(window))
    return chunks
