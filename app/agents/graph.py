from typing import TypedDict, List, Optional, Any

from langgraph.graph import StateGraph, START, END

from app.rag.retriever import retrieve_policy
from app.services.risk_service import calculate_risk
from app.agents.message_agent import generate_collection_message
from app.services.email_service import send_collection_email
from app.services.audit_service import save_audit_event


# ============================================================
# STATE
# ============================================================

class CollectionState(TypedDict, total=False):

    customer_id: str
    customer_name: str
    customer_email: str
    invoice_id: str

    outstanding_amount: float
    overdue_days: int

    payment_status: str
    no_response_count: int
    dispute_type: Optional[str]

    risk_score: int
    risk_level: str
    risk_reasons: List[str]

    policy_query: str
    policy_results: List[str]

    recommended_action: str
    recommendation_reason: List[str]

    generated_message: str

    approval_status: str
    human_approved: bool
    approval_comment: str

    email_sent: bool
    email_status: str


# ============================================================
# RISK NODE
# ============================================================

def risk_node(state: CollectionState):

    overdue_days = state.get(
        "overdue_days",
        0,
    )

    payment_status = state.get(
        "payment_status",
        "unknown",
    )

    outstanding_amount = state.get(
        "outstanding_amount",
        0,
    )

    no_response_count = state.get(
        "no_response_count",
        0,
    )

    risk_input = {
        "overdue_15_plus": (
            1
            if overdue_days >= 15
            else 0
        ),
        "overdue_30_plus": (
            1
            if overdue_days >= 30
            else 0
        ),
        "unpaid_invoices": (
            1
            if payment_status == "unpaid"
            else 0
        ),
        "partially_paid_invoices": (
            1
            if payment_status == "partially_paid"
            else 0
        ),
        "no_response_count": no_response_count,
        "outstanding_amount": outstanding_amount,
    }

    risk_score, risk_reasons = calculate_risk(
        risk_input
    )

    if risk_score >= 70:
        risk_level = "HIGH"

    elif risk_score >= 40:
        risk_level = "MEDIUM"

    else:
        risk_level = "LOW"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_reasons": risk_reasons,
    }


# ============================================================
# POLICY / RAG NODE
# ============================================================

def policy_node(state: CollectionState):

    overdue_days = state.get(
        "overdue_days",
        0,
    )

    payment_status = state.get(
        "payment_status",
        "unknown",
    )

    dispute_type = state.get(
        "dispute_type"
    )

    query = (
        "What collection action should be taken "
        f"when an invoice is {overdue_days} days "
        f"overdue, payment status is "
        f"{payment_status}, and dispute status is "
        f"{dispute_type or 'no active dispute'}?"
    )

    results = retrieve_policy(
        query,
        k=3,
    )

    policy_results = [
        document.page_content
        for document in results
    ]

    return {
        "policy_query": query,
        "policy_results": policy_results,
    }


# ============================================================
# RECOMMENDATION NODE
# ============================================================

def recommendation_node(
    state: CollectionState,
):

    overdue_days = state.get(
        "overdue_days",
        0,
    )

    outstanding_amount = state.get(
        "outstanding_amount",
        0,
    )

    no_response_count = state.get(
        "no_response_count",
        0,
    )

    dispute_type = state.get(
        "dispute_type"
    )

    policy_results = state.get(
        "policy_results",
        [],
    )

    reasons = []

    # --------------------------------------------------------
    # Active dispute takes priority
    # --------------------------------------------------------

    if dispute_type:

        recommended_action = "dispute_review"

        reasons.append(
            f"Active dispute detected: {dispute_type}"
        )

    else:

        recommended_action = "monitor"

        policy_text = " ".join(
            str(policy)
            for policy in policy_results
        ).upper()

        # ----------------------------------------------------
        # Use company policy retrieved from RAG
        # ----------------------------------------------------

        if "MANAGEMENT REVIEW" in policy_text:

            recommended_action = "management_review"

        elif "ESCALATION REVIEW" in policy_text:

            recommended_action = "escalation_review"

        elif "FORMAL REMINDER" in policy_text:

            recommended_action = "formal_reminder"

        elif "FRIENDLY REMINDER" in policy_text:

            recommended_action = "friendly_reminder"

        else:

            # ------------------------------------------------
            # Safe fallback
            # ------------------------------------------------

            if overdue_days > 30:

                recommended_action = "management_review"

            elif overdue_days >= 16:

                recommended_action = "escalation_review"

            elif overdue_days >= 8:

                recommended_action = "formal_reminder"

            elif overdue_days >= 1:

                recommended_action = "friendly_reminder"

            else:

                recommended_action = "monitor"

            reasons.append(
                "No matching company policy action "
                "was found in retrieved RAG results; "
                "default overdue rules were used."
            )

        # ----------------------------------------------------
        # Policy evidence
        # ----------------------------------------------------

        if policy_results:

            reasons.append(
                "Company policy retrieved through RAG:"
            )

            reasons.append(
                policy_results[0]
            )

    # --------------------------------------------------------
    # Overdue
    # --------------------------------------------------------

    if overdue_days > 0:

        reasons.append(
            f"Invoice is {overdue_days} days overdue."
        )

    else:

        reasons.append(
            "Invoice is not overdue."
        )

    # --------------------------------------------------------
    # Outstanding
    # --------------------------------------------------------

    if outstanding_amount > 0:

        reasons.append(
            f"Outstanding balance is "
            f"₹{outstanding_amount:,.2f}."
        )

    # --------------------------------------------------------
    # No response
    # --------------------------------------------------------

    if no_response_count > 0:

        reasons.append(
            f"{no_response_count} communication(s) "
            "received no response."
        )

    return {
        "recommended_action": recommended_action,
        "recommendation_reason": reasons,
    }


# ============================================================
# MESSAGE NORMALIZER
# ============================================================

def normalize_message(message: Any) -> str:
    """
    Convert different AI response formats into plain text.
    """

    # Normal Python dictionary response
    if isinstance(message, dict):

        text_value = message.get(
            "text"
        )

        if text_value:
            return str(text_value).strip()

        content_value = message.get(
            "content"
        )

        if content_value:
            return str(content_value).strip()

        return str(message).strip()

    # LangChain message object
    if hasattr(message, "content"):

        content = message.content

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):

            parts = []

            for item in content:

                if isinstance(item, dict):

                    text_value = item.get(
                        "text"
                    )

                    if text_value:
                        parts.append(
                            str(text_value)
                        )

                else:

                    parts.append(
                        str(item)
                    )

            return "\n".join(parts).strip()

        return str(content).strip()

    return str(message).strip()


# ============================================================
# MESSAGE GENERATION NODE
# ============================================================

def message_node(
    state: CollectionState,
):

    raw_message = generate_collection_message(
        customer_name=state.get(
            "customer_name",
            "",
        ),
        invoice_id=state.get(
            "invoice_id",
            "",
        ),
        outstanding_amount=state.get(
            "outstanding_amount",
            0,
        ),
        overdue_days=state.get(
            "overdue_days",
            0,
        ),
        recommended_action=state.get(
            "recommended_action",
            "monitor",
        ),
        policy_results=state.get(
            "policy_results",
            [],
        ),
    )

    message = normalize_message(
        raw_message
    )

    return {
        "generated_message": message
    }


# ============================================================
# HUMAN APPROVAL NODE
# ============================================================

def approval_node(
    state: CollectionState,
):
    """
    Human-in-the-loop approval.

    Application/API/Streamlit can provide:

        approval_status = "approved"
        approval_status = "rejected"
        approval_status = "pending"

    If no approval status is provided,
    CLI approval is requested.
    """

    provided_status = state.get(
        "approval_status"
    )

    # ========================================================
    # APPLICATION / API / STREAMLIT MODE
    # ========================================================

    if provided_status in {
        "approved",
        "rejected",
        "pending",
    }:

        approval_comment = state.get(
            "approval_comment",
            "",
        )

        if provided_status == "approved":

            print(
                "\n✓ Recommendation approved "
                "from application input."
            )

            return {
                "approval_status": "approved",
                "human_approved": True,
                "approval_comment": (
                    approval_comment
                ),
            }

        if provided_status == "rejected":

            print(
                "\n✗ Recommendation rejected "
                "from application input."
            )

            return {
                "approval_status": "rejected",
                "human_approved": False,
                "approval_comment": (
                    approval_comment
                ),
            }

        print(
            "\nApproval is pending."
        )

        return {
            "approval_status": "pending",
            "human_approved": False,
            "approval_comment": (
                approval_comment
            ),
        }

    # ========================================================
    # CLI MODE
    # ========================================================

    print("\n")
    print("=" * 60)
    print(
        "             HUMAN APPROVAL REQUIRED"
    )
    print("=" * 60)

    print("\nCustomer:")

    print(
        state.get(
            "customer_name",
            "Unknown",
        )
    )

    print("\nCustomer Email:")

    print(
        state.get(
            "customer_email",
            "Unknown",
        )
    )

    print("\nInvoice:")

    print(
        state.get(
            "invoice_id",
            "Unknown",
        )
    )

    print("\nRisk Level:")

    print(
        state.get(
            "risk_level",
            "LOW",
        )
    )

    print("\nRisk Score:")

    print(
        state.get(
            "risk_score",
            0,
        )
    )

    print("\nRecommended Action:")

    print(
        state.get(
            "recommended_action",
            "monitor",
        )
    )

    print("\nRecommendation Reasons:")

    for reason in state.get(
        "recommendation_reason",
        [],
    ):

        print(
            f"- {reason}"
        )

    print("\nGenerated Collection Message:")
    print("-" * 60)

    print(
        state.get(
            "generated_message",
            "",
        )
    )

    print("-" * 60)

    print("\n")
    print("=" * 60)
    print("1. APPROVE")
    print("2. REJECT")
    print("=" * 60)

    decision = input(
        "\nEnter your decision (1/2): "
    ).strip()

    # --------------------------------------------------------
    # APPROVE
    # --------------------------------------------------------

    if decision == "1":

        comment = input(
            "Enter approval comment "
            "(optional): "
        ).strip()

        print(
            "\n✓ Recommendation APPROVED"
        )

        return {
            "approval_status": "approved",
            "human_approved": True,
            "approval_comment": comment,
        }

    # --------------------------------------------------------
    # REJECT
    # --------------------------------------------------------

    if decision == "2":

        comment = input(
            "Enter rejection reason: "
        ).strip()

        print(
            "\n✗ Recommendation REJECTED"
        )

        return {
            "approval_status": "rejected",
            "human_approved": False,
            "approval_comment": comment,
        }

    # --------------------------------------------------------
    # INVALID
    # --------------------------------------------------------

    print(
        "\nInvalid decision."
    )

    return {
        "approval_status": "pending",
        "human_approved": False,
        "approval_comment": "",
    }


# ============================================================
# EMAIL NODE
# ============================================================

def email_node(
    state: CollectionState,
):
    """
    Email is only attempted after human approval.

    Current email_service.py performs a safe
    simulation instead of sending a real email.
    """

    human_approved = state.get(
        "human_approved",
        False,
    )

    if not human_approved:

        print(
            "\nEmail was NOT sent."
        )

        return {
            "email_sent": False,
            "email_status": "not_approved",
        }

    customer_email = state.get(
        "customer_email",
        "",
    )

    customer_name = state.get(
        "customer_name",
        "",
    )

    invoice_id = state.get(
        "invoice_id",
        "",
    )

    generated_message = state.get(
        "generated_message",
        "",
    )

    if not customer_email:

        print(
            "\nEmail was NOT sent."
        )

        print(
            "Customer email is missing."
        )

        return {
            "email_sent": False,
            "email_status": "missing_email",
        }

    subject = (
        "Payment Follow-up - Invoice "
        f"{invoice_id}"
    )

    success = send_collection_email(
        customer_email=customer_email,
        customer_name=customer_name,
        subject=subject,
        message=generated_message,
    )

    if success:

        return {
            "email_sent": True,
            "email_status": "sent",
        }

    return {
        "email_sent": False,
        "email_status": "failed",
    }


# ============================================================
# AUDIT NODE
# ============================================================

def audit_node(
    state: CollectionState,
):
    """
    Save the workflow decision and email result
    to the audit log.
    """

    save_audit_event(
        customer_id=state.get(
            "customer_id",
            "",
        ),
        customer_name=state.get(
            "customer_name",
            "",
        ),
        invoice_id=state.get(
            "invoice_id",
            "",
        ),
        recommended_action=state.get(
            "recommended_action",
            "unknown",
        ),
        risk_score=state.get(
            "risk_score",
            0,
        ),
        risk_level=state.get(
            "risk_level",
            "UNKNOWN",
        ),
        approval_status=state.get(
            "approval_status",
            "pending",
        ),
        approval_comment=state.get(
            "approval_comment",
            "",
        ),
        email_status=state.get(
            "email_status",
            "not_attempted",
        ),
        email_sent=state.get(
            "email_sent",
            False,
        ),
    )

    return {}


# ============================================================
# APPROVAL ROUTER
# ============================================================

def approval_router(
    state: CollectionState,
):
    """
    Approved:
        -> send email
        -> audit

    Rejected:
        -> audit

    Pending:
        -> audit
    """

    if state.get(
        "human_approved",
        False,
    ):

        return "send_email"

    return "audit"


# ============================================================
# CREATE LANGGRAPH WORKFLOW
# ============================================================

def create_collection_graph():

    graph = StateGraph(
        CollectionState
    )

    # --------------------------------------------------------
    # Nodes
    # --------------------------------------------------------

    graph.add_node(
        "risk",
        risk_node,
    )

    graph.add_node(
        "policy",
        policy_node,
    )

    graph.add_node(
        "recommendation",
        recommendation_node,
    )

    graph.add_node(
        "message",
        message_node,
    )

    graph.add_node(
        "approval",
        approval_node,
    )

    graph.add_node(
        "send_email",
        email_node,
    )

    graph.add_node(
        "audit",
        audit_node,
    )

    # --------------------------------------------------------
    # Main workflow
    # --------------------------------------------------------

    graph.add_edge(
        START,
        "risk",
    )

    graph.add_edge(
        "risk",
        "policy",
    )

    graph.add_edge(
        "policy",
        "recommendation",
    )

    graph.add_edge(
        "recommendation",
        "message",
    )

    graph.add_edge(
        "message",
        "approval",
    )

    # --------------------------------------------------------
    # Human approval routing
    # --------------------------------------------------------

    graph.add_conditional_edges(
        "approval",
        approval_router,
        {
            "send_email": "send_email",
            "audit": "audit",
        },
    )

    # --------------------------------------------------------
    # Email -> Audit
    # --------------------------------------------------------

    graph.add_edge(
        "send_email",
        "audit",
    )

    # --------------------------------------------------------
    # Audit -> End
    # --------------------------------------------------------

    graph.add_edge(
        "audit",
        END,
    )

    return graph.compile()


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    collection_graph = (
        create_collection_graph()
    )

    test_state = {
        "customer_id": "CUST001",
        "customer_name": "ABC Industries",
        "customer_email": "abc@example.com",
        "invoice_id": "INV001",
        "outstanding_amount": 480000,
        "overdue_days": 21,
        "payment_status": "partially_paid",
        "no_response_count": 2,
        "dispute_type": None,
    }

    result = collection_graph.invoke(
        test_state
    )

    print("\n")
    print("=" * 60)
    print(
        "        CASHFLOWAI COLLECTION ANALYSIS"
    )
    print("=" * 60)

    print("\nCustomer:")

    print(
        result.get(
            "customer_name",
            "",
        )
    )

    print("\nCustomer Email:")

    print(
        result.get(
            "customer_email",
            "",
        )
    )

    print("\nInvoice:")

    print(
        result.get(
            "invoice_id",
            "",
        )
    )

    print("\nOutstanding:")

    print(
        f"₹{result.get('outstanding_amount', 0):,.2f}"
    )

    print("\nOverdue Days:")

    print(
        result.get(
            "overdue_days",
            0,
        )
    )

    print("\nRisk Score:")

    print(
        result.get(
            "risk_score",
            0,
        )
    )

    print("\nRisk Level:")

    print(
        result.get(
            "risk_level",
            "UNKNOWN",
        )
    )

    print("\nRisk Reasons:")

    for reason in result.get(
        "risk_reasons",
        [],
    ):

        print(
            f"- {reason}"
        )

    print("\nRecommended Action:")

    print(
        result.get(
            "recommended_action",
            "unknown",
        )
    )

    print("\nRecommendation Reasons:")

    for reason in result.get(
        "recommendation_reason",
        [],
    ):

        print(
            f"- {reason}"
        )

    print("\nRetrieved Policies:")

    for index, policy in enumerate(
        result.get(
            "policy_results",
            [],
        ),
        start=1,
    ):

        print(
            f"\n--- Policy {index} ---"
        )

        print(policy)

    print("\n")
    print("=" * 60)
    print(
        "          COLLECTION MESSAGE"
    )
    print("=" * 60)

    print(
        result.get(
            "generated_message",
            "",
        )
    )

    print("\n")
    print("=" * 60)
    print(
        "              APPROVAL RESULT"
    )
    print("=" * 60)

    print("\nApproval Status:")

    print(
        result.get(
            "approval_status",
            "pending",
        )
    )

    print("\nHuman Approved:")

    print(
        result.get(
            "human_approved",
            False,
        )
    )

    print("\nApproval Comment:")

    print(
        result.get(
            "approval_comment",
            "",
        )
    )

    print("\nEmail Status:")

    print(
        result.get(
            "email_status",
            "not attempted",
        )
    )

    print("\nEmail Sent:")

    print(
        result.get(
            "email_sent",
            False,
        )
    )

    print("\n")
    print("=" * 60)
    print(
        "             WORKFLOW COMPLETE"
    )
    print("=" * 60)