from app.rag.retriever import retrieve_policy


def get_policy_recommendation(overdue_days: int):
    """
    Get the company's collection policy for the
    current invoice overdue period.
    """

    query = (
        f"What is the collection policy for an invoice "
        f"that is {overdue_days} days overdue?"
    )

    documents = retrieve_policy(query)

    if not documents:
        return {
            "action": "Manual Review",
            "reason": "No matching company policy was found.",
            "policy_sources": [],
        }

    # Use the strongest retrieved policy rule.
    policy = documents[0]

    content = policy.page_content
    source = policy.metadata.get(
        "source",
        "Company Policy",
    )

    # Simple policy-action extraction.
    content_upper = content.upper()

    if "FRIENDLY REMINDER" in content_upper:
        action = "Friendly Reminder"

    elif "FORMAL REMINDER" in content_upper:
        action = "Formal Reminder"

    elif "ESCALATION REVIEW" in content_upper:
        action = "Escalation Review"

    elif "ESCALATION" in content_upper:
        action = "Escalation"

    else:
        action = "Follow Company Policy"

    return {
        "action": action,
        "reason": content,
        "policy_sources": [source],
    }
