from app.rag.vectorstore import get_vectorstore


def retrieve_policy(query: str, k: int = 3):
    vectorstore = get_vectorstore()

    results = vectorstore.similarity_search(
        query,
        k=k
    )

    return results


if __name__ == "__main__":
    query = "What action should be taken for an invoice that is 16 to 30 days overdue?"

    results = retrieve_policy(query)

    for i, document in enumerate(results, start=1):
        print(f"\n--- Policy Result {i} ---")
        print(document.page_content)
        print("Source:", document.metadata.get("source"))