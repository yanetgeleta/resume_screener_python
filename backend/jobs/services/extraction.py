import pymupdf


def extract_text(file_path: str) -> str:
    """This will extract text from pdf file and return it"""
    with pymupdf.open(file_path) as doc:
        text = chr(12).join(str(page.get_text()) for page in doc)
        return text
