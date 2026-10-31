import io
import sys
import json
import re
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

from langchain_core.output_parsers import StrOutputParser

from document_processor.config.llm import llm

from document_processor.planners.ppt_planner import (
    ppt_planner_prompt
)
from document_processor.planners.excel_planner import (
    excel_planner_prompt
)
from document_processor.planners.pdf_planner import (
    pdf_report_planner_prompt
)

from document_processor.question_generation.question_generator import (
    question_generator_prompt
)
from document_processor.question_generation.question_parser import (
    QuestionListParser
)

from document_processor.rag.rag_service import (
    get_rag_response
)

from document_processor.content_generation.content_generator import (
    generate_document_content
)

from document_processor.renderers.renderer_factory import (
    render_document
)

# ======================================================
# CONFIGURATION
# ======================================================

MAX_RAG_QUESTIONS = 5
MAX_RETRIEVED_CHARACTERS = 3000
MAX_ANSWER_CHARACTERS = 400

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



def build_fallback_content(raw_text, document_type):
    raw_text = str(raw_text).strip() if raw_text else "No content generated."
    paragraphs = [p.strip() for p in raw_text.split("\n") if p.strip()]
    document_type = document_type.strip().lower()

    if document_type in ("ppt", "pptx", "powerpoint", "presentation"):
        slides = []
        for i in range(0, len(paragraphs), 4):
            chunk = paragraphs[i:i + 4]
            slides.append({"title": chunk[0][:100], "content": chunk[1:] or [chunk[0]]})
        return {"slides": slides or [{"title": "Generated Content", "content": paragraphs[:5] or ["No content available."]}]}

    if document_type in ("excel", "xlsx", "spreadsheet", "workbook"):
        rows = []
        for line in paragraphs[:30]:
            cells = [c.strip() for c in line.replace("|", "\t").split("\t") if c.strip()]
            if cells:
                rows.append(cells)
        if len(rows) >= 2:
            max_cols = max(len(r) for r in rows)
            rows = [r + [""] * (max_cols - len(r)) for r in rows]
            return {"sheets": [{"name": "Generated Data", "headers": rows[0], "rows": rows[1:]}]}
        return {"sheets": [{"name": "Generated Content", "headers": ["Content"], "rows": [[p] for p in paragraphs[:20] or ["No content available."]]}]}

    if document_type in ("pdf", "report", "pdf report"):
        sections = []
        current_heading = "Overview"
        current_paras = []
        for p in paragraphs:
            if len(p) < 80 and not p.endswith("."):
                if current_paras:
                    sections.append({"heading": current_heading, "paragraphs": current_paras})
                current_heading = p
                current_paras = []
            else:
                current_paras.append(p)
        if current_paras:
            sections.append({"heading": current_heading, "paragraphs": current_paras})
        if not sections:
            sections = [{"heading": "Report Content", "paragraphs": paragraphs[:10] or ["No content available."]}]
        return {"title": "Generated Report", "sections": sections}

    return {"sheets": [{"name": "Content", "headers": ["Content"], "rows": [[p] for p in paragraphs[:20]]}]}


def generate_illustrative_information(
    user_prompt,
    document_type,
    missing_questions,
    available_context
):
    """
    Generate clearly labelled illustrative information
    for questions that could not be answered using RAG.
    """

    if not missing_questions:
        return []

    questions_text = "\n".join(
        f"- {question}" for question in missing_questions
    )

    generation_prompt = f"""
You are an AI research analyst helping generate
complete business documents.

USER REQUEST:
{user_prompt}

DOCUMENT TYPE:
{document_type}

ADDITIONAL CONTEXT:
{available_context}

QUESTIONS FOR WHICH SOURCE DATA IS MISSING:
{questions_text}

YOUR TASK:

Generate illustrative information for the unanswered questions
so that the document can still be completed.

STRICT RULES:

1. Never claim that generated information is real or verified.
2. Generate hypothetical values and scenarios where appropriate.
3. Mark every generated figure as MODEL_GENERATED.
4. Do not create fake citations, sources, companies, or references.
5. Keep generated values internally consistent.
6. Do not describe hypothetical figures as historical observations.
7. For financial or business examples, clearly identify
   assumptions behind the illustrative values.
8. If a reliable illustrative number cannot be produced,
   describe a hypothetical scenario without inventing precision.
9. Do not alter or reproduce source-backed facts as assumptions.
10. Keep the output useful for the requested document.

OUTPUT:

For every unanswered question provide:
- Original question
- Illustrative answer
- Illustrative values, if appropriate
- Assumptions
- Classification: MODEL_GENERATED

IMPORTANT:
These are hypothetical examples, NOT actual facts.
Do not include fabricated citations.

Generate the information now.
"""

    chain = (
        llm
        | StrOutputParser()
    )

    for _attempt in range(3):
        try:
            generated_information = chain.invoke(generation_prompt)
            break
        except Exception as exc:
            if "429" in str(exc) or "rate_limit" in str(exc).lower():
                print(f"[WARN] Rate limited on illustrative gen. Waiting 30s...")
                time.sleep(30)
                continue
            raise

    if not generated_information or not generated_information.strip():
        raise RuntimeError(
            "Illustrative Information Generator returned empty output."
        )

    return [{
        "question": "Illustrative information for missing questions",
        "answer": generated_information,
        "sources": [],
        "classification": "MODEL_GENERATED",
        "verified": False,
    }]


def append_data_disclosure(content, document_type):
    """
    Automatically append a data disclosure to the final
    structured document before rendering.
    """

    disclosure_title = "Data Availability and AI-Generated Information"

    disclosure_text = (
        "This document uses information retrieved from the "
        "knowledge-base documents provided by the user. "
        "Where relevant source information was unavailable, "
        "AI-generated illustrative assumptions, hypothetical "
        "figures, or scenarios may have been included. "
        "These generated values are not verified facts, actual "
        "historical records, or official statistics. "
        "They should be independently verified before being "
        "used for business decisions or external publication. "
        "Source-backed information and AI-generated information "
        "should be interpreted separately."
    )

    document_type = document_type.lower().strip()

    if document_type in ["ppt", "pptx", "powerpoint", "presentation"]:

        content.setdefault("slides", [])

        content["slides"].append({
            "title": disclosure_title,
            "content": [disclosure_text],
        })

    elif document_type in ["pdf", "report", "pdf report"]:

        content.setdefault("sections", [])

        content["sections"].append({
            "heading": disclosure_title,
            "paragraphs": [disclosure_text],
        })

    elif document_type in ["excel", "xlsx", "spreadsheet", "workbook"]:

        content.setdefault("sheets", [])

        content["sheets"].append({
            "name": "Data_Provenance",
            "headers": [
                "Classification",
                "Description",
                "Verification Status",
            ],
            "rows": [
                [
                    "SOURCE_BACKED",
                    "Information retrieved from uploaded documents.",
                    "Source-supported; verify original source.",
                ],
                [
                    "MODEL_GENERATED",
                    "Illustrative assumptions generated by AI.",
                    "Unverified; not actual factual data.",
                ],
                [
                    "INFERRED",
                    "Analytical conclusions derived from inputs.",
                    "Depends on the provenance of its inputs.",
                ],
            ],
        })

    return content



def extract_json_candidate(raw_content: str) -> str:
    """
    Extract a JSON object from an LLM response.

    Handles:
    - Plain JSON
    - JSON wrapped in Markdown code fences
    - Explanatory text before/after a JSON object

    It does not attempt to invent missing JSON content.
    """

    if not isinstance(raw_content, str):
        raise TypeError("The LLM response must be a string.")

    cleaned = raw_content.strip()

    if not cleaned:
        raise ValueError("Content Generation returned an empty response.")

    # Remove common Markdown code fences.
    cleaned = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)

    # First try the complete response.
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return cleaned
    except json.JSONDecodeError:
        pass

    # If the model added prose, isolate the outermost JSON object.
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")

    if first_brace != -1 and last_brace > first_brace:
        candidate = cleaned[first_brace:last_brace + 1]

        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return candidate
        except json.JSONDecodeError:
            pass

    raise ValueError(
        "The response does not contain a valid JSON object."
    )


def parse_generated_content(final_content):
    """
    Convert the Content Generation LLM's response into a Python dictionary.
    """

    if isinstance(final_content, dict):
        return final_content

    if not isinstance(final_content, str):
        raise TypeError(
            "Generated content must be a JSON string or dictionary."
        )

    candidate = extract_json_candidate(final_content)

    try:
        structured_content = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Content Generation returned malformed JSON."
        ) from exc

    if not isinstance(structured_content, dict):
        raise ValueError(
            "Generated document JSON must have an object at its root."
        )

    return structured_content


def repair_generated_json(raw_content: str, document_type: str) -> str:
    """
    Ask the configured LLM to repair malformed content into JSON.

    The repair step is deliberately conservative: it must preserve the
    original information and must not invent facts, sources, or figures.
    """

    if not isinstance(raw_content, str) or not raw_content.strip():
        raise ValueError(
            "Cannot repair an empty Content Generation response."
        )

    # Bound the repair input to avoid sending an excessively large prompt.
    max_repair_input_chars = 12000
    bounded_response = raw_content[:max_repair_input_chars]

    repair_prompt = f"""
You are a strict JSON formatting and repair assistant.

DOCUMENT TYPE:
{document_type}

TASK:
Convert the ORIGINAL MODEL RESPONSE below into one valid JSON object
that can be consumed by the existing document-generation pipeline.

RULES:
1. Return ONLY a valid JSON object. No Markdown fences or explanations.
2. Preserve the original document content and intended structure.
3. Do not invent facts, statistics, sources, citations, or figures.
4. Do not remove useful content merely to make the response shorter.
5. Escape quotation marks and special characters correctly.
6. Use double quotes for all JSON keys and string values.
7. Do not add trailing commas.
8. If the original response contains a JSON object with minor syntax errors,
   repair those syntax errors while preserving its keys and values.
9. If the original response is ordinary prose and no document structure
   can be inferred, return this exact error structure instead:
   {{"_repair_error": "No document JSON structure could be recovered."}}
   Do not invent a renderer schema.
10. Any MODEL_GENERATED information must remain explicitly labelled
    illustrative and unverified. Never present it as SOURCE_BACKED.

ORIGINAL MODEL RESPONSE:
<original_response>
{bounded_response}
</original_response>

Return the repaired JSON object now.
"""

    repaired_response = (llm | StrOutputParser()).invoke(repair_prompt)

    if not isinstance(repaired_response, str) or not repaired_response.strip():
        raise ValueError("The JSON repair model returned an empty response.")

    return repaired_response.strip()


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

    for _attempt in range(3):
        try:
            content_plan = content_planner_chain.invoke({
                "user_prompt": user_prompt[:1000],
                "available_context": available_context[:500],
            })
            break
        except Exception as exc:
            if "429" in str(exc) or "rate_limit" in str(exc).lower():
                print(f"[WARN] Rate limited on planner. Waiting 30s...")
                time.sleep(30)
                continue
            raise

    if not content_plan or not content_plan.strip():
        raise RuntimeError(
            "The Content Planner returned an empty response."
        )
    content_plan = content_plan[:3000]

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

    # Limit the context sent to the Question Generator.
    MAX_CONTENT_PLAN_CHARS = 2000
    MAX_USER_PROMPT_CHARS = 1000
    MAX_CONTEXT_CHARS = 500

    question_generator_input = {
       "document_type": document_type,

       "user_prompt": user_prompt[:MAX_USER_PROMPT_CHARS],

       "available_context": available_context[:MAX_CONTEXT_CHARS],

       "content_plan": content_plan[:MAX_CONTENT_PLAN_CHARS],
    }
    try:

        print("\n[DEBUG] Question Generator Input Sizes:")

        for key, value in question_generator_input.items():
          print(f"{key}: {len(str(value))} characters")

        for _attempt in range(3):
            try:
                generated_questions = question_generator_chain.invoke(
                    question_generator_input
                )
                break
            except Exception as exc:
                if "429" in str(exc) or "rate_limit" in str(exc).lower():
                    print(f"[WARN] Rate limited on question gen. Waiting 30s...")
                    time.sleep(30)
                    continue
                raise

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
            rag_response = None
            for _rag_attempt in range(3):
                try:
                    rag_response = get_rag_response(question)
                    break
                except Exception as rate_exc:
                    if "429" in str(rate_exc) or "rate_limit" in str(rate_exc).lower():
                        print(f"[WARN] Rate limited on RAG. Waiting 30s...")
                        time.sleep(30)
                        continue
                    raise

            if rag_response is None:
                raise RuntimeError("RAG call failed after retries.")

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

            try:
                print("\n[INFO] Retrieved answer:")
                print(answer)
                print("\n[INFO] Sources:")
                print(sources)
            except (UnicodeEncodeError, UnicodeDecodeError):
                print("\n[INFO] Retrieved answer (contains special characters, display truncated)")

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
    # STEP 4: PREPARE SOURCE-BACKED INFORMATION
    # ==================================================

    retrieved_information = prepare_retrieved_information(
        rag_results
    )

    successful_count = len(retrieved_information)

    for item in retrieved_information:
        item["classification"] = "SOURCE_BACKED"
        item["verified"] = True

    failed_count = len(rag_results) - successful_count

    print(f"[INFO] Source-backed answers: {successful_count}")
    print(f"[INFO] Missing or failed answers: {failed_count}")

    # Do not confuse technical RAG failures with missing evidence.
    technical_errors = [
        item for item in rag_results if item.get("error")
    ]

    if technical_errors:
        raise RuntimeError(
            f"RAG encountered {len(technical_errors)} technical errors. "
            "Check Pinecone connectivity and LLM availability."
        )

    # Keep only the source-backed information within the input budget.
    retrieved_information = limit_retrieved_information(
        retrieved_information
    )

    # Identify questions without meaningful source-backed answers.
    answered_questions = {
        item.get("question", "").strip().lower()
        for item in retrieved_information
    }

    missing_questions = [
        item["question"]
        for item in rag_results
        if item.get("question", "").strip().lower()
        not in answered_questions
    ]

    print(f"[INFO] Missing questions: {len(missing_questions)}")

    # ==================================================
    # STEP 4.1: GENERATE ILLUSTRATIVE INFORMATION
    # ==================================================

    if missing_questions:

        print(
            "[INFO] Generating illustrative information "
            "for missing facts..."
        )

        illustrative_information = generate_illustrative_information(
            user_prompt=user_prompt,
            document_type=document_type,
            missing_questions=missing_questions,
            available_context=available_context,
        )

        retrieved_information.extend(illustrative_information)

    else:

        print("[INFO] All required questions have source-backed answers.")

    print(
        f"[INFO] Total information packages: "
        f"{len(retrieved_information)}"
    )

    if not retrieved_information:
        raise RuntimeError(
            "No information could be prepared for document generation."
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

               user_prompt=(
               user_prompt
               + "\n\nIMPORTANT DATA POLICY:\n"
               "Use SOURCE_BACKED information as evidence. "
               "Use MODEL_GENERATED information as illustrative "
                "hypothetical assumptions, not verified facts. "
                "Include useful generated assumptions in the document "
                 "and clearly label them AI-GENERATED / UNVERIFIED. "
                "Never fabricate citations or claim that generated "
                "figures represent actual historical data."
        ),

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

    print(f"[DEBUG] Content response type: {type(final_content).__name__}")
    print(f"[DEBUG] Content response length: {len(final_content) if final_content else 0}")

    # First attempt: parse the original content-generation response.
    try:
        structured_content = parse_generated_content(final_content)

    except (ValueError, TypeError) as original_parse_error:
        print(
            "[WARNING] Content Generation did not return valid JSON. "
            "Attempting one automatic repair..."
        )

        try:
            repaired_content = repair_generated_json(
                raw_content=final_content,
                document_type=document_type
            )

            print("[INFO] JSON repair response received.")

            # Parse the repaired response using the same parser.
            structured_content = parse_generated_content(repaired_content)

            if structured_content.get("_repair_error"):
                raise ValueError(
                    structured_content["_repair_error"]
                )

            # Keep the repaired response in the pipeline result for debugging.
            final_content = repaired_content

            print("[INFO] JSON repair succeeded.")

        except Exception as repair_error:
            print("[WARNING] JSON repair also failed. Building fallback document from raw text.")
            structured_content = build_fallback_content(final_content, document_type)


    structured_content = append_data_disclosure(
            structured_content,
            document_type
    )

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
