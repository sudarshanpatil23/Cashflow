from datetime import timedelta

from app.models.database import SessionLocal
from app.models.entities import Communication, Customer, Invoice


db = SessionLocal()

try:
    existing = db.query(Communication).count()

    if existing > 0:
        print(f"Communications already exist: {existing}")
        print("Nothing was added.")
    else:
        customers = db.query(Customer).all()
        created = 0

        for customer in customers:

            invoices = (
                db.query(Invoice)
                .filter(Invoice.customer_id == customer.id)
                .order_by(Invoice.due_date.asc())
                .all()
            )

            if not invoices:
                continue

            invoice = invoices[0]

            base_date = invoice.due_date

            # Reminder sent
            db.add(
                Communication(
                    company_id=customer.company_id,
                    customer_id=customer.id,
                    invoice_id=invoice.id,
                    channel="email",
                    direction="outbound",
                    subject="Payment Reminder",
                    message="Payment reminder sent to customer.",
                    status="sent",
                    sent_at=base_date + timedelta(days=1),
                )
            )
            created += 1

            # No response
            db.add(
                Communication(
                    company_id=customer.company_id,
                    customer_id=customer.id,
                    invoice_id=invoice.id,
                    channel="email",
                    direction="outbound",
                    subject="Payment Reminder",
                    message="Payment reminder sent. No response received.",
                    status="no_response",
                    sent_at=base_date + timedelta(days=4),
                )
            )
            created += 1

            # Customer response
            db.add(
                Communication(
                    company_id=customer.company_id,
                    customer_id=customer.id,
                    invoice_id=invoice.id,
                    channel="email",
                    direction="inbound",
                    subject="Payment Response",
                    message="Customer responded regarding payment.",
                    status="response",
                    sent_at=base_date + timedelta(days=7),
                )
            )
            created += 1

        db.commit()

        print(f"Synthetic communications created: {created}")

finally:
    db.close()
