
from __future__ import annotations

import sys
import uuid
import shutil
from pathlib import Path
from datetime import datetime

import streamlit as st


# ============================================================
# 1. PROJECT CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
UPLOAD_DIR = PROJECT_ROOT / "uploads"
KNOWLEDGE_UPLOAD_DIR = UPLOAD_DIR / "knowledge_base"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
KNOWLEDGE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ============================================================
# 2. BACKEND IMPORTS
# ============================================================

try:
    from document_processor.pipeline.document_pipeline import (
        run_document_chain,
    )

    from document_processor.rag.rag_service import (
        ingest_file,
    )

    BACKEND_IMPORT_ERROR = None

except Exception as exc:
    run_document_chain = None
    ingest_file = None
    BACKEND_IMPORT_ERROR = exc


# ============================================================
# 3. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Document Manager",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 4. CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    @import url(
        'https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap'
    );

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }

    .stApp {
        background: #0B1120;
        color: #E5E7EB;
    }

    [data-testid="stSidebar"] {
        background: #101827;
        border-right: 1px solid #263246;
    }

    [data-testid="stSidebar"] * {
        color: #E5E7EB;
    }

    .main-header {
        padding: 10px 0 25px 0;
    }

    .main-heading {
        font-size: 34px;
        font-weight: 700;
        color: #F8FAFC;
        letter-spacing: -1px;
        margin-bottom: 5px;
    }

    .sub-heading {
        color: #94A3B8;
        font-size: 14px;
    }

    .section-title {
        font-size: 19px;
        font-weight: 700;
        color: #F1F5F9;
        margin-top: 18px;
        margin-bottom: 10px;
    }

    .info-card {
        padding: 18px;
        background: #111C2E;
        border: 1px solid #26364D;
        border-radius: 12px;
        min-height: 105px;
    }

    .info-label {
        font-size: 12px;
        color: #94A3B8;
        margin-bottom: 7px;
    }

    .info-value {
        font-size: 23px;
        font-weight: 700;
        color: #F8FAFC;
    }

    .format-card {
        background: #111C2E;
        border: 1px solid #26364D;
        border-radius: 12px;
        padding: 16px;
        min-height: 120px;
    }

    .format-card h4 {
        color: #F8FAFC;
        margin-bottom: 6px;
    }

    .format-card p {
        color: #94A3B8;
        font-size: 12px;
    }

    .status-text {
        color: #94A3B8;
        font-size: 12px;
    }

    .file-card {
        padding: 17px;
        background: #111C2E;
        border: 1px solid #26364D;
        border-radius: 12px;
        margin-bottom: 10px;
    }

    div[data-testid="stButton"] button[kind="primary"] {
        background: #6366F1;
        border: none;
        color: white;
        font-weight: 600;
        border-radius: 9px;
        min-height: 44px;
    }

    div[data-testid="stButton"] button[kind="primary"]:hover {
        background: #4F46E5;
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stTextArea"] textarea {
        background: #111C2E;
        color: #F8FAFC;
        border: 1px solid #334155;
        border-radius: 8px;
    }

    div[data-testid="stSelectbox"] div[data-baseweb="select"] {
        background: #111C2E;
    }

    .step-number {
        color: #818CF8;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 1px;
    }

    hr {
        border-color: #263246;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 5. SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "page": "Create Document",
    "generated_files": [],
    "knowledge_files": [],
    "last_result": None,
    "generation_logs": [],
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# 6. HELPER FUNCTIONS
# ============================================================

FORMAT_CONFIG = {
    "PowerPoint Presentation": {
        "type": "ppt",
        "extension": ".pptx",
        "description": "Create professional slide presentations.",
        "icon": "📊",
        "mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    },
    "PDF Report": {
        "type": "pdf",
        "extension": ".pdf",
        "description": "Generate detailed, structured PDF reports.",
        "icon": "📕",
        "mime": "application/pdf",
    },
    "Excel Workbook": {
        "type": "excel",
        "extension": ".xlsx",
        "description": "Create structured spreadsheets and analytical workbooks.",
        "icon": "📈",
        "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
}


def add_log(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")

    st.session_state.generation_logs.append(
        f"[{timestamp}] {message}"
    )


def get_output_metadata(file_path: Path):
    stat = file_path.stat()

    return {
        "id": str(uuid.uuid4()),
        "name": file_path.name,
        "path": str(file_path.resolve()),
        "size": stat.st_size,
        "created_at": datetime.now().strftime(
            "%d %b %Y, %I:%M %p"
        ),
        "extension": file_path.suffix.lower(),
    }


def format_file_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"

    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"

    return f"{size / (1024 * 1024):.2f} MB"


def get_icon(extension: str):
    icons = {
        ".pdf": "📕",
        ".pptx": "📊",
        ".xlsx": "📈",
    }

    return icons.get(extension, "📄")


def validate_backend():
    if BACKEND_IMPORT_ERROR:
        st.error(
            "Backend imports failed. Check the terminal for "
            "the import error and verify your dependencies."
        )

        with st.expander("Technical details"):
            st.exception(BACKEND_IMPORT_ERROR)

        return False

    return True


# ============================================================
# 7. SIDEBAR NAVIGATION
# ============================================================

with st.sidebar:

    st.markdown(
        """
        <div style="padding:15px 4px 25px 4px;">
            <div style="font-size:27px;font-weight:700;">
                📄 Document Manager
            </div>
            <div style="font-size:12px;color:#94A3B8;">
                AI-Powered Document Generation
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.caption("WORKSPACE")

    pages = {
        "Create Document": "✦ Create Document",
        "Knowledge Base": "▤ Knowledge Base",
        "Generated Documents": "↓ Generated Documents",
    }

    for page_name, label in pages.items():

        if st.button(
            label,
            key=f"nav_{page_name}",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.page == page_name
                else "secondary"
            ),
        ):
            st.session_state.page = page_name
            st.rerun()

    st.divider()

    st.caption("WORKSPACE STATISTICS")

    total_files = len(st.session_state.generated_files)
    total_sources = len(st.session_state.knowledge_files)

    st.metric("Generated documents", total_files)
    st.metric("Knowledge base uploads", total_sources)

    st.divider()

    st.markdown(
        """
        <div style="font-size:12px;color:#64748B;">
            DOCUMENT MANAGER<br>
            AI Document Generation Engine
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# 8. HEADER
# ============================================================

def render_header(title: str, subtitle: str):

    st.markdown(
        f"""
        <div class="main-header">
            <div class="main-heading">{title}</div>
            <div class="sub-heading">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# 9. CREATE DOCUMENT PAGE
# ============================================================

def create_document_page():

    render_header(
        "Create your document",
        "Turn your instructions and source knowledge into "
        "professionally structured documents.",
    )

    st.markdown('<div class="step-number">STEP 01</div>',
                unsafe_allow_html=True)

    st.markdown(
        '<div class="section-title">Choose output format</div>',
        unsafe_allow_html=True,
    )

    selected_format = st.radio(
        "Select the document you want to generate",
        options=list(FORMAT_CONFIG.keys()),
        horizontal=True,
        label_visibility="collapsed",
        key="selected_format",
    )

    format_info = FORMAT_CONFIG[selected_format]

    col1, col2, col3 = st.columns(3)

    cards = [
        (
            "📊 PowerPoint",
            "PPTX",
            "Slide-based presentations with structured content.",
        ),
        (
            "📕 PDF Report",
            "PDF",
            "Detailed reports with sections and supporting tables.",
        ),
        (
            "📈 Excel",
            "XLSX",
            "Structured workbooks with sheets, headers and data.",
        ),
    ]

    for column, card in zip(
        [col1, col2, col3],
        cards,
    ):
        with column:
            st.markdown(
                f"""
                <div class="format-card">
                    <h4>{card[0]}</h4>
                    <p>{card[1]}</p>
                    <p>{card[2]}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    st.markdown('<div class="step-number">STEP 02</div>',
                unsafe_allow_html=True)

    st.markdown(
        '<div class="section-title">Describe your document</div>',
        unsafe_allow_html=True,
    )

    with st.form("document_generation_form"):

        user_prompt = st.text_area(
            "What should the AI generate?",
            placeholder=(
                "Example: Create a 10-slide presentation "
                "explaining our quarterly business performance "
                "for the executive team."
            ),
            height=160,
            help=(
                "Describe the document objective, subject, "
                "sections, length and any specific requirements."
            ),
        )

        st.markdown(
            "**Additional context and instructions**"
        )

        available_context = st.text_area(
            "Additional context",
            placeholder=(
                "Audience: Executive leadership team\n"
                "Reporting period: Q3 FY2026\n"
                "Tone: Professional and analytical\n"
                "Design: Minimal and corporate\n"
                "Additional requirements: Include key KPIs."
            ),
            height=120,
        )

        st.markdown(
            """
            <div class="status-text">
                Context can include audience, time periods,
                formatting preferences, definitions and
                other relevant information.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        st.markdown(
            "**Generation configuration**"
        )

        col_a, col_b = st.columns(2)

        with col_a:
            include_source_info = st.checkbox(
                "Use uploaded knowledge-base documents",
                value=True,
                help=(
                    "The pipeline already performs RAG "
                    "retrieval. This option controls whether "
                    "generation should proceed."
                ),
            )

        with col_b:
            display_debug = st.checkbox(
                "Show pipeline details after generation",
                value=True,
            )

        submitted = st.form_submit_button(
            "✦ Generate Document",
            type="primary",
            use_container_width=True,
        )

    if submitted:

        if not user_prompt.strip():
            st.warning(
                "Please describe the document you want to generate."
            )
            return

        if not validate_backend():
            return

        if not include_source_info:
            st.warning(
                "Your current backend requires source-backed RAG "
                "answers and does not yet support a no-RAG mode. "
                "Upload source documents to the Knowledge Base first."
            )
            return

        st.session_state.generation_logs = []

        progress = st.progress(0)
        status = st.status(
            "Initializing document generation...",
            expanded=True,
        )

        try:

            add_log("Starting document generation.")

            with status:

                status.write("Initializing pipeline...")
                progress.progress(10)

                add_log(
                    f"Selected document type: {format_info['type']}"
                )

                status.write(
                    "Running content planner, retrieval question "
                    "generator, RAG, content generation and renderer."
                )

                progress.progress(20)

                result = run_document_chain(
                    document_type=format_info["type"],
                    user_prompt=user_prompt.strip(),
                    available_context=(
                        available_context.strip()
                        if available_context.strip()
                        else "No additional context provided."
                    ),
                )

                progress.progress(90)

                add_log("Pipeline finished successfully.")

                status.write("Checking generated file...")

                output_path = Path(result["output_path"])

                if not output_path.exists():
                    raise FileNotFoundError(
                        f"Generated file not found: {output_path}"
                    )

                metadata = get_output_metadata(output_path)

                metadata["document_type"] = selected_format
                metadata["user_prompt"] = user_prompt.strip()

                st.session_state.generated_files.insert(
                    0,
                    metadata,
                )

                st.session_state.last_result = result

                add_log(
                    f"Output generated: {output_path.name}"
                )

                progress.progress(100)

                status.update(
                    label="Document generated successfully!",
                    state="complete",
                    expanded=False,
                )

            st.success(
                "Your document has been generated successfully."
            )

            st.session_state.page = "Generated Documents"

            st.rerun()

        except Exception as exc:

            progress.empty()

            status.update(
                label="Document generation failed.",
                state="error",
                expanded=True,
            )

            add_log(f"Generation failed: {exc}")

            st.error(
                "The pipeline encountered an error. "
                "Check the technical details below."
            )

            st.exception(exc)

    # Pipeline details from the last successful generation.

    if (
        display_debug
        and st.session_state.last_result is not None
    ):

        with st.expander("View latest pipeline details"):

            result = st.session_state.last_result

            st.markdown("**Content plan**")

            st.text(
                result.get("content_plan", "")
            )

            st.markdown("**RAG retrieval questions**")

            for index, question in enumerate(
                result.get("rag_questions", []),
                start=1,
            ):
                st.write(f"{index}. {question}")

            st.markdown("**Retrieved information**")

            for item in result.get(
                "retrieved_information", []
            ):
                with st.expander(
                    item.get("question", "Retrieved result")
                ):
                    st.write(item.get("answer", ""))
                    st.caption(
                        "Sources: "
                        + ", ".join(item.get("sources", []))
                    )


# ============================================================
# 10. KNOWLEDGE BASE PAGE
# ============================================================

def knowledge_base_page():

    render_header(
        "Knowledge Base",
        "Upload source documents that your RAG system "
        "can search when generating documents.",
    )

    st.info(
        "Uploaded files will be ingested into your existing "
        "Pinecone vector database. They become retrieval sources "
        "for future document generation."
    )

    st.markdown(
        '<div class="section-title">Upload source documents</div>',
        unsafe_allow_html=True,
    )

    uploaded_files = st.file_uploader(
        "Upload PDF, DOCX or TXT files",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="Supported formats are defined in your RAG ingestion module.",
    )

    if uploaded_files:

        st.write(
            f"**{len(uploaded_files)} file(s) selected**"
        )

        for file in uploaded_files:
            st.write(
                f"📄 {file.name} · {format_file_size(file.size)}"
            )

    if st.button(
        "⬆ Ingest Documents",
        type="primary",
        use_container_width=True,
        disabled=not uploaded_files,
    ):

        if not validate_backend():
            return

        overall_progress = st.progress(0)

        success_count = 0
        failures = []

        for index, uploaded_file in enumerate(uploaded_files):

            safe_name = (
                f"{uuid.uuid4().hex[:8]}_"
                f"{Path(uploaded_file.name).name}"
            )

            saved_path = KNOWLEDGE_UPLOAD_DIR / safe_name

            try:

                with open(saved_path, "wb") as file:
                    file.write(uploaded_file.getbuffer())

                with st.spinner(
                    f"Ingesting {uploaded_file.name}..."
                ):

                    result = ingest_file(
                        str(saved_path.resolve())
                    )

                success_count += 1

                existing_names = {
                    item["name"]
                    for item in st.session_state.knowledge_files
                }

                if uploaded_file.name not in existing_names:

                    st.session_state.knowledge_files.append({
                        "name": uploaded_file.name,
                        "stored_path": str(saved_path.resolve()),
                        "chunks": result.get("chunks", 0),
                        "ingested_at": datetime.now().strftime(
                            "%d %b %Y, %I:%M %p"
                        ),
                    })

                st.success(
                    f"{uploaded_file.name}: "
                    f"{result.get('chunks', 0)} chunks ingested."
                )

            except Exception as exc:

                failures.append(
                    f"{uploaded_file.name}: {exc}"
                )

                st.error(
                    f"Failed to ingest {uploaded_file.name}"
                )

                with st.expander("Error details"):
                    st.exception(exc)

            overall_progress.progress(
                (index + 1) / len(uploaded_files)
            )

        if success_count:
            st.success(
                f"Successfully ingested {success_count} document(s)."
            )

        if failures:
            st.warning(
                f"{len(failures)} document(s) failed."
            )

    st.divider()

    st.markdown(
        '<div class="section-title">Uploaded documents</div>',
        unsafe_allow_html=True,
    )

    if not st.session_state.knowledge_files:

        st.info(
            "No documents have been ingested in this session yet."
        )

    else:

        for index, item in enumerate(
            st.session_state.knowledge_files
        ):

            with st.container(border=True):

                col1, col2, col3 = st.columns(
                    [4, 1, 2]
                )

                with col1:
                    st.write(f"📄 **{item['name']}**")

                with col2:
                    st.write(
                        f"{item['chunks']} chunks"
                    )

                with col3:
                    st.caption(
                        item["ingested_at"]
                    )


# ============================================================
# 11. GENERATED DOCUMENTS PAGE
# ============================================================

def generated_documents_page():

    render_header(
        "Generated Documents",
        "Access, review and download your previously "
        "generated documents.",
    )

    files = st.session_state.generated_files

    total_files = len(files)

    pdf_count = sum(
        1 for item in files
        if item["extension"] == ".pdf"
    )

    ppt_count = sum(
        1 for item in files
        if item["extension"] == ".pptx"
    )

    excel_count = sum(
        1 for item in files
        if item["extension"] == ".xlsx"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total documents", total_files)

    with col2:
        st.metric("PDF reports", pdf_count)

    with col3:
        st.metric("Presentations", ppt_count)

    with col4:
        st.metric("Excel workbooks", excel_count)

    st.divider()

    col_left, col_right = st.columns(
        [3, 1]
    )

    with col_left:
        st.markdown(
            '<div class="section-title">Your files</div>',
            unsafe_allow_html=True,
        )

    with col_right:
        file_filter = st.selectbox(
            "Filter",
            ["All", "PDF", "PPTX", "XLSX"],
            label_visibility="collapsed",
        )

    if not files:

        st.info(
            "You haven't generated any documents yet. "
            "Your completed outputs will appear here."
        )

        if st.button("Create your first document"):
            st.session_state.page = "Create Document"
            st.rerun()

        return

    for index, item in enumerate(files):

        extension = item["extension"]

        if file_filter != "All":

            if extension != f".{file_filter.lower()}":
                continue

        file_path = Path(item["path"])

        if not file_path.exists():
            st.warning(
                f"{item['name']} is no longer available on disk."
            )
            continue

        with st.container(border=True):

            col1, col2, col3 = st.columns(
                [1, 5, 2]
            )

            with col1:
                st.markdown(
                    f"<div style='font-size:32px;'>"
                    f"{get_icon(extension)}</div>",
                    unsafe_allow_html=True,
                )

            with col2:

                st.markdown(
                    f"**{item['name']}**"
                )

                st.caption(
                    f"{item['document_type']} · "
                    f"{format_file_size(item['size'])} · "
                    f"{item['created_at']}"
                )

                if item.get("user_prompt"):
                    st.caption(
                        item["user_prompt"][:150]
                    )

            with col3:

                mime = FORMAT_CONFIG[
                    item["document_type"]
                ]["mime"]

                with open(file_path, "rb") as file:

                    st.download_button(
                        label="⬇ Download",
                        data=file.read(),
                        file_name=item["name"],
                        mime=mime,
                        key=f"download_{item['id']}",
                        use_container_width=True,
                    )


# ============================================================
# 12. PAGE ROUTER
# ============================================================

current_page = st.session_state.page

if current_page == "Create Document":

    create_document_page()

elif current_page == "Knowledge Base":

    knowledge_base_page()

elif current_page == "Generated Documents":

    generated_documents_page()

else:

    st.session_state.page = "Create Document"
    st.rerun()
