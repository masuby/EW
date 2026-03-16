"""PDF rendering and preview utilities for the dashboard."""

import io
from pathlib import Path

import streamlit as st
from PIL import Image
import fitz  # PyMuPDF


def pdf_to_images(pdf_path: str, dpi: int = 150) -> list[bytes]:
    """Convert all pages of a PDF to PNG byte arrays.

    Returns list of PNG bytes (serializable for st.cache_data).
    """
    doc = fitz.open(pdf_path)
    images = []
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        images.append(buf.getvalue())
    doc.close()
    return images


@st.cache_data(ttl=60)
def pdf_to_images_cached(pdf_path: str, file_mtime: float, dpi: int = 150) -> list[bytes]:
    """Cached version - uses file modification time as cache key."""
    return pdf_to_images(pdf_path, dpi)


def get_pdf_pages(pdf_path: str, dpi: int = 150) -> list[bytes]:
    """Get PDF pages as PNG bytes with caching."""
    path = Path(pdf_path)
    if not path.exists():
        return []
    mtime = path.stat().st_mtime
    return pdf_to_images_cached(str(path), mtime, dpi)


def render_pdf_preview(pdf_path: str, label: str = "Preview", key_prefix: str = "pdf"):
    """Render a PDF preview with page navigation."""
    pages = get_pdf_pages(pdf_path)
    if not pages:
        st.warning(f"No PDF found at: {pdf_path}")
        return

    st.subheader(label)
    if len(pages) > 1:
        page_num = st.slider(
            "Page", 1, len(pages), 1,
            key=f"{key_prefix}_page_slider"
        )
    else:
        page_num = 1

    st.image(pages[page_num - 1],
             caption=f"Page {page_num} of {len(pages)}",
             width="stretch")


def render_side_by_side(gen_pdf_path: str, ref_pdf_path: str,
                        key_prefix: str = "compare"):
    """Render side-by-side comparison of generated vs reference PDF."""
    gen_pages = get_pdf_pages(gen_pdf_path, dpi=120) if gen_pdf_path else []
    ref_pages = get_pdf_pages(ref_pdf_path, dpi=120) if ref_pdf_path else []

    if not gen_pages and not ref_pages:
        st.info("No PDFs to compare.")
        return

    max_pages = max(len(gen_pages), len(ref_pages))
    page_num = st.slider("Page", 1, max_pages, 1, key=f"{key_prefix}_slider")

    col_gen, col_ref = st.columns(2)

    with col_gen:
        st.markdown("**Generated**")
        if page_num <= len(gen_pages):
            st.image(gen_pages[page_num - 1], width="stretch")
        else:
            st.info(f"Generated has {len(gen_pages)} pages")

    with col_ref:
        st.markdown("**Reference**")
        if page_num <= len(ref_pages):
            st.image(ref_pages[page_num - 1], width="stretch")
        else:
            st.info(f"Reference has {len(ref_pages)} pages")
