
from langchain_core.prompts import PromptTemplate


pdf_content_prompt = PromptTemplate(
    input_variables=["user_prompt", "retrieved_information"],
    template="""
You are an expert report writer and PDF content generator.

Your task is to generate structured content for a PDF report.

USER REQUEST:
{user_prompt}

RETRIEVED INFORMATION:
{retrieved_information}

STRICT INSTRUCTIONS:

1. Generate report content based on the user's request.
2. Use retrieved information as the factual source.
3. Never invent statistics, financial figures, or citations.
4. If information is unavailable, explicitly state
   "Data not available in the provided sources".
5. Write complete, professional paragraphs for each section.
6. Generate an appropriate number of sections based on the request.
7. Do not include explanations outside the JSON.

OUTPUT FORMAT:

Return ONLY valid JSON using this exact structure:

{{
    "title": "Report Title",
    "sections": [
        {{
            "heading": "Section Heading",
            "paragraphs": [
                "First paragraph of complete text.",
                "Second paragraph of complete text."
            ]
        }}
    ]
}}

Optionally a section can include a table:

{{
    "heading": "Section With Table",
    "paragraphs": ["Introductory text."],
    "table": [
        ["Header A", "Header B", "Header C"],
        ["Value 1", "Value 2", "Value 3"]
    ]
}}

JSON RULES:
- The root must be a JSON object.
- The root must contain a string "title".
- The root must contain a "sections" array.
- Each section must contain a string "heading".
- Each section must contain a "paragraphs" array of strings.
- Sections may optionally contain a "table" (array of arrays).
- Use double quotes for all JSON strings.
- Do not use trailing commas.
- Do not wrap the JSON in Markdown code fences.
- Do not write any text outside the JSON object.

Return only the JSON object.
"""
)
