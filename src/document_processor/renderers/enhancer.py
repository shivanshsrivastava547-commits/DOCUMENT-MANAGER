"""
Document output enhancer — professional styling for all generated documents.

Patches the individual renderers BEFORE renderer_factory imports them,
so the factory transparently uses the enhanced versions.

Activated by importing this module early via document_processor/__init__.py.
"""

from pathlib import Path

from document_processor.renderers import pptx_renderer as _pptx_mod
from document_processor.renderers import excel_renderer as _excel_mod
from document_processor.renderers import pdf_renderer as _pdf_mod

_orig_render_pptx = _pptx_mod.render_pptx
_orig_render_excel = _excel_mod.render_excel
_orig_render_pdf = _pdf_mod.render_pdf


NAVY = "#1B2A4A"
ACCENT = "#2E86DE"
LIGHT_BG = "#F0F4F8"
WHITE_HEX = "#FFFFFF"
DARK_TEXT = "#1A1A2E"
MUTED = "#64748B"
BORDER_CLR = "#D1D5DB"


# ═══════════════════════════════════════════════════════════════
#  POWERPOINT ENHANCER
# ═══════════════════════════════════════════════════════════════

def _post_process_pptx(filepath):
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    def _rgb(h):
        h = h.lstrip("#")
        return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    prs = Presentation(filepath)
    total = len(prs.slides)

    for idx, slide in enumerate(prs.slides):
        is_first = idx == 0
        is_last = idx == total - 1

        bg = slide.background.fill
        bg.solid()
        bg.fore_color.rgb = _rgb(NAVY) if is_first else _rgb(WHITE_HEX)

        shapes = list(slide.shapes)
        for s_idx, shape in enumerate(shapes):
            if not shape.has_text_frame:
                continue
            for p_idx, para in enumerate(shape.text_frame.paragraphs):
                for run in para.runs:
                    run.font.name = "Calibri"
                    if is_first:
                        if s_idx == 0:
                            run.font.size = Pt(38)
                            run.font.bold = True
                            run.font.color.rgb = _rgb(WHITE_HEX)
                        else:
                            run.font.size = Pt(17)
                            run.font.color.rgb = _rgb("#B0BEC5")
                    else:
                        if s_idx == 0 and p_idx == 0:
                            run.font.size = Pt(26)
                            run.font.bold = True
                            run.font.color.rgb = _rgb(NAVY)
                        else:
                            run.font.size = Pt(15)
                            run.font.color.rgb = _rgb(DARK_TEXT)
                if not is_first and s_idx > 0:
                    para.space_after = Pt(10)
                    para.space_before = Pt(3)

        if is_first:
            lw = int(prs.slide_width * 0.35)
            ll = int((prs.slide_width - lw) / 2)
            bar = slide.shapes.add_shape(1, ll, Inches(1.35), lw, Pt(3))
            bar.fill.solid()
            bar.fill.fore_color.rgb = _rgb(ACCENT)
            bar.line.fill.background()
        else:
            bar = slide.shapes.add_shape(1, 0, 0, prs.slide_width, Pt(5))
            bar.fill.solid()
            bar.fill.fore_color.rgb = _rgb(ACCENT)
            bar.line.fill.background()

            nb = slide.shapes.add_textbox(
                prs.slide_width - Inches(1.3),
                prs.slide_height - Inches(0.5),
                Inches(1), Inches(0.3),
            )
            p = nb.text_frame.paragraphs[0]
            p.text = f"{idx + 1} / {total}"
            p.alignment = PP_ALIGN.RIGHT
            for run in p.runs:
                run.font.size = Pt(9)
                run.font.color.rgb = _rgb(MUTED)
                run.font.name = "Calibri"

        if is_last and total > 2:
            ft = slide.shapes.add_textbox(
                Inches(0.7), prs.slide_height - Inches(0.6),
                Inches(4), Inches(0.3),
            )
            p = ft.text_frame.paragraphs[0]
            p.text = "AI-Generated Document"
            for run in p.runs:
                run.font.size = Pt(8)
                run.font.color.rgb = _rgb(MUTED)
                run.font.name = "Calibri"

    prs.save(filepath)


def _enhanced_render_pptx(content, output_path):
    path = _orig_render_pptx(content, output_path)
    try:
        _post_process_pptx(path)
    except Exception:
        pass
    return path


# ═══════════════════════════════════════════════════════════════
#  EXCEL ENHANCER
# ═══════════════════════════════════════════════════════════════

def _post_process_excel(filepath):
    from openpyxl import load_workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = load_workbook(filepath)

    hdr_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    hdr_fill = PatternFill("solid", fgColor="1B2A4A")
    hdr_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    hdr_border = Border(
        bottom=Side(style="medium", color="2E86DE"),
        left=Side(style="thin", color="1B2A4A"),
        right=Side(style="thin", color="1B2A4A"),
        top=Side(style="thin", color="1B2A4A"),
    )

    cell_font = Font(name="Calibri", size=10, color="1A1A2E")
    even_fill = PatternFill("solid", fgColor="F0F4F8")
    odd_fill = PatternFill("solid", fgColor="FFFFFF")
    cell_border = Border(
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
        top=Side(style="thin", color="D1D5DB"),
        bottom=Side(style="thin", color="D1D5DB"),
    )
    cell_align = Alignment(vertical="center", wrap_text=True)

    tab_colors = ["2E86DE", "10B981", "F59E0B", "EF4444", "8B5CF6"]

    for ws_idx, ws in enumerate(wb.worksheets):
        ws.sheet_properties.tabColor = tab_colors[ws_idx % len(tab_colors)]

        if ws.max_row is None or ws.max_row < 1:
            continue

        for cell in ws[1]:
            cell.font = hdr_font
            cell.fill = hdr_fill
            cell.alignment = hdr_align
            cell.border = hdr_border

        for row_idx in range(2, (ws.max_row or 1) + 1):
            fill = even_fill if row_idx % 2 == 0 else odd_fill
            for cell in ws[row_idx]:
                cell.font = cell_font
                cell.fill = fill
                cell.alignment = cell_align
                cell.border = cell_border

        for col_cells in ws.columns:
            letter = get_column_letter(col_cells[0].column)
            max_len = max(
                (len(str(c.value or "")) for c in col_cells), default=8
            )
            ws.column_dimensions[letter].width = min(max(max_len + 3, 12), 45)

        ws.freeze_panes = "A2"
        ws.row_dimensions[1].height = 32
        for r in range(2, (ws.max_row or 1) + 1):
            ws.row_dimensions[r].height = 24

    wb.save(filepath)


def _enhanced_render_excel(content, output_path):
    path = _orig_render_excel(content, output_path)
    try:
        _post_process_excel(path)
    except Exception:
        pass
    return path


# ═══════════════════════════════════════════════════════════════
#  PDF ENHANCER
# ═══════════════════════════════════════════════════════════════

def _safe_text(text):
    if not isinstance(text, str):
        text = str(text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _enhanced_render_pdf(content, output_path):
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    navy_c = colors.HexColor(NAVY)
    accent_c = colors.HexColor(ACCENT)
    light_c = colors.HexColor(LIGHT_BG)
    dark_c = colors.HexColor(DARK_TEXT)
    muted_c = colors.HexColor(MUTED)
    border_c = colors.HexColor(BORDER_CLR)

    doc = SimpleDocTemplate(
        output_path,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.75 * inch,
    )

    base = getSampleStyleSheet()

    s_title = ParagraphStyle(
        "ETitle", parent=base["Title"],
        fontSize=26, leading=32, textColor=navy_c,
        fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4,
    )
    s_sub = ParagraphStyle(
        "ESub", parent=base["Normal"],
        fontSize=11, textColor=muted_c,
        alignment=TA_CENTER, spaceAfter=20,
    )
    s_head = ParagraphStyle(
        "EHead", parent=base["Heading2"],
        fontSize=15, leading=20, textColor=navy_c,
        fontName="Helvetica-Bold", spaceBefore=16, spaceAfter=6,
    )
    s_body = ParagraphStyle(
        "EBody", parent=base["BodyText"],
        fontSize=10, leading=14, textColor=dark_c,
        fontName="Helvetica", alignment=TA_JUSTIFY, spaceAfter=8,
    )

    story = []

    story.append(Spacer(1, 30))
    story.append(Paragraph(_safe_text(content.get("title", "Report")), s_title))
    story.append(HRFlowable(
        width="50%", thickness=2, color=accent_c,
        spaceBefore=6, spaceAfter=8, hAlign="CENTER",
    ))
    story.append(Paragraph("AI-Generated Document", s_sub))
    story.append(Spacer(1, 16))

    for section in content.get("sections", []):
        story.append(HRFlowable(
            width="100%", thickness=0.5, color=border_c,
            spaceBefore=10, spaceAfter=2,
        ))
        story.append(Paragraph(_safe_text(section.get("heading", "")), s_head))

        for para_text in section.get("paragraphs", []):
            try:
                story.append(Paragraph(_safe_text(para_text), s_body))
            except Exception:
                story.append(Paragraph(para_text[:500], s_body))

        if "table" in section and section["table"]:
            tbl_data = section["table"]
            tbl = Table(tbl_data, repeatRows=1)
            cmds = [
                ("BACKGROUND", (0, 0), (-1, 0), navy_c),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("TEXTCOLOR", (0, 1), (-1, -1), dark_c),
                ("GRID", (0, 0), (-1, -1), 0.5, border_c),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
            for i in range(1, len(tbl_data)):
                if i % 2 == 0:
                    cmds.append(("BACKGROUND", (0, i), (-1, i), light_c))
            tbl.setStyle(TableStyle(cmds))
            story.append(Spacer(1, 6))
            story.append(tbl)
            story.append(Spacer(1, 10))

    def _page_deco(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(accent_c)
        canvas.setLineWidth(2)
        canvas.line(
            0.75 * inch, doc.pagesize[1] - 0.55 * inch,
            doc.pagesize[0] - 0.75 * inch, doc.pagesize[1] - 0.55 * inch,
        )
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(muted_c)
        canvas.drawRightString(
            doc.pagesize[0] - 0.75 * inch, 0.45 * inch,
            f"Page {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_page_deco, onLaterPages=_page_deco)
    return output_path


# ═══════════════════════════════════════════════════════════════
#  APPLY PATCHES — runs at import time
# ═══════════════════════════════════════════════════════════════

_pptx_mod.render_pptx = _enhanced_render_pptx
_excel_mod.render_excel = _enhanced_render_excel
_pdf_mod.render_pdf = _enhanced_render_pdf
