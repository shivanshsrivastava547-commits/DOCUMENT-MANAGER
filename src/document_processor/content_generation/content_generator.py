import json
import time
from langchain_core.output_parsers import StrOutputParser
from document_processor.config.llm import llm

MAX_RETRIES = 3
RETRY_DELAY = 30
MAX_RETRIEVED_INFO_CHARS = 3000

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

    retrieved_information_text = json.dumps(
        retrieved_information,
        indent=None,
        ensure_ascii=False,
        default=str,
    )[:MAX_RETRIEVED_INFO_CHARS]

    content_generation_chain = (
        selected_prompt
        | llm
        | StrOutputParser()
    )

    print("\n[INFO] Starting Content Generation LLM...")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            final_content = content_generation_chain.invoke({
                "user_prompt": user_prompt[:1000],
                "retrieved_information": retrieved_information_text,
            })
            break
        except Exception as exc:
            if "429" in str(exc) or "rate_limit" in str(exc).lower():
                if attempt < MAX_RETRIES:
                    print(f"[WARN] Rate limited. Waiting {RETRY_DELAY}s before retry {attempt + 1}/{MAX_RETRIES}...")
                    time.sleep(RETRY_DELAY)
                    continue
            raise

    if not final_content or not final_content.strip():
        raise RuntimeError(
            "Content Generation LLM returned empty output."
        )

    print("[INFO] Content generation completed.")

    return final_content
