from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd


def build_recovery_learning_loop(
    communications: pd.DataFrame,
    receivables: pd.DataFrame,
    customer_name: str,
) -> Dict[str, Any]:

    if communications is None or communications.empty:
        return _empty_result(
            customer_name,
            "No historical communication data is available yet.",
        )

    if receivables is None or receivables.empty:
        return _empty_result(
            customer_name,
            "No receivables data is available for customer mapping.",
        )

    comms = communications.copy()
    invoices = receivables.copy()

    comms.columns = [
        str(col).strip().lower().replace(" ", "_")
        for col in comms.columns
    ]

    invoices.columns = [
        str(col).strip().lower().replace(" ", "_")
        for col in invoices.columns
    ]

    customer_name_col = next(
        (
            col
            for col in [
                "customer_name",
                "customer",
                "client_name",
                "client",
            ]
            if col in invoices.columns
        ),
        None,
    )

    invoice_id_col = next(
        (
            col
            for col in [
                "invoice_id",
                "invoice",
                "invoice_number",
            ]
            if col in invoices.columns
        ),
        None,
    )

    customer_id_col = next(
        (
            col
            for col in [
                "customer_id",
                "customerid",
                "client_id",
            ]
            if col in invoices.columns
        ),
        None,
    )

    if not customer_name_col or not invoice_id_col:
        return _empty_result(
            customer_name,
            "Receivables data does not contain the required customer/invoice fields.",
        )

    customer_invoices = invoices[
        invoices[customer_name_col]
        .astype(str)
        .str.strip()
        .str.lower()
        == str(customer_name).strip().lower()
    ].copy()

    if customer_invoices.empty:
        return _empty_result(
            customer_name,
            "No invoices were found for this customer.",
        )

    invoice_ids = set(
        customer_invoices[invoice_id_col]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    if "invoice_id" not in comms.columns:
        return _empty_result(
            customer_name,
            "Communication data does not contain an invoice_id field.",
        )

    customer_comms = comms[
        comms["invoice_id"]
        .astype(str)
        .str.strip()
        .str.upper()
        .isin(invoice_ids)
    ].copy()

    if customer_comms.empty:
        return _empty_result(
            customer_name,
            "No historical communication actions were found for this customer's invoices.",
        )

    action_col = next(
        (
            col
            for col in [
                "action",
                "action_type",
                "communication_type",
                "type",
                "channel",
            ]
            if col in customer_comms.columns
        ),
        "channel",
    )

    status_col = next(
        (
            col
            for col in [
                "status",
                "communication_status",
                "outcome",
                "result",
            ]
            if col in customer_comms.columns
        ),
        None,
    )

    date_col = next(
        (
            col
            for col in [
                "communication_date",
                "date",
                "sent_at",
                "created_at",
            ]
            if col in customer_comms.columns
        ),
        None,
    )

    notes_col = "notes" if "notes" in customer_comms.columns else (
        "message" if "message" in customer_comms.columns else None
    )

    evidence: List[Dict[str, Any]] = []

    for _, row in customer_comms.iterrows():

        action = str(
            row.get(action_col, "Follow-up")
        ).strip()

        outcome = (
            str(row.get(status_col, "Unknown")).strip()
            if status_col
            else "Unknown"
        )

        notes = (
            str(row.get(notes_col, "")).strip()
            if notes_col
            else ""
        )

        outcome_lower = outcome.lower()
        notes_lower = notes.lower()

        # IMPORTANT:
        # Check no_response BEFORE checking response.
        is_no_response = outcome_lower == "no_response"

        is_response = (
            not is_no_response
            and outcome_lower in {
                "response",
                "responded",
                "promise",
                "committed",
            }
        )

        is_paid = any(
            keyword in outcome_lower or keyword in notes_lower
            for keyword in [
                "paid",
                "payment received",
                "partially paid",
                "resolved",
            ]
        )

        is_dispute = (
            outcome_lower == "dispute"
            or "dispute" in outcome_lower
        )

        evidence.append(
            {
                "invoice_id": str(row.get("invoice_id", "")),
                "action": action,
                "outcome": outcome,
                "notes": notes,
                "successful": is_paid,
                "response": is_response,
                "no_response": is_no_response,
                "dispute": is_dispute,
                "date": (
                    str(row.get(date_col))
                    if date_col and pd.notna(row.get(date_col))
                    else ""
                ),
            }
        )

    total_actions = len(evidence)

    successful_actions = sum(
        1 for item in evidence if item["successful"]
    )

    response_count = sum(
        1 for item in evidence if item["response"]
    )

    no_response_count = sum(
        1 for item in evidence if item["no_response"]
    )

    dispute_count = sum(
        1 for item in evidence if item["dispute"]
    )

    response_rate = (
        response_count / total_actions
        if total_actions
        else 0.0
    )

    action_stats: Dict[str, Dict[str, int]] = {}

    for item in evidence:

        action = item["action"]

        if action not in action_stats:
            action_stats[action] = {
                "total": 0,
                "responses": 0,
                "successful": 0,
                "no_response": 0,
                "disputes": 0,
            }

        stats = action_stats[action]

        stats["total"] += 1

        if item["response"]:
            stats["responses"] += 1

        if item["successful"]:
            stats["successful"] += 1

        if item["no_response"]:
            stats["no_response"] += 1

        if item["dispute"]:
            stats["disputes"] += 1

    best_action = None
    best_score = -1.0

    for action, stats in action_stats.items():

        total = stats["total"]

        if total == 0:
            continue

        response_rate_for_action = stats["responses"] / total
        payment_success_rate = stats["successful"] / total

        score = (
            response_rate_for_action * 0.7
            + payment_success_rate * 0.3
        )

        if score > best_score:
            best_score = score
            best_action = action

    if best_action:
        stats = action_stats[best_action]

        recommended_action = best_action

        reason = (
            f"{best_action} has the strongest historical response "
            f"signal for this customer's invoices: "
            f"{stats['responses']}/{stats['total']} "
            f"communications produced a response."
        )

        if stats["successful"] > 0:
            reason += (
                f" {stats['successful']} also had a payment-related "
                f"success signal."
            )

    else:
        recommended_action = "Standard payment follow-up"

        reason = (
            "There is not enough historical evidence to identify "
            "a preferred recovery action."
        )

    if dispute_count > 0:
        reason += (
            f" {dispute_count} dispute-related communication(s) "
            f"were detected."
        )

    customer_id = None

    if customer_id_col and not customer_invoices.empty:
        customer_id = str(
            customer_invoices.iloc[0][customer_id_col]
        )

    return {
        "customer_name": customer_name,
        "customer_id": customer_id,
        "invoice_ids": sorted(invoice_ids),
        "actions_analyzed": total_actions,
        "successful_actions": successful_actions,
        "success_rate": round(
            (successful_actions / total_actions) * 100,
            1,
        )
        if total_actions
        else 0.0,
        "response_count": response_count,
        "response_rate": round(
            response_rate * 100,
            1,
        ),
        "no_response_count": no_response_count,
        "dispute_count": dispute_count,
        "recommended_action": recommended_action,
        "reason": reason,
        "evidence": evidence,
        "action_stats": action_stats,
    }


def _empty_result(
    customer_name: str,
    reason: str,
) -> Dict[str, Any]:

    return {
        "customer_name": customer_name,
        "customer_id": None,
        "invoice_ids": [],
        "actions_analyzed": 0,
        "successful_actions": 0,
        "success_rate": 0.0,
        "response_count": 0,
        "response_rate": 0.0,
        "no_response_count": 0,
        "dispute_count": 0,
        "recommended_action": "Start with a standard payment follow-up",
        "reason": reason,
        "evidence": [],
        "action_stats": {},
    }
