import html
import smtplib
from email.message import EmailMessage
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings

_LOGO_PATH = Path(__file__).resolve().parent.parent / "static" / "AppLogo.png"


def _esc(value: str | None) -> str:
    return html.escape((value or "").strip() or "—")


@lru_cache
def _logo_data_uri() -> str:
    try:
        from app.core.email_logo_b64 import LOGO_PNG_BASE64

        if LOGO_PNG_BASE64:
            return f"data:image/png;base64,{LOGO_PNG_BASE64}"
    except ImportError:
        pass

    if _LOGO_PATH.is_file():
        import base64

        encoded = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    return ""


def _email_logo_block() -> str:
    uri = _logo_data_uri()
    if not uri:
        return (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            '<tr><td align="center" style="padding:0 0 24px;">'
            '<span style="font-size:26px;font-weight:800;color:#E63946;letter-spacing:1px;">RevvUp</span>'
            "</td></tr></table>"
        )
    return f"""\
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#FFFFFF">
  <tr>
    <td align="center" bgcolor="#FFFFFF" style="padding:28px 16px 20px;background-color:#FFFFFF;">
      <img src="{uri}" alt="RevvUp" width="220" height="62"
        style="display:block;max-width:220px;width:220px;height:auto;border:0;outline:none;" />
    </td>
  </tr>
</table>"""


def _detail_row(label: str, value: str) -> str:
    return f"""\
<tr>
  <td colspan="2" style="padding:0 0 10px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
      style="background-color:#F9FAFB;border:1px solid #E5E7EB;border-radius:10px;">
      <tr>
        <td style="padding:14px 16px 4px;font-size:11px;font-weight:700;letter-spacing:0.6px;
          text-transform:uppercase;color:#6B7280;font-family:Arial,Helvetica,sans-serif;">
          {_esc(label)}
        </td>
      </tr>
      <tr>
        <td style="padding:0 16px 14px;font-size:16px;font-weight:600;color:#111827;
          font-family:Arial,Helvetica,sans-serif;line-height:22px;">
          {value}
        </td>
      </tr>
    </table>
  </td>
</tr>"""


def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an HTML email via SMTP."""
    settings = get_settings()

    if not settings.email_configured:
        print("[email] SMTP not configured — would have sent:")
        print(f"[email] To: {to}\n[email] Subject: {subject}\n{html_body[:500]}...")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.from_address
    msg["To"] = to
    msg.set_content("Open this email in an HTML-capable client to approve the showroom owner.")
    msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001
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
    logo = _email_logo_block()
    email_cell = (
        f'<a href="mailto:{_esc(email)}" style="color:#E63946;text-decoration:none;">'
        f"{_esc(email)}</a>"
    )
    detail_rows = "".join(
        _detail_row(label, value)
        for label, value in [
            ("Full name", _esc(full_name)),
            ("Email", email_cell),
            ("Showroom", _esc(showroom_name)),
            ("Address", _esc(showroom_address)),
            ("Phone", _esc(phone)),
        ]
    )

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light only" />
  <meta name="supported-color-schemes" content="light" />
  <title>Approve showroom owner — RevvUp</title>
</head>
<body style="margin:0;padding:0;background-color:#FFFFFF !important;" bgcolor="#FFFFFF">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#FFFFFF"
    style="background-color:#FFFFFF !important;min-width:100%;">
    <tr>
      <td align="center" bgcolor="#FFFFFF" style="padding:32px 16px;background-color:#FFFFFF;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#FFFFFF"
          style="max-width:560px;background-color:#FFFFFF;border:1px solid #E5E7EB;border-radius:20px;
          box-shadow:0 4px 24px rgba(0,0,0,0.06);overflow:hidden;">
          <tr>
            <td bgcolor="#FFFFFF" style="background-color:#FFFFFF;">
              {logo}
            </td>
          </tr>
          <tr>
            <td bgcolor="#E63946" style="height:4px;line-height:4px;font-size:0;background-color:#E63946;">&nbsp;</td>
          </tr>
          <tr>
            <td bgcolor="#FFFFFF" style="padding:28px 28px 8px;background-color:#FFFFFF;">
              <h1 style="margin:0 0 10px;font-size:24px;font-weight:800;color:#111827;
                font-family:Arial,Helvetica,sans-serif;text-align:center;line-height:1.3;">
                Approve showroom owner
              </h1>
              <p style="margin:0;font-size:15px;color:#6B7280;text-align:center;line-height:24px;
                font-family:Arial,Helvetica,sans-serif;">
                A new <strong style="color:#111827;">bike showroom owner</strong> registered on RevvUp.
                Review the details below, then approve or reject.
              </p>
            </td>
          </tr>
          <tr>
            <td bgcolor="#FFFFFF" style="padding:20px 24px 8px;background-color:#FFFFFF;">
              <p style="margin:0 0 12px;font-size:12px;font-weight:700;letter-spacing:0.5px;
                text-transform:uppercase;color:#9CA3AF;font-family:Arial,Helvetica,sans-serif;">
                Application details
              </p>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                {detail_rows}
              </table>
            </td>
          </tr>
          <tr>
            <td bgcolor="#FFFFFF" style="padding:16px 24px 32px;background-color:#FFFFFF;text-align:center;">
              <table role="presentation" cellpadding="0" cellspacing="0" align="center">
                <tr>
                  <td style="padding:6px;">
                    <a href="{_esc(approve_url)}" target="_blank"
                      style="display:inline-block;background-color:#22C55E;color:#FFFFFF !important;
                      text-decoration:none;font-weight:700;font-size:15px;padding:15px 36px;
                      border-radius:12px;font-family:Arial,Helvetica,sans-serif;">
                      ✓&nbsp; Approve
                    </a>
                  </td>
                  <td style="padding:6px;">
                    <a href="{_esc(reject_url)}" target="_blank"
                      style="display:inline-block;background-color:#EF4444;color:#FFFFFF !important;
                      text-decoration:none;font-weight:700;font-size:15px;padding:15px 36px;
                      border-radius:12px;font-family:Arial,Helvetica,sans-serif;">
                      ✕&nbsp; Reject
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin:24px 0 0;font-size:12px;color:#9CA3AF;line-height:18px;
                font-family:Arial,Helvetica,sans-serif;text-align:center;">
                Approving activates their account so they can sign in and manage listings.<br/>
                <span style="color:#E63946;font-weight:600;">RevvUp</span> · Premium Motorbike Marketplace
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def result_page(*, title: str, message: str, ok: bool) -> str:
    """HTML page shown after the developer clicks approve/reject."""
    accent = "#22C55E" if ok else "#EF4444"
    icon = "✓" if ok else "✕"
    logo = _email_logo_block()
    return f"""\
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <meta name="color-scheme" content="light only"/>
    <title>{_esc(title)}</title>
  </head>
  <body style="margin:0;background-color:#FFFFFF;" bgcolor="#FFFFFF">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#FFFFFF">
      <tr>
        <td align="center" style="padding:48px 24px;">
          <table role="presentation" width="100%" style="max-width:440px;" cellpadding="0" cellspacing="0">
            <tr><td>{logo}</td></tr>
            <tr>
              <td align="center" style="padding-top:16px;">
                <div style="width:72px;height:72px;border-radius:50%;background:{accent};color:#fff;
                  font-size:36px;line-height:72px;margin:0 auto 20px;text-align:center;">{icon}</div>
                <h1 style="color:#111827;font-size:24px;margin:0 0 8px;font-family:Arial,Helvetica,sans-serif;">
                  {_esc(title)}
                </h1>
                <p style="color:#6B7280;font-size:15px;margin:0;line-height:22px;font-family:Arial,Helvetica,sans-serif;">
                  {_esc(message)}
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
