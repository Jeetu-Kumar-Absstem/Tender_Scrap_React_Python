"""
scraper/email/brevo.py
──────────────────────
Email digest via Brevo (Sendinblue) API.

Logic:
  - Called at end of every daily run
  - If new_tenders is empty → no email sent
  - If new_tenders has items → send one HTML digest email
  - Returns True if sent, False otherwise
"""

from __future__ import annotations
import os
import structlog
from datetime import datetime, timezone
from typing import Optional

log = structlog.get_logger()


def _build_html(tenders: list[dict]) -> str:
    """Build a clean HTML email body for the tender digest."""
    today = datetime.now(timezone.utc).strftime("%d %B %Y")
    count = len(tenders)

    rows = ""
    for t in tenders:
        deadline = t.get("deadline") or "—"
        value    = t.get("estimated_value") or "—"
        org      = t.get("organization") or "—"
        location = t.get("location") or "—"
        site     = t.get("source_site") or "—"
        kws      = ", ".join(t.get("keywords_matched") or [])
        url      = t.get("source_url") or "#"
        title    = t.get("title") or "Untitled Tender"
        ref      = t.get("reference_number") or "—"

        doc_links = ""
        for doc_url in (t.get("document_urls") or [])[:3]:
            doc_links += f'<a href="{doc_url}" style="color:#2563EB;margin-right:8px;">📄 Document</a>'

        rows += f"""
        <tr>
          <td style="padding:16px;border-bottom:1px solid #E5E7EB;vertical-align:top;">
            <div style="font-weight:600;font-size:15px;color:#111827;margin-bottom:4px;">
              <a href="{url}" style="color:#1D4ED8;text-decoration:none;">{title}</a>
            </div>
            <div style="font-size:12px;color:#6B7280;margin-bottom:8px;">
              Ref: {ref} &nbsp;|&nbsp; Source: {site} &nbsp;|&nbsp; Keywords: <strong>{kws}</strong>
            </div>
            <table style="width:100%;font-size:13px;color:#374151;">
              <tr>
                <td style="padding:2px 12px 2px 0;"><strong>Organisation</strong></td>
                <td>{org}</td>
                <td style="padding:2px 12px;"><strong>Deadline</strong></td>
                <td style="color:#DC2626;font-weight:600;">{deadline}</td>
              </tr>
              <tr>
                <td style="padding:2px 12px 2px 0;"><strong>Est. Value</strong></td>
                <td>{value}</td>
                <td style="padding:2px 12px;"><strong>Location</strong></td>
                <td>{location}</td>
              </tr>
            </table>
            {"<div style='margin-top:8px;'>" + doc_links + "</div>" if doc_links else ""}
          </td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#F9FAFB;font-family:'Segoe UI',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#F9FAFB;padding:24px 0;">
        <tr><td>
          <table width="640" align="center" cellpadding="0" cellspacing="0"
                 style="background:#FFFFFF;border-radius:8px;overflow:hidden;
                        box-shadow:0 1px 3px rgba(0,0,0,0.1);">

            <!-- Header -->
            <tr>
              <td style="background:#1D4ED8;padding:24px 32px;">
                <div style="font-size:22px;font-weight:700;color:#FFFFFF;">
                  📋 TenderPulse Daily Digest
                </div>
                <div style="font-size:14px;color:#BFDBFE;margin-top:4px;">
                  {today} &nbsp;·&nbsp; {count} new tender{"s" if count != 1 else ""} found
                </div>
              </td>
            </tr>

            <!-- Tender rows -->
            <tr>
              <td style="padding:0;">
                <table width="100%" cellpadding="0" cellspacing="0">
                  {rows}
                </table>
              </td>
            </tr>

            <!-- Footer -->
            <tr>
              <td style="padding:20px 32px;background:#F3F4F6;text-align:center;
                         font-size:12px;color:#9CA3AF;">
                TenderPulse — Automated Government Tender Monitoring<br>
                Tenders sourced from {len(set(t.get('source_site','') for t in tenders))} portals today
              </td>
            </tr>

          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """


def send_digest(
    tenders: list[dict],
    run_id: Optional[str] = None,
) -> bool:
    """
    Send daily tender digest via Brevo.

    Args:
        tenders: List of tender dicts from Supabase (run's PASS tenders)
        run_id:  For logging only

    Returns:
        True if email sent, False if skipped (no tenders) or failed
    """
    if not tenders:
        log.info("email.skipped", reason="no_new_tenders", run_id=run_id)
        return False

    api_key    = os.environ["BREVO_API_KEY"]
    sender_email = os.environ["BREVO_SENDER_EMAIL"]
    sender_name  = os.environ.get("BREVO_SENDER_NAME", "TenderPulse")
    recipients   = [
        r.strip()
        for r in os.environ.get("BREVO_RECIPIENT_EMAILS", "").split(",")
        if r.strip()
    ]

    if not recipients:
        log.error("email.no_recipients")
        return False

    today = datetime.now(timezone.utc).strftime("%d %b %Y")
    subject = f"TenderPulse — {len(tenders)} New Tender{'s' if len(tenders) != 1 else ''} · {today}"
    html_body = _build_html(tenders)

    import httpx
    try:
        resp = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key":      api_key,
                "Content-Type": "application/json",
            },
            json={
                "sender": {
                    "name":  sender_name,
                    "email": sender_email,
                },
                "to": [{"email": r} for r in recipients],
                "subject":   subject,
                "htmlContent": html_body,
            },
            timeout=15,
        )
        resp.raise_for_status()
        log.info(
            "email.sent",
            recipients=recipients,
            tender_count=len(tenders),
            run_id=run_id,
        )
        return True

    except httpx.HTTPStatusError as exc:
        log.error("email.http_error", status=exc.response.status_code,
                  body=exc.response.text[:200], run_id=run_id)
        return False
    except Exception as exc:
        log.error("email.failed", error=str(exc), run_id=run_id)
        return False
