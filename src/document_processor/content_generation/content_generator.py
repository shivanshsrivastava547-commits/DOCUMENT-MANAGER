import json
from langchain_core.output_parsers import StrOutputParser
from document_processor.config.llm import llm

from document_processor.content_generation.prompts.ppt_prompt import (
    ppt_content_prompt
)

from document_processor.content_generation.prompts.excel_prompt import (
    excel_content_prompt
)

from document_processor.content_generation.prompts.pdf_prompt import (
    pdf_content_prompt
)


def select_content_prompt(document_type: str):

    document_type = document_type.strip().lower()

    if document_type in ["ppt", "powerpoint", "presentation"]:
        return ppt_content_prompt

    elif document_type in ["excel", "spreadsheet", "workbook"]:
        return excel_content_prompt

    elif document_type in ["pdf", "report", "pdf report"]:
        return pdf_content_prompt

    else:
        raise ValueError(
            f"Unsupported document type: {document_type}"
        )


def generate_document_content(
    document_type: str,
    user_prompt: str,
    retrieved_information: list,
) -> str:

    selected_prompt = select_content_prompt(document_type)

    # Preserve questions, answers and source metadata.
    retrieved_information_text = json.dumps(
        retrieved_information,
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    content_generation_chain = (
        selected_prompt
        | llm
        | StrOutputParser()
    )

    print("\n[INFO] Starting Content Generation LLM...")

    final_content = content_generation_chain.invoke({
        "user_prompt": user_prompt,
        "retrieved_information": retrieved_information_text,
    })

    if not final_content or not final_content.strip():
        raise RuntimeError(
            "Content Generation LLM returned empty output."
        )

    print("[INFO] Content generation completed.")

    return final_content
