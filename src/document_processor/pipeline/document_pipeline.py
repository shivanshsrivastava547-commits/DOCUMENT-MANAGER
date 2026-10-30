
import json
import re
from pathlib import Path

from document_processor.config.llm import llm
from document_processor.planners.ppt_planner import ppt_planner_prompt
from document_processor.planners.excel_planner import excel_planner_prompt
from document_processor.planners.pdf_planner import pdf_report_planner_prompt
from document_processor.question_generation.question_generator import (
    question_generator_prompt
)

from langchain_core.output_parsers import StrOutputParser

from question_parser import QuestionListParser
from RAG.rag_service import get_rag_response

from content_generation.content_generator import (
    generate_document_content
)

from renderers.renderer_factory import render_document


# ======================================================
# CONFIGURATION
# ======================================================

MAX_RAG_QUESTIONS = 12
MAX_RETRIEVED_CHARACTERS = 9000
MAX_ANSWER_CHARACTERS = 1200

OUTPUT_DIR = Path("outputs")


# ======================================================
# HELPER FUNCTIONS
# ======================================================

def select_planner_prompt(document_type: str):

    document_type = document_type.strip().lower()

    if document_type in ["ppt", "pptx", "powerpoint", "presentation"]:
        return ppt_planner_prompt

    elif document_type in ["excel", "xlsx", "spreadsheet", "workbook"]:
        return excel_planner_prompt

    elif document_type in ["pdf", "report", "pdf report"]:
        return pdf_report_planner_prompt

    else:
        raise ValueError(
            f"Unsupported document type: {document_type}"
        )


def limit_questions(questions, max_questions=MAX_RAG_QUESTIONS):

    unique_questions = []
    seen_questions = set()

    for question in questions:

        if not isinstance(question, str):
            continue

        question = question.strip()

        if not question:
            continue

        normalized_question = re.sub(
            r"\s+", " ", question.lower()
        )

        if normalized_question in seen_questions:
            continue

        seen_questions.add(normalized_question)
        unique_questions.append(question)

    return unique_questions[:max_questions]


def is_valid_rag_answer(answer):

    if not isinstance(answer, str):
        return False

    answer = answer.strip()

    if not answer:
        return False

    missing_phrases = [
        "i couldn't find relevant information",
        "i could not find relevant information",
        "no relevant information found",
        "information not available in the provided documents",
        "not found in the provided documents",
        "not mentioned in the provided documents",
        "the provided documents do not contain",
        "the uploaded documents do not contain",
        "unable to find relevant information",
    ]

    answer_lower = answer.lower()

    if any(
        phrase in answer_lower
        for phrase in missing_phrases
    ):
        return False

    return True


def prepare_retrieved_information(rag_results):

    retrieved_information = []

    for item in rag_results:

        if item.get("error"):
            continue

        answer = item.get("answer", "")
        sources = item.get("sources", [])

        if not is_valid_rag_answer(answer):
            continue

        if not sources:
            continue

        retrieved_information.append({
            "question": item.get("question"),
            "answer": answer.strip()[:MAX_ANSWER_CHARACTERS],
            "sources": sources,
        })

    return retrieved_information


def limit_retrieved_information(retrieved_information):

    limited_information = []
    total_characters = 0

    for item in retrieved_information:

        item_text = json.dumps(
            item,
            ensure_ascii=False,
            default=str
        )

        item_length = len(item_text)

        if total_characters + item_length > MAX_RETRIEVED_CHARACTERS:
            break

        limited_information.append(item)
        total_characters += item_length

    return limited_information


def parse_generated_content(final_content):

    """
    Convert the Content Generation LLM's JSON response
    into a Python dictionary for the rendering layer.
    """

    if isinstance(final_content, dict):
        return final_content

    if not isinstance(final_content, str):
        raise TypeError(
            "Generated content must be a JSON string or dictionary."
        )

    cleaned_content = final_content.strip()

    # Remove Markdown JSON code fences if present.
    cleaned_content = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned_content,
        flags=re.IGNORECASE
    )

    cleaned_content = re.sub(
        r"\s*```$",
        "",
        cleaned_content
    )

    try:
        structured_content = json.loads(cleaned_content)

    except json.JSONDecodeError as exc:

        raise ValueError(
            "Content Generation returned ordinary text or invalid JSON. "
            "Update the document-specific content generation prompt "
            "to return valid structured JSON."
        ) from exc

    if not isinstance(structured_content, dict):
        raise ValueError(
            "Generated document JSON must have an object at its root."
        )

    return structured_content


# ======================================================
# MAIN DOCUMENT GENERATION PIPELINE
# ======================================================

def run_document_chain(
    document_type: str,
    user_prompt: str,
    available_context: str = "No additional context provided."
):

    """
    Complete document generation pipeline:

    1. Content Planning
    2. RAG Question Generation
    3. RAG Retrieval
    4. Retrieved Information Filtering
    5. Content Generation
    6. Structured Content Parsing
    7. Document Rendering
    8. Output Validation

    Returns pipeline results and the generated file path.
    """

    # ==================================================
    # STEP 1: CONTENT PLANNER
    # ==================================================

    print("\n" + "=" * 70)
    print("STEP 1: CONTENT PLANNER")
    print("=" * 70)

    selected_prompt = select_planner_prompt(document_type)

    content_planner_chain = (
        selected_prompt
        | llm
        | StrOutputParser()
    )

    print("\n[INFO] Generating content plan...")

    content_plan = content_planner_chain.invoke({
        "user_prompt": user_prompt,
        "available_context": available_context,
    })

    if not content_plan or not content_plan.strip():
        raise RuntimeError(
            "The Content Planner returned an empty response."
        )

    print("[INFO] Content plan generated successfully.")
    print(
        f"[DEBUG] Content plan length: "
        f"{len(content_plan)} characters"
    )

    # ==================================================
    # STEP 2: RAG QUESTION GENERATOR
    # ==================================================

    print("\n" + "=" * 70)
    print("STEP 2: RAG QUESTION GENERATOR")
    print("=" * 70)

    question_parser = QuestionListParser()

    question_generator_chain = (
        question_generator_prompt
        | llm
        | question_parser
    )

    print("\n[INFO] Generating RAG questions...")

    question_generator_input = {
        "document_type": document_type,
        "user_prompt": user_prompt,
        "available_context": available_context,
        "content_plan": content_plan,
    }

    try:

        generated_questions = question_generator_chain.invoke(
            question_generator_input
        )

    except Exception as exc:

        raise RuntimeError(
            f"RAG Question Generator or parser failed: {exc}"
        ) from exc

    if not generated_questions:
        raise RuntimeError(
            "The RAG Question Generator returned no valid questions."
        )

    rag_questions = limit_questions(generated_questions)

    print(
        f"[INFO] Question Generator produced "
        f"{len(rag_questions)} questions."
    )

    for index, question in enumerate(rag_questions, start=1):
        print(f"{index}. {question}")

    # ==================================================
    # STEP 3: RAG RETRIEVAL
    # ==================================================

    print("\n" + "=" * 70)
    print("STEP 3: RAG RETRIEVAL")
    print("=" * 70)

    rag_results = []

    for index, question in enumerate(rag_questions, start=1):

        print(
            f"\n[INFO] Processing question "
            f"{index}/{len(rag_questions)}"
        )

        print(f"Question: {question}")

        try:

            rag_response = get_rag_response(question)

            if not isinstance(rag_response, dict):
                raise TypeError(
                    "RAG response must be a dictionary."
                )

            answer = rag_response.get("answer", "")
            sources = rag_response.get("sources", [])

            rag_results.append({
                "question": question,
                "answer": answer,
                "sources": sources,
            })

            print("\n[INFO] Retrieved answer:")
            print(answer)

            print("\n[INFO] Sources:")
            print(sources)

        except Exception as exc:

            rag_results.append({
                "question": question,
                "answer": None,
                "sources": [],
                "error": str(exc),
            })

            print(
                f"[ERROR] RAG failed for question "
                f"{index}: {exc}"
            )

    # ==================================================
    # STEP 4: PREPARE RETRIEVED INFORMATION
    # ==================================================

    print("\n" + "=" * 70)
    print("STEP 4: PREPARING RETRIEVED INFORMATION")
    print("=" * 70)

    retrieved_information = prepare_retrieved_information(
        rag_results
    )

    successful_count = len(retrieved_information)
    failed_count = len(rag_results) - successful_count

    print(f"[INFO] Valid source-backed answers: {successful_count}")
    print(f"[INFO] Missing or failed answers: {failed_count}")

    if successful_count == 0:
        raise RuntimeError(
            "No meaningful source-backed answers were retrieved. "
            "Content generation stopped."
        )

    retrieved_information = limit_retrieved_information(
        retrieved_information
    )

    if not retrieved_information:
        raise RuntimeError(
            "Retrieved information exceeded the configured input budget."
        )

    # ==================================================
    # STEP 5: CONTENT GENERATION
    # ==================================================

    print("\n" + "=" * 70)
    print("STEP 5: CONTENT GENERATION")
    print("=" * 70)

    print("[INFO] Generating document content...")

    try:

        final_content = generate_document_content(
            document_type=document_type,
            user_prompt=user_prompt,
            retrieved_information=retrieved_information,
        )

    except Exception as exc:

        raise RuntimeError(
            f"Content Generation failed: {exc}"
        ) from exc

    if not final_content:
        raise RuntimeError(
            "Content Generation returned empty output."
        )

    print("[INFO] Content generation completed.")

    # ==================================================
    # STEP 6: PARSE STRUCTURED CONTENT
    # ==================================================

    print("\n" + "=" * 70)
    print("STEP 6: PARSING STRUCTURED CONTENT")
    print("=" * 70)

    structured_content = parse_generated_content(final_content)

    print("[INFO] Structured document content parsed successfully.")

    # ==================================================
    # STEP 7: DOCUMENT RENDERING
    # ==================================================

    print("\n" + "=" * 70)
    print("STEP 7: DOCUMENT RENDERING")
    print("=" * 70)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print(
        f"[INFO] Rendering {document_type.upper()} document..."
    )

    try:

        output_path = render_document(
            document_type=document_type,
            content=structured_content
        )

    except Exception as exc:

        raise RuntimeError(
            f"Document rendering failed: {exc}"
        ) from exc

    output_path = Path(output_path)

    if not output_path.exists():
        raise RuntimeError(
            "Renderer completed but the output file was not found."
        )

    if output_path.stat().st_size == 0:
        raise RuntimeError(
            "Generated document is empty."
        )

    print("[INFO] Document rendered successfully.")
    print(f"[INFO] Output file: {output_path.resolve()}")
    print(f"[INFO] File size: {output_path.stat().st_size} bytes")

    # ==================================================
    # STEP 8: RETURN RESULTS
    # ==================================================

    return {
        "document_type": document_type,
        "content_plan": content_plan,
        "rag_questions": rag_questions,
        "rag_results": rag_results,
        "retrieved_information": retrieved_information,
        "final_content": final_content,
        "structured_content": structured_content,
        "output_path": str(output_path.resolve()),
    }


# ======================================================
# MAIN EXECUTION
# ======================================================

if __name__ == "__main__":

    result = run_document_chain(
        document_type="PPT",

        user_prompt=(
            "Create a 10-slide presentation on "
            "quarterly business performance."
        ),

        available_context=(
            "The audience is the executive team. "
            "The company sells software subscriptions."
        ),
    )

    print("\n" + "=" * 70)
    print("DOCUMENT GENERATION COMPLETED")
    print("=" * 70)

    print("\nGenerated file:")
    print(result["output_path"])

    # Save generated content for debugging.
    with open(
        "generated_content.txt",
        "w",
        encoding="utf-8"
    ) as file:

        file.write(result["final_content"])

    # Save pipeline debug information.
    with open(
        "pipeline_debug.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            {
                "content_plan": result["content_plan"],
                "rag_questions": result["rag_questions"],
                "rag_results": result["rag_results"],
                "retrieved_information": result["retrieved_information"],
                "output_path": result["output_path"],
            },
            file,
            indent=4,
            ensure_ascii=False,
            default=str
        )

    print("\n[INFO] Debug information saved.")
    print("[INFO] Actual document file generated.")
