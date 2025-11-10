# utils/template_analyzer.py
"""
Template Analyzer - Swedish Section Detection
Detects section headers in Swedish HTML templates
Supports both TABLE-based and TEXT-based templates
"""

from bs4 import BeautifulSoup, NavigableString
import re

try:
    from save_logs import log_debug
except:
    def log_debug(msg):
        pass


def normalize_text(text):
    """Normalize Swedish text for comparison"""
    if not text:
        return ""
    text = str(text).strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def has_instruction_pattern(element):
    """Check if element contains instruction text like (Sammanställning...)"""
    text = element.get_text(strip=True) if hasattr(element, 'get_text') else str(element)
    if text.startswith('(') and 'sammanställning' in text.lower():
        return True, element
    
    if hasattr(element, 'next_siblings'):
        for sibling in list(element.next_siblings)[:3]:
            if isinstance(sibling, NavigableString):
                text = str(sibling).strip()
                if text.startswith('(') and 'sammanställning' in text.lower():
                    return True, sibling
            elif hasattr(sibling, 'get_text'):
                text = sibling.get_text(strip=True)
                if text.startswith('(') and 'sammanställning' in text.lower():
                    return True, sibling
    
    return False, None


def detect_table_based_sections(soup):
    """Detect sections in TABLE templates with gray header cells"""
    sections = []
    tables = soup.find_all('table')
    
    for table in tables:
        rows = table.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            
            for cell in cells:
                style = cell.get('style', '')
                
                # Check for gray background
                if 'background-color: #cccccc' in style.lower() or 'background-color: rgb(204, 204, 204)' in style.lower():
                    text = cell.get_text(strip=True)
                    text = re.sub(r'\s+', ' ', text)
                    
                    if text and len(text) < 150:
                        content_cell = cell.find_next_sibling('td')
                        
                        sections.append({
                            'name': text,
                            'type': 'table',
                            'header_element': cell,
                            'content_element': content_cell,
                            'confidence': 'high'
                        })
    
    return sections


# def detect_text_based_sections(soup):
#     """Detect sections in TEXT templates - FIXED for strong tags"""
#     sections = []
#     seen_names = set()
    
#     # Priority 1: <strong> tags (most common for section headers)
#     for strong_tag in soup.find_all('strong'):
#         text = strong_tag.get_text(strip=True)
        
#         # Skip empty or very short text
#         if not text or len(text) < 2:
#             continue
            
#         # Skip if it's a placeholder pattern
#         if text.startswith('[') and text.endswith(']'):
#             continue
            
#         # Skip if already seen
#         if text in seen_names:
#             continue
        
#         # Valid section header (2-150 characters)
#         if len(text) < 150:
#             # Find instruction/placeholder element after the header
#             instruction_elem = None
#             current = strong_tag
            
#             # Search through next siblings for (AI CONTENT) or (...) or [...]
#             for sibling in list(strong_tag.next_siblings)[:5]:
#                 if isinstance(sibling, NavigableString):
#                     sibling_text = str(sibling).strip()
#                     if sibling_text.startswith('(') or sibling_text.startswith('['):
#                         instruction_elem = sibling
#                         current = sibling
#                         break
#                 elif hasattr(sibling, 'get_text'):
#                     sibling_text = sibling.get_text(strip=True)
#                     if sibling_text.startswith('(') or sibling_text.startswith('['):
#                         instruction_elem = sibling
#                         current = sibling
#                         break
#                     elif sibling.name == 'br':
#                         current = sibling
#                     else:
#                         break
            
#             sections.append({
#                 'name': text,
#                 'type': 'text',
#                 'header_element': strong_tag,
#                 'instruction_element': instruction_elem,
#                 'insert_after': current,
#                 'confidence': 'high' if instruction_elem else 'medium'
#             })
            
#             seen_names.add(text)
    
#     # Priority 2: <font> tags (fallback)
#     if not sections:
#         for font_tag in soup.find_all('font'):
#             face = font_tag.get('face', '')
#             size = font_tag.get('size', '')
            
#             if 'Times New Roman' in face or size == '3':
#                 text = font_tag.get_text(strip=True)
                
#                 # Skip placeholders
#                 if (text.startswith('[') and text.endswith(']')) or not text:
#                     continue
                
#                 if text and len(text) < 150 and text not in seen_names:
#                     has_instruction, instruction_elem = has_instruction_pattern(font_tag)
#                     insert_after = instruction_elem if instruction_elem else font_tag
                    
#                     sections.append({
#                         'name': text,
#                         'type': 'text',
#                         'header_element': font_tag,
#                         'instruction_element': instruction_elem,
#                         'insert_after': insert_after,
#                         'confidence': 'high' if has_instruction else 'medium'
#                     })
                    
#                     seen_names.add(text)
    
#     # Priority 3: <span> tags (fallback)
#     if not sections:
#         for span_tag in soup.find_all('span'):
#             style = span_tag.get('style', '')
            
#             if 'Times New Roman' in style and '12pt' in style:
#                 text = span_tag.get_text(strip=True)
                
#                 # Skip placeholders
#                 if (text.startswith('[') and text.endswith(']')) or not text:
#                     continue
                
#                 if text and len(text) < 150 and text not in seen_names:
#                     has_instruction, instruction_elem = has_instruction_pattern(span_tag)
#                     insert_after = instruction_elem if instruction_elem else span_tag
                    
#                     sections.append({
#                         'name': text,
#                         'type': 'text',
#                         'header_element': span_tag,
#                         'instruction_element': instruction_elem,
#                         'insert_after': insert_after,
#                         'confidence': 'high' if has_instruction else 'medium'
#                     })
                    
#                     seen_names.add(text)
    
#     return sections


def detect_text_based_sections(soup):
    """Detect sections in TEXT templates - IMPROVED"""
    sections = []
    seen_names = set()
    
    # Common title words to skip (not real sections)
    skip_titles = ['slutrapport', 'månadsrapport', 'rapport', 'document']
    
    # Priority 1: <strong> tags
    for strong_tag in soup.find_all('strong'):
        text = strong_tag.get_text(strip=True)
        
        # Skip empty or very short text
        if not text or len(text) < 2:
            continue
        
        # Skip title text
        if text.lower() in skip_titles:
            continue
        
        # Skip placeholders
        if text.startswith('[') and text.endswith(']'):
            continue
        
        # Skip if already seen
        if text in seen_names:
            continue
        
        # Valid section header (2-150 characters)
        if len(text) < 150:
            # Find instruction/placeholder element OUTSIDE the strong tag
            instruction_elem = None
            current = strong_tag
            
            # Look at SIBLINGS of the strong tag, not children
            for sibling in list(strong_tag.next_siblings)[:10]:
                if isinstance(sibling, NavigableString):
                    sibling_text = str(sibling).strip()
                    if sibling_text and (sibling_text.startswith('(') or sibling_text.startswith('[')):
                        instruction_elem = sibling
                        current = sibling
                        break
                elif hasattr(sibling, 'get_text'):
                    sibling_text = sibling.get_text(strip=True)
                    if sibling_text and (sibling_text.startswith('(') or sibling_text.startswith('[')):
                        instruction_elem = sibling
                        current = sibling
                        break
                    elif sibling.name == 'br':
                        current = sibling
                    elif sibling.name == 'div':
                        # Check if div contains placeholder
                        div_text = sibling.get_text(strip=True)
                        if div_text.startswith('(') or div_text.startswith('['):
                            instruction_elem = sibling
                            current = sibling
                            break
                        else:
                            break
                    else:
                        break
            
            sections.append({
                'name': text,
                'type': 'text',
                'header_element': strong_tag,
                'instruction_element': instruction_elem,
                'insert_after': current,
                'confidence': 'high' if instruction_elem else 'medium'
            })
            
            seen_names.add(text)
    
    # Priority 2: <font> tags (fallback)
    if not sections:
        for font_tag in soup.find_all('font'):
            face = font_tag.get('face', '')
            size = font_tag.get('size', '')
            
            if 'Times New Roman' in face or size == '3':
                text = font_tag.get_text(strip=True)
                
                # Skip placeholders and titles
                if (text.startswith('[') and text.endswith(']')) or not text or text.lower() in skip_titles:
                    continue
                
                if text and len(text) < 150 and text not in seen_names:
                    has_instruction, instruction_elem = has_instruction_pattern(font_tag)
                    insert_after = instruction_elem if instruction_elem else font_tag
                    
                    sections.append({
                        'name': text,
                        'type': 'text',
                        'header_element': font_tag,
                        'instruction_element': instruction_elem,
                        'insert_after': insert_after,
                        'confidence': 'high' if has_instruction else 'medium'
                    })
                    
                    seen_names.add(text)
    
    return sections


def analyze_template(template_html):
    """
    Analyze template and detect sections
    
    Returns:
        dict: {
            'sections': list,
            'template_type': str,
            'total_sections': int,
            'soup': BeautifulSoup object
        }
    """
    soup = BeautifulSoup(template_html, 'html.parser')
    
    table_sections = detect_table_based_sections(soup)
    text_sections = detect_text_based_sections(soup)
    
    if table_sections and not text_sections:
        template_type = 'table'
        sections = table_sections
    elif text_sections and not table_sections:
        template_type = 'text'
        sections = text_sections
    elif table_sections and text_sections:
        template_type = 'mixed'
        sections = table_sections + text_sections
    else:
        template_type = 'unknown'
        sections = []
    
    return {
        'sections': sections,
        'template_type': template_type,
        'total_sections': len(sections),
        'soup': soup
    }