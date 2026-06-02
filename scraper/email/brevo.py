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
import base64
import io
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



def _build_pdf(tenders: list[dict]) -> bytes:
    """
    Generate a PDF digest of tenders.
    Each tender shows: Title (hyperlink), Reference No, Portal, Closing Date, Direct URL.
    Returns raw PDF bytes.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer, HRFlowable
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TenderTitle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#1D4ED8"),
        leading=12,
    )
    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#374151"),
        leading=11,
    )
    url_style = ParagraphStyle(
        "URL",
        parent=styles["Normal"],
        fontSize=7,
        textColor=colors.HexColor("#6B7280"),
        leading=10,
    )
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.white,
        fontName="Helvetica-Bold",
        leading=11,
    )

    today = datetime.now(timezone.utc).strftime("%d %B %Y")
    elements = []

    # ── Title block ──────────────────────────────────────────
    elements.append(Paragraph(
        f"<b>TenderPulse Daily Digest — {today}</b>",
        ParagraphStyle("H1", parent=styles["Normal"],
                       fontSize=16, textColor=colors.HexColor("#1D4ED8"),
                       spaceAfter=4)
    ))
    elements.append(Paragraph(
        f"{len(tenders)} new tender{'s' if len(tenders) != 1 else ''} found across "
        f"{len(set(t.get('source_site','') for t in tenders))} portal{'s' if len(set(t.get('source_site','') for t in tenders)) != 1 else ''}",
        ParagraphStyle("Sub", parent=styles["Normal"],
                       fontSize=10, textColor=colors.HexColor("#6B7280"),
                       spaceAfter=12)
    ))
    elements.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor("#E5E7EB"), spaceAfter=12))

    # ── Table ────────────────────────────────────────────────
    col_widths = [7.5*cm, 3.5*cm, 3*cm, 2.5*cm]  # Title | Ref No | Portal | Deadline

    # Header row
    table_data = [[
        Paragraph("<b>Tender Title</b>", header_style),
        Paragraph("<b>Reference No</b>", header_style),
        Paragraph("<b>Portal</b>", header_style),
        Paragraph("<b>Closing Date</b>", header_style),
    ]]

    for t in tenders:
        url      = t.get("source_url") or ""
        title    = t.get("title") or "Untitled"
        ref      = t.get("reference_number") or "—"
        site     = t.get("source_site") or "—"
        deadline = t.get("deadline") or "—"
        kws      = ", ".join(t.get("keywords_matched") or [])

        # Title as hyperlink + keyword tag below
        title_para = Paragraph(
            f'<a href="{url}" color="#1D4ED8"><u>{title}</u></a>'
            f'<br/><font size="6" color="#9CA3AF">🔑 {kws}</font>',
            title_style
        )
        # URL on its own line below ref
        ref_para = Paragraph(
            f"{ref}",
            cell_style
        )
        site_para  = Paragraph(site, cell_style)
        date_para  = Paragraph(
            f'<font color="#DC2626"><b>{deadline}</b></font>' if deadline != "—" else "—",
            cell_style
        )

        table_data.append([title_para, ref_para, site_para, date_para])

        # URL row spanning all columns
        table_data.append([
            Paragraph(f'<a href="{url}" color="#6B7280"><u>{url[:90]}{"…" if len(url)>90 else ""}</u></a>',
                      url_style),
            "", "", ""
        ])

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        # Header
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0), 8),
        ("TOPPADDING",   (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING",(0, 0), (-1, 0), 6),
        # Data rows
        ("FONTSIZE",     (0, 1), (-1, -1), 8),
        ("TOPPADDING",   (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 1), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        # Alternating row colours (skip URL rows which are even-indexed after header)
        *[("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F9FAFB"))
          for i in range(2, len(table_data), 4)],
        # URL rows — span and light background
        *[("SPAN",       (0, i), (-1, i)) for i in range(2, len(table_data), 2)],
        *[("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F3F4F6"))
          for i in range(2, len(table_data), 2)],
        *[("TOPPADDING", (0, i), (-1, i), 2) for i in range(2, len(table_data), 2)],
        *[("BOTTOMPADDING",(0,i),(-1, i), 4) for i in range(2, len(table_data), 2)],
        # Grid
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("LINEBELOW",    (0, 0), (-1, 0),  1,   colors.HexColor("#1D4ED8")),
    ]))

    elements.append(tbl)
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(
        "Generated by TenderPulse — Automated Government Tender Monitoring",
        ParagraphStyle("Footer", parent=styles["Normal"],
                       fontSize=7, textColor=colors.HexColor("#9CA3AF"),
                       alignment=TA_CENTER)
    ))

    doc.build(elements)
    return buf.getvalue()


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
                "attachment": [{
                    "name":    f"TenderPulse_{today.replace(' ', '_')}.pdf",
                    "content": base64.b64encode(_build_pdf(tenders)).decode(),
                }],
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