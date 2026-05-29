import smtplib
from email.message import EmailMessage

from app.core.config import get_settings


def send_email(to: str, subject: str, html: str) -> bool:
    """Send an HTML email via SMTP.

    Returns True if sent. If SMTP is not configured, logs the email to the
    server console (useful for local development) and returns False instead
    of raising — so registration never fails just because email is down.
    """
    settings = get_settings()

    if not settings.email_configured:
        print("[email] SMTP not configured — would have sent:")
        print(f"[email] To: {to}\n[email] Subject: {subject}\n{html}")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.from_address
    msg["To"] = to
    msg.set_content("This email requires an HTML-capable client.")
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 — never break the request flow
        print(f"[email] Failed to send email: {exc}")
        return False


def build_owner_approval_email(
    *,
    full_name: str,
    email: str,
    showroom_name: str | None,
    showroom_address: str | None,
    phone: str | None,
    approve_url: str,
    reject_url: str,
) -> str:
    """HTML email sent to the developer to approve/reject a showroom owner."""
    rows = "".join(
        f"""
        <tr>
          <td style="padding:8px 0;color:#9CA3AF;font-size:14px;">{label}</td>
          <td style="padding:8px 0;color:#FFFFFF;font-size:14px;font-weight:600;text-align:right;">{value or '—'}</td>
        </tr>"""
        for label, value in [
            ("Full name", full_name),
            ("Email", email),
            ("Showroom", showroom_name),
            ("Address", showroom_address),
            ("Phone", phone),
        ]
    )

    return f"""\
<!DOCTYPE html>
<html>
  <body style="margin:0;padding:0;background:#0A0A0B;font-family:Arial,Helvetica,sans-serif;">
    <div style="max-width:520px;margin:0 auto;padding:32px 20px;">
      <div style="background:#141416;border:1px solid #2A2A2E;border-radius:16px;padding:28px;">
        <h1 style="color:#FFFFFF;font-size:22px;margin:0 0 6px;">New showroom owner request</h1>
        <p style="color:#9CA3AF;font-size:14px;margin:0 0 20px;">
          A new <strong style="color:#fff;">bike showroom owner</strong> registered on RevvUp and is awaiting your approval.
        </p>
        <table style="width:100%;border-collapse:collapse;border-top:1px solid #2A2A2E;border-bottom:1px solid #2A2A2E;margin-bottom:24px;">
          {rows}
        </table>
        <div style="text-align:center;">
          <a href="{approve_url}" style="display:inline-block;background:#22C55E;color:#fff;text-decoration:none;font-weight:700;font-size:15px;padding:14px 28px;border-radius:12px;margin:0 6px;">✓ Approve</a>
          <a href="{reject_url}" style="display:inline-block;background:#EF4444;color:#fff;text-decoration:none;font-weight:700;font-size:15px;padding:14px 28px;border-radius:12px;margin:0 6px;">✕ Reject</a>
        </div>
        <p style="color:#6B7280;font-size:12px;margin:24px 0 0;text-align:center;">
          Approving activates their account with admin CRUD capabilities. RevvUp © 2026
        </p>
      </div>
    </div>
  </body>
</html>"""


def result_page(*, title: str, message: str, ok: bool) -> str:
    """Simple HTML page shown after the developer clicks approve/reject."""
    accent = "#22C55E" if ok else "#EF4444"
    icon = "✓" if ok else "✕"
    return f"""\
<!DOCTYPE html>
<html>
  <head><meta name="viewport" content="width=device-width, initial-scale=1"/><title>{title}</title></head>
  <body style="margin:0;background:#0A0A0B;font-family:Arial,Helvetica,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;">
    <div style="text-align:center;padding:40px;">
      <div style="width:72px;height:72px;border-radius:50%;background:{accent};color:#fff;font-size:36px;line-height:72px;margin:0 auto 20px;">{icon}</div>
      <h1 style="color:#fff;font-size:24px;margin:0 0 8px;">{title}</h1>
      <p style="color:#9CA3AF;font-size:15px;margin:0;">{message}</p>
    </div>
  </body>
</html>"""
