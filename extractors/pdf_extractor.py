# extractor/pdf_extractor.py
"""
PDF Text Extractor using pdfplumber
Extracts text from PDF files with excellent table and layout handling
"""

import pdfplumber
import requests
from io import BytesIO
import os
import tempfile


def extract_text_from_pdf_file(file_path):
    """
    Extract text from a local PDF file using pdfplumber
    
    Args:
        file_path (str): Full path to PDF file
        
    Returns:
        tuple: (success: bool, text: str, error: str)
    """
    try:
        if not os.path.exists(file_path):
            return False, "", f"File not found: {file_path}"
        
        
        text = ""
        
        with pdfplumber.open(file_path) as pdf:
            num_pages = len(pdf.pages)
            # print(f"  PDF has {num_pages} pages")
            
            # Extract text from all pages (limit to 50 pages for performance)
            for page_num in range(min(num_pages, 50)):
                page = pdf.pages[page_num]
                
                # Extract regular text
                page_text = page.extract_text()
                if page_text:
                    text += f"\n--- Page {page_num + 1} ---\n"
                    text += page_text + "\n"
                
                # Extract tables (IMPORTANT for your documents!)
                tables = page.extract_tables()
                if tables:
                    # print(f"    Found {len(tables)} table(s) on page {page_num + 1}")
                    for table_num, table in enumerate(tables, 1):
                        text += f"\n[Table {table_num}]\n"
                        for row in table:
                            # Clean and join cells
                            cleaned_row = [str(cell).strip() if cell else '' for cell in row]
                            text += " | ".join(cleaned_row) + "\n"
                        text += "\n"
        
        # Check if PDF has actual text
        if len(text.strip()) < 50:
            return False, "", "PDF appears to be scanned or empty (no text found). Use scanned_pdf_extractor instead."
        
        return True, text.strip(), None
        
    except Exception as e:
        return False, "", f"Error extracting PDF: {str(e)}"


def extract_text_from_pdf_url(url):
    """
    Extract text from a PDF file via URL using pdfplumber
    
    Args:
        url (str): URL to PDF file
        
    Returns:
        tuple: (success: bool, text: str, error: str)
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Save to temporary file (pdfplumber works better with file paths)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(response.content)
            tmp_path = tmp_file.name
        
        try:
            text = ""
            
            with pdfplumber.open(tmp_path) as pdf:
                num_pages = len(pdf.pages)
                # print(f"  PDF has {num_pages} pages")
                
                # Extract text from all pages (limit to 50 pages)
                for page_num in range(min(num_pages, 50)):
                    page = pdf.pages[page_num]
                    
                    # Extract regular text
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- Page {page_num + 1} ---\n"
                        text += page_text + "\n"
                    
                    # Extract tables
                    tables = page.extract_tables()
                    if tables:
                        # print(f"    Found {len(tables)} table(s) on page {page_num + 1}")
                        for table_num, table in enumerate(tables, 1):
                            text += f"\n[Table {table_num}]\n"
                            for row in table:
                                cleaned_row = [str(cell).strip() if cell else '' for cell in row]
                                text += " | ".join(cleaned_row) + "\n"
                            text += "\n"
            
            # Check if PDF has actual text
            if len(text.strip()) < 50:
                return False, "", "PDF appears to be scanned or empty (no text found). Use scanned_pdf_extractor instead."
            
            return True, text.strip(), None
            
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        
    except requests.exceptions.RequestException as e:
        return False, "", f"Error downloading PDF: {str(e)}"
    except Exception as e:
        return False, "", f"Error extracting PDF from URL: {str(e)}"


def extract_text_from_pdf(pdf_path, base_path=""):
    """
    Extract text from PDF - handles both local files and URLs
    Uses pdfplumber for excellent table and layout handling
    
    Args:
        pdf_path (str): PDF filename or relative path
        base_path (str): Base path (folder path or URL)
        
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
    
    # print(f"[PDF] Extracting PDF with pdfplumber: {os.path.basename(pdf_path)}")
    
    # Check if it's a URL or local file
    if full_path.startswith('http://') or full_path.startswith('https://'):
        return extract_text_from_pdf_url(full_path)
    else:
        return extract_text_from_pdf_file(full_path)


def get_pdf_info(pdf_path, base_path=""):
    """
    Get basic information about PDF
    
    Args:
        pdf_path (str): PDF filename or relative path
        base_path (str): Base path
        
    Returns:
        dict: PDF information
    """
    if base_path:
        if base_path.endswith('/') or base_path.endswith('\\'):
            full_path = base_path + pdf_path
        else:
            full_path = os.path.join(base_path, pdf_path)
    else:
        full_path = pdf_path
    
    try:
        if full_path.startswith('http://') or full_path.startswith('https://'):
            response = requests.get(full_path, timeout=30)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(response.content)
                tmp_path = tmp_file.name
            
            try:
                with pdfplumber.open(tmp_path) as pdf:
                    return {
                        'num_pages': len(pdf.pages),
                        'has_text': True,
                        'path': full_path,
                        'extractor': 'pdfplumber'
                    }
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        else:
            with pdfplumber.open(full_path) as pdf:
                return {
                    'num_pages': len(pdf.pages),
                    'has_text': True,
                    'path': full_path,
                    'extractor': 'pdfplumber'
                }
        
    except Exception as e:
        return {
            'error': str(e),
            'path': full_path
        }