from langchain_core.documents import Document

from app.rag.vectorstore import get_vectorstore, load_policy_documents


def ingest_policies():
    policy_data = load_policy_documents()

    if not policy_data:
        print("No policy documents found.")
        return

    documents = []

    for item in policy_data:
        sections = item["content"].split("\n\n")

        for section in sections:
            section = section.strip()

            if section:
                documents.append(
                    Document(
                        page_content=section,
                        metadata={
                            "source": item["source"]
                        },
                    )
                )

    vectorstore = get_vectorstore()

    existing = vectorstore.get()

    if existing.get("ids"):
        vectorstore.delete(ids=existing["ids"])

    vectorstore.add_documents(documents)

    print(f"Successfully ingested {len(documents)} policy rules.")


if __name__ == "__main__":
    ingest_policies()