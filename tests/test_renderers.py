
from document_processor.renderers.renderer_factory import (
    render_document
)
from pathlib import Path


# ==========================================
# TEST 1: POWERPOINT
# ==========================================

ppt_content = {
    "title": "Quarterly Business Performance",
    "subtitle": "FY26 Q3",
    "slides": [
        {
            "title": "Executive Summary",
            "layout": "title_and_bullets",
            "content": [
                "Revenue increased to $10.10M.",
                "Operating performance improved.",
                "Q3 performance exceeded Q2 revenue."
            ]
        },
        {
            "title": "Revenue Comparison",
            "layout": "title_and_bullets",
            "content": [
                "Q2 Revenue: $9.40M",
                "Q3 Revenue: $10.10M"
            ]
        }
    ]
}


# ==========================================
# TEST 2: EXCEL
# ==========================================

excel_content = {
    "title": "Business Performance",
    "sheets": [
        {
            "name": "Revenue",
            "headers": ["Quarter", "Revenue"],
            "rows": [
                ["Q2 FY26", 9.4],
                ["Q3 FY26", 10.1]
            ]
        }
    ]
}


# ==========================================
# TEST 3: PDF
# ==========================================

pdf_content = {
    "title": "Quarterly Business Report",
    "sections": [
        {
            "heading": "Executive Summary",
            "paragraphs": [
                "This report presents quarterly business performance.",
                "Revenue increased from $9.40M in Q2 to $10.10M in Q3."
            ]
        },
        {
            "heading": "Revenue Performance",
            "paragraphs": [
                "Q3 revenue reached $10.10M."
            ],
            "table": [
                ["Quarter", "Revenue"],
                ["Q2 FY26", "$9.40M"],
                ["Q3 FY26", "$10.10M"]
            ]
        }
    ]
}


# ==========================================
# RUN TESTS
# ==========================================

tests = [
    ("PPT", ppt_content),
    ("EXCEL", excel_content),
    ("PDF", pdf_content)
]

for document_type, content in tests:

    print(f"\nTesting {document_type} renderer...")

    try:
        output_path = render_document(
            document_type=document_type,
            content=content
        )

        path = Path(output_path)

        if path.exists() and path.stat().st_size > 0:
            print(f"SUCCESS: {path.resolve()}")
            print(f"File size: {path.stat().st_size} bytes")
        else:
            print("FAILED: Output file missing or empty.")

    except Exception as exc:
        print(f"FAILED: {exc}")