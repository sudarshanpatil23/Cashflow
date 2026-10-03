from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI


load_dotenv()


def generate_fallback_message(
    customer_name: str,
    invoice_id: str,
    outstanding_amount: float,
    overdue_days: int,
    recommended_action: str,
) -> str:
    """
    Deterministic fallback message.

    Used when Gemini is unavailable, including
    quota/rate-limit errors.
    """

    if recommended_action == "friendly_reminder":
        opening = (
            "This is a friendly reminder regarding "
            f"Invoice {invoice_id}."
        )

    elif recommended_action == "formal_reminder":
        opening = (
            "This is a formal follow-up regarding "
            f"Invoice {invoice_id}, which is currently "
            f"{overdue_days} days overdue."
        )

    elif recommended_action == "escalation_review":
        opening = (
            f"We are following up regarding Invoice "
            f"{invoice_id}, which is currently "
            f"{overdue_days} days overdue."
        )

    elif recommended_action == "management_review":
        opening = (
            f"We are writing regarding Invoice "
            f"{invoice_id}, which is currently "
            f"{overdue_days} days overdue and requires "
            "payment status review."
        )

    elif recommended_action == "dispute_review":
        opening = (
            f"We are following up regarding Invoice "
            f"{invoice_id} and the outstanding payment."
        )

    else:
        opening = (
            f"We are following up regarding Invoice "
            f"{invoice_id}."
        )

    return f"""Dear {customer_name} Team,

I hope you are doing well.

{opening}

The current outstanding balance is ₹{outstanding_amount:,.2f}.

We kindly request you to review the payment status and provide an update on the expected payment date. If the payment has already been processed, please share the remittance details so that we can update our records.

If there is any issue or discrepancy with the invoice, please let us know so that our finance team can review it.

Thank you for your attention to this matter.

Best regards,

Finance Team
"""


def generate_collection_message(
    customer_name: str,
    invoice_id: str,
    outstanding_amount: float,
    overdue_days: int,
    recommended_action: str,
    policy_results: list[str],
) -> str:
    """
    Generate a collection message using Gemini.

    If Gemini is unavailable because of quota,
    rate limits, API errors, or another exception,
    safely falls back to a deterministic template.
    """

    try:
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured."
            )

        llm = ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            google_api_key=api_key,
            temperature=0.2,
        )

        policy_text = "\n".join(
            policy_results
        )

        prompt = f"""
You are an accounts receivable assistant.

Generate a professional payment follow-up email.

Customer:
{customer_name}

Invoice:
{invoice_id}

Outstanding Amount:
₹{outstanding_amount:,.2f}

Overdue Days:
{overdue_days}

Recommended Collection Action:
{recommended_action}

Relevant Company Policy:
{policy_text}

Requirements:
- Be professional and concise.
- Do not threaten the customer.
- Do not make legal claims.
- Do not invent payment details.
- Clearly mention the invoice number.
- Clearly mention the outstanding amount.
- Mention the overdue status when applicable.
- Ask for a payment update.
- Ask for remittance details if payment has already been made.
- If there may be an invoice issue, invite the customer to contact the finance team.
- Do not include a subject line.
- Return only the email body.
"""

        response = llm.invoke(prompt)

        message = response.content

        if isinstance(message, list):
            message = "\n".join(
                str(item)
                for item in message
            )

        message = str(message).strip()

        if not message:
            raise ValueError(
                "Gemini returned an empty message."
            )

        print(
            "\n✓ Gemini message generated successfully."
        )

        return message

    except Exception as error:

        print(
            "\n⚠ Gemini message generation failed."
        )

        print(
            f"Reason: {type(error).__name__}"
        )

        print(
            "Using deterministic fallback message."
        )

        return generate_fallback_message(
            customer_name=customer_name,
            invoice_id=invoice_id,
            outstanding_amount=outstanding_amount,
            overdue_days=overdue_days,
            recommended_action=recommended_action,
        )