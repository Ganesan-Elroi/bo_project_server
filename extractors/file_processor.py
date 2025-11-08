# extractor/file_processor.py
"""
File Processor - Main Router
Routes files to appropriate extractors based on file type
"""

import os
from extractors.pdf_extractor import extract_text_from_pdf
from extractors.image_extractor import extract_text_from_image
from extractors.docx_extractor import extract_text_from_docx, extract_text_from_doc
from extractors.scanned_pdf_extractor import extract_text_from_scanned_pdf

from save_logs import log_debug


def get_file_extension(filename):
    """Get file extension in lowercase"""
    return os.path.splitext(filename)[1].lower()


def process_file(filename, base_path="", ocr_language='swe', try_ocr_if_empty=True):
    """
    Process any file and extract text
    Automatically detects file type and uses appropriate extractor
    
    Args:
        filename (str): File name or path
        base_path (str): Base path (local folder or URL)
        ocr_language (str): Language for OCR ('swe', 'swe', etc.)
        try_ocr_if_empty (bool): If PDF has no text, try OCR
        
    Returns:
        dict: {
            'success': bool,
            'text': str,
            'error': str,
            'file_type': str,
            'extraction_method': str
        }
    """
    result = {
        'success': False,
        'text': '',
        'error': None,
        'file_type': 'unknown',
        'extraction_method': 'none'
    }
    
    # Get file extension
    ext = get_file_extension(filename)
    result['file_type'] = ext

    
    try:
        # Route to appropriate extractor
        
        # PDF files
        if ext == '.pdf':
            result['extraction_method'] = 'pdf_text'
            success, text, error = extract_text_from_pdf(filename, base_path)
            
            # If PDF has no text and try_ocr_if_empty is True, try OCR
            if not success and try_ocr_if_empty and "scanned" in str(error).lower():
                log_debug(f"  [WARNING] PDF appears to be scanned, trying OCR...path--->{base_path}/{filename}")
                result['extraction_method'] = 'pdf_ocr'
                success, text, error = extract_text_from_scanned_pdf(filename, base_path, ocr_language)
            
            result['success'] = success
            result['text'] = text
            result['error'] = error
        
        # Image files
        elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']:
            result['extraction_method'] = 'image_ocr'
            success, text, error = extract_text_from_image(filename, base_path, ocr_language)
            result['success'] = success
            result['text'] = text
            result['error'] = error
        
        # DOCX files
        elif ext == '.docx':
            result['extraction_method'] = 'docx_text'
            success, text, error = extract_text_from_docx(filename, base_path)
            result['success'] = success
            result['text'] = text
            result['error'] = error
        
        # Old DOC files
        elif ext == '.doc':
            result['extraction_method'] = 'doc_text'
            success, text, error = extract_text_from_doc(filename, base_path)
            result['success'] = success
            result['text'] = text
            result['error'] = error
        
        # Unsupported file type
        else:
            result['error'] = f"Unsupported file type: {ext}"
            # print(f"  [ERROR] Unsupported file type: {ext}")
        
        # Print result
        if result['success']:
            char_count = len(result['text'])
            word_count = len(result['text'].split())
            log_debug(f"  [SUCCESS] Extraction completed!")
            log_debug(f"  Method: {result['extraction_method']}")
            log_debug(f"  Extracted: {char_count} characters, {word_count} words")
        else:
            # pass
            log_debug(f"  [FAILED] {result['error']}")
        
    except Exception as e:
        result['error'] = f"Unexpected error: {str(e)}"
        log_debug(f"  [ERROR] Unexpected error: {str(e)}")
    

    return result


def process_multiple_files(files_list, base_path="", ocr_language='swe'):
    """
    Process multiple files
    
    Args:
        files_list (list): List of filenames
        base_path (str): Base path for all files
        ocr_language (str): Language for OCR
        
    Returns:
        list: List of results for each file
    """
    results = []

    
    for i, filename in enumerate(files_list, 1):
        result = process_file(filename, base_path, ocr_language)
        result['filename'] = filename
        results.append(result)
    
    # Summary
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    
    return results
