"""Safe SMTP Connectivity and Delivery Diagnostic Test for Java APEX.

Usage:
    python scripts/test_smtp.py [recipient_email]

Examples:
    python scripts/test_smtp.py
    python scripts/test_smtp.py testuser@gmail.com

Security:
    Never logs or prints plain passwords, app passwords, or sensitive keys.
"""

from __future__ import annotations

import argparse
import socket
import smtplib
import sys
from pathlib import Path

# Add backend root to Python path
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.infrastructure.email.email_service import (
    _build_verification_email_message,
    _send_smtp_message_sync,
)


def run_smtp_diagnostics(target_recipient: str | None = None) -> bool:
    print("=" * 60)
    print(" Java APEX SMTP Diagnostic Tool")
    print("=" * 60)

    # 1. Check Configuration
    print("\n[1/5] Checking Configuration...")
    print(f"  SMTP Host:             {settings.smtp_host or '(not set)'}")
    print(f"  SMTP Port:             {settings.smtp_port}")
    print(f"  SMTP Username:         {settings.smtp_username or '(not set)'}")
    print(f"  SMTP Password Set:     {'Yes (' + str(len(settings.smtp_password_clean)) + ' chars)' if settings.smtp_password else 'No'}")
    print(f"  SMTP Use TLS:          {settings.smtp_use_tls}")
    print(f"  SMTP From Address:     {settings.smtp_from_address or '(not set)'}")
    print(f"  Is Fully Configured:   {settings.is_smtp_configured}")

    if not settings.is_smtp_configured:
        print("\n[FAIL] SMTP is missing required configuration settings.")
        return False

    # 2. DNS Resolution
    print("\n[2/5] Testing DNS Resolution...")
    try:
        ip_addresses = socket.gethostbyname_ex(settings.smtp_host)[2]
        print(f"  [PASS] Resolved {settings.smtp_host} -> {', '.join(ip_addresses)}")
    except Exception as exc:
        print(f"  [FAIL] DNS Resolution Failed: {exc}")
        return False

    # 3. TCP Connectivity
    print("\n[3/5] Testing TCP Connection...")
    try:
        sock = socket.create_connection((settings.smtp_host, settings.smtp_port), timeout=10)
        sock.close()
        print(f"  [PASS] Successfully connected to {settings.smtp_host}:{settings.smtp_port}")
    except Exception as exc:
        print(f"  [FAIL] TCP Connection Failed: {exc}")
        return False

    # 4. SMTP Handshake & Authentication
    print("\n[4/5] Testing SMTP Handshake & Authentication...")
    server = None
    try:
        if settings.smtp_port == 465 or (not settings.smtp_use_tls and settings.smtp_port != 587):
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
            server.ehlo()
            print("  [PASS] SSL Connection established.")
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
            server.ehlo()
            if settings.smtp_use_tls:
                server.starttls()
                server.ehlo()
                print("  [PASS] STARTTLS handshake succeeded.")

        if settings.smtp_username and settings.smtp_password_clean:
            server.login(settings.smtp_username, settings.smtp_password_clean)
            print("  [PASS] SMTP Authentication succeeded!")

        server.quit()
        server = None
    except smtplib.SMTPAuthenticationError as exc:
        print(f"  [FAIL] SMTP Authentication Failed: code={getattr(exc, 'smtp_code', 'unknown')}, message={getattr(exc, 'smtp_error', exc)}")
        print("  [INFO] Tip: For Gmail, ensure 2-Step Verification is ON and use a 16-character Google App Password.")
        return False
    except Exception as exc:
        print(f"  [FAIL] SMTP Handshake/Auth Failed: {exc}")
        return False
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass

    # 5. Message Delivery Test
    recipient = target_recipient or settings.smtp_username or settings.smtp_from_address
    print(f"\n[5/5] Sending Test Verification Email to {recipient}...")
    try:
        test_msg = _build_verification_email_message(
            to_email=recipient,
            user_name="APEX Admin",
            verification_code="482731",
        )
        _send_smtp_message_sync(test_msg, recipient)
        print(f"  [PASS] Test email successfully submitted to {recipient}!")
    except Exception as exc:
        print(f"  [FAIL] Test email sending failed: {exc}")
        return False

    print("\n" + "=" * 60)
    print(" [SUCCESS] ALL SMTP CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test SMTP connectivity and email delivery.")
    parser.add_argument("recipient", nargs="?", help="Optional recipient email address for test email")
    args = parser.parse_args()

    success = run_smtp_diagnostics(args.recipient)
    sys.exit(0 if success else 1)
