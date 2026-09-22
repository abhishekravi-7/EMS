import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_password_reset_email(to_email: str, user_name: str, reset_link: str) -> None:
    """Send a password reset email using the configured SMTP server.
    
    If SMTP is not configured, logs the email content to stdout for development.
    """
    subject = "Reset Your Password - Java APEX"
    body = f"""Hi {user_name},

We received a request to reset the password for your account.

Click the button below to create a new password:

Reset Password: {reset_link}

If you did not request a password reset, you can safely ignore this email. Your password will remain unchanged.

For security reasons, this password reset link will expire after 30 minutes.

Regards,
Java APEX Team
"""

    if not settings.is_smtp_configured:
        logger.info(
            f"SMTP not configured. Skipping email send. Email content:\n"
            f"To: {to_email}\nSubject: {subject}\n\n{body}"
        )
        return

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_address
    msg["To"] = to_email

    try:
        if settings.smtp_use_tls:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port)

        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)
            
        server.send_message(msg)
        server.quit()
        logger.info(f"Password reset email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send password reset email to {to_email}: {e}")
        raise e
