# utils/template_analyzer.py
"""
Template Analyzer - Enhanced for Flexible Templates
Detects section headers in ANY HTML template structure
"""

from bs4 import BeautifulSoup, NavigableString
import re

try:
    from save_logs import log_debug
except:
    def log_debug(msg):
        pass


def normalize_text(text):
    """Normalize text for comparison"""
    if not text:
        return ""
    text = str(text).strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def is_instruction_text(text):
    """Check if text is instruction (in parentheses)"""
    text = str(text).strip()
    return text.startswith('(') and text.endswith(')')


# def extract_all_potential_sections(template_html):
#     """
#     Extract ALL potential section headers from template
#     Uses multiple detection strategies - NO rigid patterns
    
#     Returns:
#         list: [{'name': str, 'confidence': str, 'element': tag, 'type': str}]
#     """
#     soup = BeautifulSoup(template_html, 'html.parser')
    
#     potential_sections = []
#     seen = set()
    
#     log_debug("[TEMPLATE_ANALYZER] Starting flexible section detection...")
    
#     # Strategy 1: Bold/Strong text (HIGH confidence)
#     for tag in soup.find_all(['b', 'strong']):
#         text = tag.get_text(strip=True)
        
#         # Filter: reasonable length, not instruction, not seen
#         if text and 5 < len(text) < 200 and not is_instruction_text(text) and text not in seen:
#             potential_sections.append({
#                 'name': text,
#                 'confidence': 'high',
#                 'element': tag,
#                 'type': 'bold'
#             })
#             seen.add(text)
#             log_debug(f"  [BOLD] Found: {text[:50]}")
    
#     # Strategy 2: Heading tags (HIGH confidence)
#     for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
#         text = tag.get_text(strip=True)
        
#         if text and not is_instruction_text(text) and text not in seen:
#             potential_sections.append({
#                 'name': text,
#                 'confidence': 'high',
#                 'element': tag,
#                 'type': 'heading'
#             })
#             seen.add(text)
#             log_debug(f"  [HEADING] Found: {text[:50]}")
    
#     # Strategy 3: Table headers with gray background (HIGH confidence)
#     for td in soup.find_all('td'):
#         style = td.get('style', '').lower()
#         bgcolor = td.get('bgcolor', '').lower()
        
#         # Check for gray background
#         is_gray = ('background-color: #cccccc' in style or 
#                    'background-color: rgb(204, 204, 204)' in style or
#                    bgcolor in ['#cccccc', 'gray', 'grey'])
        
#         if is_gray:
#             text = td.get_text(strip=True)
            
#             if text and not is_instruction_text(text) and text not in seen:
#                 potential_sections.append({
#                     'name': text,
#                     'confidence': 'high',
#                     'element': td,
#                     'content_element': td.find_next_sibling('td'),
#                     'type': 'table_header'
#                 })
#                 seen.add(text)
#                 log_debug(f"  [TABLE] Found: {text[:50]}")
    
#     # Strategy 4: Styled spans/fonts with Times New Roman (MEDIUM confidence)
#     for tag in soup.find_all(['span', 'font']):
#         style = tag.get('style', '').lower()
#         face = tag.get('face', '').lower()
        
#         # Check for Times New Roman styling
#         if 'times new roman' in style or 'times new roman' in face:
#             text = tag.get_text(strip=True)
            
#             # Filter: looks like header (short, no excessive punctuation)
#             if text and 5 < len(text) < 200 and not is_instruction_text(text) and text not in seen:
#                 word_count = len(text.split())
#                 has_period = text.endswith('.')
                
#                 # Headers typically don't end with periods or are very short
#                 if word_count < 15 and (not has_period or word_count < 5):
#                     potential_sections.append({
#                         'name': text,
#                         'confidence': 'medium',
#                         'element': tag,
#                         'type': 'styled_text'
#                     })
#                     seen.add(text)
#                     log_debug(f"  [STYLED] Found: {text[:50]}")
    
#     # Strategy 5: Font tags with specific attributes
#     for font_tag in soup.find_all('font'):
#         face = font_tag.get('face', '')
#         size = font_tag.get('size', '')
        
#         if 'Times New Roman' in face or size == '3':
#             text = font_tag.get_text(strip=True)
            
#             if text and 5 < len(text) < 200 and not is_instruction_text(text) and text not in seen:
#                 potential_sections.append({
#                     'name': text,
#                     'confidence': 'medium',
#                     'element': font_tag,
#                     'type': 'font_text'
#                 })
#                 seen.add(text)
#                 log_debug(f"  [FONT] Found: {text[:50]}")
    
#     log_debug(f"[TEMPLATE_ANALYZER] Total sections found: {len(potential_sections)}")
    
#     # Sort: high confidence first, then by document order
#     high_conf = [s for s in potential_sections if s['confidence'] == 'high']
#     medium_conf = [s for s in potential_sections if s['confidence'] == 'medium']
    
#     return high_conf + medium_conf


# utils/template_analyzer.py

def extract_all_potential_sections(template_html):
    """
    Extract ALL potential section headers from template
    ENHANCED: Handles nested spans and elements
    """
    soup = BeautifulSoup(template_html, 'html.parser')
    
    potential_sections = []
    seen = set()
    
    log_debug("[TEMPLATE_ANALYZER] Starting flexible section detection...")
    
    # Strategy 1: Bold/Strong text (HIGH confidence)
    for tag in soup.find_all(['b', 'strong']):
        text = tag.get_text(strip=True)
        
        if text and 5 < len(text) < 200 and not is_instruction_text(text) and text not in seen:
            potential_sections.append({
                'name': text,
                'confidence': 'high',
                'element': tag,
                'type': 'bold'
            })
            seen.add(text)
            log_debug(f"  [BOLD] Found: {text[:50]}")
    
    # Strategy 2: Heading tags (HIGH confidence)
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        text = tag.get_text(strip=True)
        
        if text and not is_instruction_text(text) and text not in seen:
            potential_sections.append({
                'name': text,
                'confidence': 'high',
                'element': tag,
                'type': 'heading'
            })
            seen.add(text)
            log_debug(f"  [HEADING] Found: {text[:50]}")
    
    # Strategy 3: Table headers with gray background (HIGH confidence)
    for td in soup.find_all('td'):
        style = td.get('style', '').lower()
        bgcolor = td.get('bgcolor', '').lower()
        
        is_gray = ('background-color: #cccccc' in style or 
                   'background-color: rgb(204, 204, 204)' in style or
                   bgcolor in ['#cccccc', 'gray', 'grey'])
        
        if is_gray:
            text = td.get_text(strip=True)
            
            if text and not is_instruction_text(text) and text not in seen:
                potential_sections.append({
                    'name': text,
                    'confidence': 'high',
                    'element': td,
                    'content_element': td.find_next_sibling('td'),
                    'type': 'table_header'
                })
                seen.add(text)
                log_debug(f"  [TABLE] Found: {text[:50]}")
    
    # Strategy 4: ANY span/font with Times New Roman (ENHANCED - checks parent AND children)
    for tag in soup.find_all(['span', 'font']):
        style = tag.get('style', '').lower()
        face = tag.get('face', '').lower()
        
        # Check if THIS element or its PARENT has Times New Roman
        has_times_new_roman = False
        check_element = tag
        
        # Check up to 2 levels up
        for _ in range(3):
            if check_element:
                elem_style = check_element.get('style', '').lower()
                elem_face = check_element.get('face', '').lower()
                
                if 'times new roman' in elem_style or 'times new roman' in elem_face:
                    has_times_new_roman = True
                    break
                
                check_element = check_element.parent if hasattr(check_element, 'parent') else None
        
        if has_times_new_roman:
            # Get direct text (not from nested elements)
            text = tag.get_text(strip=True)
            
            # Filter: reasonable length, not instruction
            if text and 5 < len(text) < 200 and not is_instruction_text(text) and text not in seen:
                word_count = len(text.split())
                
                # Headers typically are short and don't end with periods
                if word_count < 20:
                    # Additional check: not full sentences
                    sentence_indicators = text.count('.') + text.count('?') + text.count('!')
                    
                    if sentence_indicators == 0 or (sentence_indicators == 1 and text.endswith('.')):
                        potential_sections.append({
                            'name': text,
                            'confidence': 'medium',
                            'element': tag,
                            'type': 'styled_text'
                        })
                        seen.add(text)
                        log_debug(f"  [STYLED] Found: {text[:50]}")
    
    # Strategy 5: Font tags with specific size
    for font_tag in soup.find_all('font'):
        size = font_tag.get('size', '')
        
        if size in ['2', '3', '4']:  # Common header sizes
            text = font_tag.get_text(strip=True)
            
            if text and 5 < len(text) < 200 and not is_instruction_text(text) and text not in seen:
                word_count = len(text.split())
                if word_count < 20:
                    potential_sections.append({
                        'name': text,
                        'confidence': 'medium',
                        'element': font_tag,
                        'type': 'font_text'
                    })
                    seen.add(text)
                    log_debug(f"  [FONT] Found: {text[:50]}")
    
    # Strategy 6: FALLBACK - Look for ANY text with specific patterns
    # This catches sections that don't match any style criteria
    if len(potential_sections) == 0:
        log_debug("[TEMPLATE_ANALYZER] No sections found with style detection, trying text pattern matching...")
        
        # Look for text that appears to be section headers based on position and content
        for element in soup.find_all(string=True):
            text = str(element).strip()
            
            # Must be reasonable length
            if text and 10 < len(text) < 150 and not is_instruction_text(text) and text not in seen:
                parent = element.parent
                
                # Skip if parent is script, style, etc.
                if parent and parent.name not in ['script', 'style', 'meta', 'link', 'title']:
                    word_count = len(text.split())
                    
                    # Check if it looks like a header (not too many words, not a sentence)
                    if word_count < 15:
                        # Check if followed by instruction text or content
                        next_sibling = parent.find_next_sibling() if parent else None
                        looks_like_header = False
                        
                        if next_sibling:
                            next_text = next_sibling.get_text(strip=True)
                            # If next text is instruction, this is likely a header
                            if next_text.startswith('(') or len(next_text) > 100:
                                looks_like_header = True
                        
                        if looks_like_header:
                            potential_sections.append({
                                'name': text,
                                'confidence': 'low',
                                'element': parent,
                                'type': 'text_pattern'
                            })
                            seen.add(text)
                            log_debug(f"  [PATTERN] Found: {text[:50]}")
    
    log_debug(f"[TEMPLATE_ANALYZER] Total sections found: {len(potential_sections)}")
    
    # Sort by confidence
    high_conf = [s for s in potential_sections if s['confidence'] == 'high']
    medium_conf = [s for s in potential_sections if s['confidence'] == 'medium']
    low_conf = [s for s in potential_sections if s['confidence'] == 'low']
    
    return high_conf + medium_conf + low_conf

def detect_table_based_sections(soup):
    """Legacy function - now uses extract_all_potential_sections"""
    sections = extract_all_potential_sections(str(soup))
    return [s for s in sections if s['type'] == 'table_header']


def detect_text_based_sections(soup):
    """Legacy function - now uses extract_all_potential_sections"""
    sections = extract_all_potential_sections(str(soup))
    return [s for s in sections if s['type'] != 'table_header']


def analyze_template(template_html):
    """
    Analyze template and detect sections (ENHANCED)
    
    Returns:
        dict: {
            'sections': list,
            'template_type': str,
            'total_sections': int,
            'soup': BeautifulSoup object
        }
    """
    soup = BeautifulSoup(template_html, 'html.parser')
    
    # Use enhanced detection
    sections = extract_all_potential_sections(template_html)
    
    # Determine template type
    table_sections = [s for s in sections if s['type'] == 'table_header']
    text_sections = [s for s in sections if s['type'] != 'table_header']
    
    if table_sections and not text_sections:
        template_type = 'table'
    elif text_sections and not table_sections:
        template_type = 'text'
    elif table_sections and text_sections:
        template_type = 'mixed'
    else:
        template_type = 'unknown'
    
    return {
        'sections': sections,
        'template_type': template_type,
        'total_sections': len(sections),
        'soup': soup
    }