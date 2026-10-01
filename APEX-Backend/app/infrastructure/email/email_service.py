"""Email delivery service for Java APEX.

Handles transactional emails (verification emails, password resets) via standard SMTP.
Follows safe authentication practices: never logs passwords, tokens, or secrets.
"""

from __future__ import annotations

import asyncio
import html
import logging
import smtplib
import socket
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when an email cannot be delivered via SMTP."""

    def __init__(self, message: str, reason: str = "DELIVERY_FAILED", status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.reason = reason
        self.status_code = status_code


class EmailNotConfiguredError(EmailDeliveryError):
    """Raised when email delivery is requested but SMTP is not configured."""

    def __init__(self, message: str = "SMTP email service is not configured."):
        super().__init__(message, reason="NOT_CONFIGURED", status_code=503)


def _build_verification_email_message(to_email: str, user_name: str, verification_code: str) -> EmailMessage:
    """Construct a multipart MIME email with both plain-text and HTML versions displaying a 6-digit verification code."""
    subject = "Java APEX - Verify Your Email"
    escaped_name = html.escape(user_name or "User")
    escaped_code = html.escape(verification_code)

    plain_text = f"""Hello {user_name},

Your Java APEX verification code is:

{verification_code}

Enter this code on the Java APEX verification page to verify your email address.

This code expires in 10 minutes.

If you did not create this account, you can ignore this email.

Regards,
Java APEX Team
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Java APEX - Verify Your Email</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 32px 16px; color: #1e293b;">
  <div style="max-width: 560px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">

    <!-- Header -->
    <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 32px 28px; text-align: center;">
      <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px;">
        Java <span style="color: #3b82f6;">APEX</span>
      </h1>
      <p style="color: #94a3b8; margin: 6px 0 0; font-size: 13px; font-weight: 500;">
        Modern Enterprise Java Migration Platform
      </p>
    </div>

    <!-- Body -->
    <div style="padding: 36px 32px; text-align: center;">
      <h2 style="margin: 0 0 12px; color: #0f172a; font-size: 20px; font-weight: 600;">
        Verify your email address
      </h2>
      <p style="margin: 0 0 20px; font-size: 15px; line-height: 1.6; color: #475569; text-align: left;">
        Hello <strong>{escaped_name}</strong>, thank you for signing up for Java APEX. Enter the verification code below to verify your email and activate your account:
      </p>

      <!-- 6-digit Code Badge -->
      <div style="background-color: #f0fdf4; border: 2px dashed #86efac; border-radius: 12px; padding: 22px 20px; margin: 24px 0; display: inline-block; width: 85%; box-sizing: border-box;">
        <span style="font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 800; letter-spacing: 10px; color: #166534; display: block; margin-left: 10px;">
          {escaped_code}
        </span>
      </div>

      <p style="margin: 12px 0 0; font-size: 14px; line-height: 1.5; color: #64748b;">
        This code expires in <strong>10 minutes</strong>.
      </p>

      <div style="border-top: 1px solid #f1f5f9; padding-top: 20px; margin-top: 28px; text-align: left;">
        <p style="margin: 0; font-size: 13px; line-height: 1.5; color: #94a3b8;">
          If you did not create a Java APEX account, you can safely ignore this email.
        </p>
      </div>
    </div>

    <!-- Footer -->
    <div style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 32px; text-align: center;">
      <p style="margin: 0; font-size: 12px; color: #94a3b8;">
        &copy; Java APEX Platform. All rights reserved.
      </p>
    </div>
  </div>
</body>
</html>
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_address
    msg["To"] = to_email
    msg.set_content(plain_text)
    msg.add_alternative(html_content, subtype="html")
    return msg


def _build_password_reset_email_message(to_email: str, user_name: str, reset_link: str) -> EmailMessage:
    """Construct a multipart MIME email for password reset."""
    subject = "Reset Your Password - Java APEX"
    escaped_name = html.escape(user_name or "User")
    escaped_link = html.escape(reset_link)

    plain_text = f"""Hi {user_name},

We received a request to reset the password for your Java APEX account.

Click the link below to set a new password:

{reset_link}

If you did not request a password reset, you can safely ignore this email. Your password will remain unchanged.

This link will expire in 30 minutes.

Regards,
Java APEX Team
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reset Your Password - Java APEX</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 32px 16px; color: #1e293b;">
  <div style="max-width: 560px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">

    <!-- Header -->
    <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 32px 28px; text-align: center;">
      <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700;">
        Java <span style="color: #3b82f6;">APEX</span>
      </h1>
      <p style="color: #94a3b8; margin: 6px 0 0; font-size: 13px;">
        Account Security
      </p>
    </div>

    <!-- Body -->
    <div style="padding: 36px 32px;">
      <h2 style="margin: 0 0 16px; color: #0f172a; font-size: 20px; font-weight: 600;">
        Reset your password
      </h2>
      <p style="margin: 0 0 20px; font-size: 15px; line-height: 1.6; color: #475569;">
        Hi <strong>{escaped_name}</strong>, we received a request to reset the password for your Java APEX account.
      </p>

      <!-- CTA Button -->
      <div style="text-align: center; margin: 32px 0;">
        <a href="{escaped_link}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; font-weight: 600; font-size: 15px; padding: 14px 32px; border-radius: 8px; text-decoration: none; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);">
          Reset Password
        </a>
      </div>

      <p style="margin: 24px 0 8px; font-size: 13px; line-height: 1.5; color: #64748b;">
        Or copy and paste this link into your browser:
      </p>
      <p style="margin: 0 0 24px; font-size: 12px; line-height: 1.4; color: #3b82f6; word-break: break-all; background-color: #f1f5f9; padding: 12px; border-radius: 6px;">
        {escaped_link}
      </p>

      <div style="border-top: 1px solid #f1f5f9; padding-top: 20px; margin-top: 24px;">
        <p style="margin: 0; font-size: 13px; line-height: 1.5; color: #94a3b8;">
          This link will expire in <strong>30 minutes</strong>. If you did not make this request, you can safely ignore this email.
        </p>
      </div>
    </div>

    <!-- Footer -->
    <div style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 32px; text-align: center;">
      <p style="margin: 0; font-size: 12px; color: #94a3b8;">
        &copy; Java APEX Platform. All rights reserved.
      </p>
    </div>
  </div>
</body>
</html>
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_address
    msg["To"] = to_email
    msg.set_content(plain_text)
    msg.add_alternative(html_content, subtype="html")
    return msg


def _send_smtp_message_sync(msg: EmailMessage, to_email: str) -> None:
    """Synchronous SMTP submission following standard RFC flow. Never logs credentials or raw tokens."""
    if not settings.is_smtp_configured:
        logger.error("SMTP delivery attempted but SMTP is not fully configured.")
        raise EmailNotConfiguredError("SMTP email service is not configured.")

    host = settings.smtp_host
    port = settings.smtp_port
    username = settings.smtp_username
    password = settings.smtp_password_clean
    use_tls = settings.smtp_use_tls

    logger.info("Initiating SMTP connection to %s:%d for recipient %s...", host, port, to_email)

    server = None
    try:
        # Port 465 uses SSL from start; Port 587 uses standard STARTTLS
        if port == 465 or (not use_tls and port != 587):
            server = smtplib.SMTP_SSL(host, port, timeout=15)
            server.ehlo()
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()

        if username and password:
            server.login(username, password)

        server.send_message(msg)
        logger.info("Email message successfully accepted by SMTP server for %s", to_email)
    except smtplib.SMTPAuthenticationError as exc:
        logger.error("SMTP authentication failed for host %s: code=%s", host, getattr(exc, "smtp_code", "unknown"))
        raise EmailDeliveryError("SMTP authentication failed. Please verify SMTP credentials.", reason="AUTH_FAILED") from exc
    except (smtplib.SMTPConnectError, ConnectionRefusedError, socket.gaierror) as exc:
        logger.error("Failed to connect to SMTP server %s:%d: %s", host, port, type(exc).__name__)
        raise EmailDeliveryError(f"Could not connect to SMTP server {host}:{port}.", reason="CONNECT_FAILED") from exc
    except smtplib.SMTPRecipientsRefused as exc:
        logger.error("SMTP recipient address was refused for %s", to_email)
        raise EmailDeliveryError(f"Recipient address {to_email} was rejected by the SMTP server.", reason="RECIPIENT_REJECTED") from exc
    except smtplib.SMTPSenderRefused as exc:
        logger.error("SMTP sender address was refused by server: %s", settings.smtp_from_address)
        raise EmailDeliveryError("Sender address was rejected by the SMTP server.", reason="SENDER_REJECTED") from exc
    except (socket.timeout, TimeoutError) as exc:
        logger.error("SMTP connection timed out while sending to %s", to_email)
        raise EmailDeliveryError("SMTP server connection timed out.", reason="TIMEOUT") from exc
    except smtplib.SMTPException as exc:
        logger.error("SMTP protocol error while sending to %s: %s", to_email, str(exc))
        raise EmailDeliveryError(f"SMTP protocol error: {exc}", reason="SMTP_ERROR") from exc
    except Exception as exc:
        logger.error("Unexpected error during email delivery to %s: %s", to_email, str(exc))
        raise EmailDeliveryError(f"Unexpected email delivery failure: {exc}", reason="UNKNOWN") from exc
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


async def send_verification_email(
    to_email: str,
    user_name: str,
    verification_code: str = "",
    verify_code: str = "",
    code: str = "",
    verify_link: str = "",
    verification_link: str = "",
) -> None:
    """Send an email verification code using the configured SMTP server.

    Raises EmailDeliveryError or EmailNotConfiguredError if delivery fails.
    """
    code_to_send = verification_code or verify_code or code or verify_link or verification_link
    if not code_to_send:
        raise ValueError("Verification code is required.")

    msg = _build_verification_email_message(to_email=to_email, user_name=user_name, verification_code=code_to_send)
    await asyncio.to_thread(_send_smtp_message_sync, msg, to_email)


async def send_password_reset_email(
    to_email: str,
    user_name: str,
    reset_link: str,
) -> None:
    """Send a password reset email using the configured SMTP server.

    Raises EmailDeliveryError or EmailNotConfiguredError if delivery fails.
    """
    if not reset_link:
        raise ValueError("Reset link is required.")

    msg = _build_password_reset_email_message(to_email=to_email, user_name=user_name, reset_link=reset_link)
    await asyncio.to_thread(_send_smtp_message_sync, msg, to_email)
