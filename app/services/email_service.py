from __future__ import annotations

import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


SMTP_HOST = os.getenv(
    "SMTP_HOST",
    "smtp.gmail.com",
).strip()

SMTP_PORT = int(
    os.getenv(
        "SMTP_PORT",
        "587",
    )
)

SMTP_USERNAME = os.getenv(
    "SMTP_USERNAME",
    "",
).strip()

SMTP_PASSWORD = os.getenv(
    "SMTP_PASSWORD",
    "",
).strip()

EMAIL_FROM = os.getenv(
    "EMAIL_FROM",
    SMTP_USERNAME,
).strip()

EMAIL_FROM_NAME = os.getenv(
    "EMAIL_FROM_NAME",
    "CashFlowAI",
).strip()


# ============================================================
# VALIDATION
# ============================================================

def is_valid_email(
    email: str,
) -> bool:

    if not email:
        return False

    pattern = (
        r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
        r"@[A-Za-z0-9-]+"
        r"(?:\.[A-Za-z0-9-]+)+$"
    )

    return bool(
        re.match(
            pattern,
            email.strip(),
        )
    )


# ============================================================
# MESSAGE NORMALIZATION
# ============================================================

def normalize_message(
    message,
) -> str:

    if isinstance(
        message,
        dict,
    ):
        return str(
            message.get(
                "text",
                "",
            )
        ).strip()

    return str(
        message or ""
    ).strip()


# ============================================================
# REAL EMAIL SENDER
# ============================================================

def send_collection_email(
    customer_email: str,
    customer_name: str,
    subject: str,
    message: str,
) -> bool:
    """
    Send a real collection email through the configured SMTP server.

    The caller is responsible for enforcing human approval before
    calling this function.
    """

    customer_email = str(
        customer_email or ""
    ).strip()

    customer_name = str(
        customer_name or ""
    ).strip()

    subject = str(
        subject or ""
    ).strip()

    message = normalize_message(
        message
    )

    # --------------------------------------------------------
    # Required configuration
    # --------------------------------------------------------

    if not SMTP_USERNAME:
        print(
            "\nEmail send failed:"
            "\nSMTP_USERNAME is not configured."
        )
        return False

    if not SMTP_PASSWORD:
        print(
            "\nEmail send failed:"
            "\nSMTP_PASSWORD is not configured."
        )
        return False

    if not EMAIL_FROM:
        print(
            "\nEmail send failed:"
            "\nEMAIL_FROM is not configured."
        )
        return False

    # --------------------------------------------------------
    # Validate recipient
    # --------------------------------------------------------

    if not is_valid_email(
        customer_email
    ):
        print(
            "\nEmail send failed:"
            f"\nInvalid recipient email: {customer_email}"
        )
        return False

    # --------------------------------------------------------
    # Validate content
    # --------------------------------------------------------

    if not subject:
        print(
            "\nEmail send failed:"
            "\nEmail subject is empty."
        )
        return False

    if not message:
        print(
            "\nEmail send failed:"
            "\nEmail message is empty."
        )
        return False

    # --------------------------------------------------------
    # Create email
    # --------------------------------------------------------

    email = MIMEMultipart(
        "alternative"
    )

    email["From"] = (
        f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>"
        if EMAIL_FROM_NAME
        else EMAIL_FROM
    )

    email["To"] = customer_email
    email["Subject"] = subject

    greeting = (
        f"Dear {customer_name},"
        if customer_name
        else "Dear Customer,"
    )

    plain_text = (
        f"{greeting}\n\n"
        f"{message}\n\n"
        "Regards,\n"
        f"{EMAIL_FROM_NAME}"
    )

    # Basic HTML version
    html_message = (
        message
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )

    html_body = f"""
    <html>
        <body>
            <p>{greeting}</p>

            <p>{html_message}</p>

            <p>
                Regards,<br>
                {EMAIL_FROM_NAME}
            </p>
        </body>
    </html>
    """

    email.attach(
        MIMEText(
            plain_text,
            "plain",
            "utf-8",
        )
    )

    email.attach(
        MIMEText(
            html_body,
            "html",
            "utf-8",
        )
    )

    # --------------------------------------------------------
    # SMTP SEND
    # --------------------------------------------------------

    try:

        print(
            "\nConnecting to email server..."
        )

        with smtplib.SMTP(
            SMTP_HOST,
            SMTP_PORT,
            timeout=30,
        ) as smtp:

            smtp.ehlo()

            smtp.starttls()

            smtp.ehlo()

            smtp.login(
                SMTP_USERNAME,
                SMTP_PASSWORD,
            )

            smtp.sendmail(
                EMAIL_FROM,
                [customer_email],
                email.as_string(),
            )

        print(
            "\n✓ REAL EMAIL SENT SUCCESSFULLY"
        )

        print(
            f"From: {EMAIL_FROM}"
        )

        print(
            f"To: {customer_email}"
        )

        print(
            f"Subject: {subject}"
        )

        return True

    except smtplib.SMTPAuthenticationError as error:

        print(
            "\nEmail authentication failed."
        )

        print(
            "Check your SMTP username and Gmail App Password."
        )

        print(
            f"SMTP error: {error}"
        )

        return False

    except smtplib.SMTPException as error:

        print(
            "\nSMTP email sending failed."
        )

        print(
            f"SMTP error: {error}"
        )

        return False

    except OSError as error:

        print(
            "\nCould not connect to the email server."
        )

        print(
            f"Connection error: {error}"
        )

        return False

    except Exception as error:

        print(
            "\nUnexpected email error."
        )

        print(
            f"Error: {error}"
        )

        return False