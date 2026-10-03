from pathlib import Path

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from pypdf import PdfReader


BASE_DIR = Path(__file__).resolve().parents[2]

POLICY_DIR = BASE_DIR / "data" / "policies"
CHROMA_DIR = BASE_DIR / "chroma_db"


def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )


def get_vectorstore():
    return Chroma(
        collection_name="cashflow_policies",
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )


def load_policy_documents():
    documents = []

    # TXT policy files
    for file_path in POLICY_DIR.glob("*.txt"):

        text = file_path.read_text(
            encoding="utf-8"
        )

        if text.strip():
            documents.append(
                {
                    "content": text,
                    "source": file_path.name,
                }
            )

    # PDF policy files
    for file_path in POLICY_DIR.glob("*.pdf"):

        reader = PdfReader(str(file_path))

        pages = []

        for page in reader.pages:

            text = page.extract_text() or ""

            if text.strip():
                pages.append(text)

        full_text = "\n\n".join(pages)

        if full_text.strip():

            documents.append(
                {
                    "content": full_text,
                    "source": file_path.name,
                }
            )

    return documents