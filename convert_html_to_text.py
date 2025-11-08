"""
HTML to Text Converter Module - IIS Compatible Version
Converts HTML content to clean, readable text
"""

from bs4 import BeautifulSoup
import re

try:
    from save_logs import log_debug
    LOGGING_ENABLED = True
except:
    LOGGING_ENABLED = False
    def log_debug(msg):
        pass


def html_to_text(html_content):
    """
    Convert HTML content to clean text
    
    Args:
        html_content (str): HTML string to convert
        
    Returns:
        str: Clean text without HTML tags
    """
    if not html_content or not isinstance(html_content, str):
        return ""
    
    try:
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "meta", "link"]):
            script.decompose()
        
        # Get text
        text = soup.get_text(separator=' ')
        
        # Clean up whitespace
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Remove excessive line breaks
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        return text
        
    except Exception as e:
        log_debug(f"[HTML_CONVERTER] [ERROR] Error converting HTML to text: {e}")
        # Fallback: remove HTML tags with regex
        text = re.sub(r'<[^>]+>', '', html_content)
        text = re.sub(r'\s+', ' ', text).strip()
        return text


def html_to_text_batch(html_list):
    """
    Convert multiple HTML contents to text
    
    Args:
        html_list (list): List of HTML strings
        
    Returns:
        list: List of clean text strings
    """
    log_debug(f"[HTML_CONVERTER] Converting {len(html_list)} HTML documents to text")
    return [html_to_text(html) for html in html_list]


def get_text_summary_info(text):
    """
    Get basic information about converted text
    
    Args:
        text (str): Text content
        
    Returns:
        dict: Information about the text (word count, char count, etc.)
    """
    words = text.split()
    info = {
        'character_count': len(text),
        'word_count': len(words),
        'estimated_tokens': int(len(words) * 1.3),  # Rough estimate: 1 word = 1.3 tokens
        'preview': text[:200] + '...' if len(text) > 200 else text
    }
    
    log_debug(f"[HTML_CONVERTER] Text info: {info['word_count']} words, {info['character_count']} chars")
    
    return info