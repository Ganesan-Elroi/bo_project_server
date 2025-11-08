# extractor/image_extractor.py
"""
Image Text Extractor (OCR)
Extracts text from images: PNG, JPG, JPEG using OCR (Tesseract)
"""

import pytesseract
from PIL import Image
import requests
from io import BytesIO
import os


def extract_text_from_image_file(file_path, lang='swe'):
    """
    Extract text from local image file using OCR
    
    Args:
        file_path (str): Full path to image file
        lang (str): OCR language (default: 'swe', can be 'swe' for Swedish)
        
    Returns:
        tuple: (success: bool, text: str, error: str)
    """
    try:
        if not os.path.exists(file_path):
            return False, "", f"File not found: {file_path}"
    
        # Open image
        image = Image.open(file_path)
        
        # Perform OCR
        text = pytesseract.image_to_string(image, lang=lang)
        
        if len(text.strip()) < 10:
            return False, "", "No text detected in image (OCR found very little text)"
        
        return True, text.strip(), None
        
    except Exception as e:
        return False, "", f"Error extracting text from image: {str(e)}"


def extract_text_from_image_url(url, lang='swe'):
    """
    Extract text from image via URL using OCR
    
    Args:
        url (str): URL to image file
        lang (str): OCR language
        
    Returns:
        tuple: (success: bool, text: str, error: str)
    """
    try:

        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Open image from bytes
        image = Image.open(BytesIO(response.content))
        
        
        # Perform OCR
        text = pytesseract.image_to_string(image, lang=lang)
        
        if len(text.strip()) < 10:
            return False, "", "No text detected in image (OCR found very little text)"
        
        return True, text.strip(), None
        
    except requests.exceptions.RequestException as e:
        return False, "", f"Error downloading image: {str(e)}"
    except Exception as e:
        return False, "", f"Error extracting text from image URL: {str(e)}"


def extract_text_from_image(image_path, base_path="", lang='swe'):
    """
    Extract text from image - handles both local files and URLs
    
    Args:
        image_path (str): Image filename or relative path
        base_path (str): Base path (folder path or URL)
        lang (str): OCR language ('swe', 'swe', etc.)
        
    Returns:
        tuple: (success: bool, text: str, error: str)
    """
    # Build full path
    if base_path:
        if base_path.endswith('/') or base_path.endswith('\\'):
            full_path = base_path + image_path
        else:
            full_path = os.path.join(base_path, image_path)
    else:
        full_path = image_path
    
    
    # Check if it's a URL or local file
    if full_path.startswith('http://') or full_path.startswith('https://'):
        # print("[INFO]: Image extract from live URL")
        return extract_text_from_image_url(full_path, lang)
    else:
        # print("[INFO]: Image extract from Local file")
        return extract_text_from_image_file(full_path, lang)