# extractors/scanned_pdf_extractor.py
"""
Scanned PDF Text Extractor (OCR)
Extracts text from scanned PDFs (image-based PDFs) using OCR
"""

import pdf2image
import pytesseract
from PIL import Image
import requests
from io import BytesIO
import os
import tempfile
from save_logs import log_debug

os.environ["PATH"] += os.pathsep + r"C:\poppler\Library\bin"
os.environ["PATH"] += os.pathsep + r"C:\Program Files\Tesseract-OCR"


def extract_text_from_scanned_pdf_file(file_path, lang='swe'):
    log_debug(f" extract_text_from_scanned_pdf_file  function calling ...")
    """
    Extract text from scanned PDF file using OCR
    
    Args:
        file_path (str): Full path to scanned PDF file
        lang (str): OCR language ('swe', 'swe', etc.)
        
    Returns:
        tuple: (success: bool, text: str, error: str)
    """
    try:
        if not os.path.exists(file_path):
            return False, "", f"File not found: {file_path}"

        log_debug(f"  Converting PDF pages to images...")
        # Convert PDF to images
        images = pdf2image.convert_from_path(file_path, dpi=300)

        log_debug(f"  PDF has {len(images)} pages")
        log_debug(f"  Running OCR on each page (language: {lang})...")
        
        
        text = ""
        # Perform OCR on each page
        for i, image in enumerate(images[:50], 1):  # Limit to 50 pages
            log_debug(f"    Processing page {i}/{min(len(images), 50)}...")
            page_text = pytesseract.image_to_string(image, lang=lang)
            text += f"\n--- Page {i} ---\n{page_text}\n"
        
        if len(text.strip()) < 50:
            return False, "", "No text detected in scanned PDF"
        
        return True, text.strip(), None
        
    except Exception as e:
        return False, "", f"Error extracting text from scanned PDF: {str(e)}"


def extract_text_from_scanned_pdf_url(url, lang='swe'):
    log_debug(f" extract_text_from_scanned_pdf_url  function calling url...{url}")
    """
    Extract text from scanned PDF via URL using OCR
    
    Args:
        url (str): URL to scanned PDF file
        lang (str): OCR language
        
    Returns:
        tuple: (success: bool, text: str, error: str)
    """
    try:
        log_debug(f"  Downloading PDF from URL...")
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        
        # Save to temporary file (pdf2image requires a file path)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(response.content)
            tmp_path = tmp_file.name
        
        try:
            log_debug(f"  Converting PDF pages to images...")
            # Convert PDF to images
            images = pdf2image.convert_from_path(tmp_path, dpi=300)
            
            log_debug(f"  PDF has {len(images)} pages")
            log_debug(f"  Running OCR on each page (language: {lang})...")
            
            text = ""
            # Perform OCR on each page
            for i, image in enumerate(images[:50], 1):  # Limit to 50 pages
                log_debug(f"    Processing page {i}/{min(len(images), 50)}...")
                page_text = pytesseract.image_to_string(image, lang=lang)
                text += f"\n--- Page {i} ---\n{page_text}\n"
            
            if len(text.strip()) < 50:
                return False, "", "No text detected in scanned PDF"
            
            return True, text.strip(), None
            
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        
    except requests.exceptions.RequestException as e:
        return False, "", f"Error downloading PDF: {str(e)}"
    except Exception as e:
        return False, "", f"Error extracting text from scanned PDF URL: {str(e)}"


def extract_text_from_scanned_pdf(pdf_path, base_path="", lang='swe'):
    log_debug(f" extract_text_from_scanned_pdf  function calling pdf path ... {pdf_path}")
    """
    Extract text from scanned PDF - handles both local files and URLs
    
    Args:
        pdf_path (str): PDF filename or relative path
        base_path (str): Base path (folder path or URL)
        lang (str): OCR language ('swe', 'swe', etc.)
        
    Returns:
        tuple: (success: bool, text: str, error: str)
    """
    # Build full path
    if base_path:
        if base_path.endswith('/') or base_path.endswith('\\'):
            full_path = base_path + pdf_path
        else:
            full_path = os.path.join(base_path, pdf_path)
    else:
        full_path = pdf_path
    
    # log_debug(f"[PDF-OCR] Extracting from scanned PDF: {os.path.basename(pdf_path)}")
    
    # Check if it's a URL or local file
    if full_path.startswith('http://') or full_path.startswith('https://'):
        return extract_text_from_scanned_pdf_url(full_path, lang)
    else:
        return extract_text_from_scanned_pdf_file(full_path, lang)