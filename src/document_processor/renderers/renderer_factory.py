from pathlib import Path

from document_processor.renderers.pptx_renderer import render_pptx
from document_processor.renderers.excel_renderer import render_excel
from document_processor.renderers.pdf_renderer import render_pdf


def render_document(document_type, content):

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    document_type = document_type.lower().strip()

    if document_type in ["ppt", "pptx", "powerpoint"]:
        output_path = output_dir / "generated_presentation.pptx"
        return render_pptx(content, str(output_path))

    elif document_type in ["excel", "xlsx", "spreadsheet"]:
        output_path = output_dir / "generated_workbook.xlsx"
        return render_excel(content, str(output_path))

    elif document_type in ["pdf", "report"]:
        output_path = output_dir / "generated_report.pdf"
        return render_pdf(content, str(output_path))

    else:
        raise ValueError(
            f"Unsupported document type: {document_type}"
        )