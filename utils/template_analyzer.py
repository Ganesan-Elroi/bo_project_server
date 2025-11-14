"""
Template Analyzer - FINAL VERSION
Detects section headers in Swedish HTML templates
Supports both TABLE-based and TEXT-based templates
Ignores title text like "Slutrapport", "Månadsrapport"
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


def is_placeholder_text(text):
    """Check if text is a placeholder in (...) or [...]"""
    if not text:
        return False
    
    text = text.strip()
    
    # Check for (...) pattern
    if text.startswith('(') and text.endswith(')'):
        return True
    
    # Check for [...] pattern
    if text.startswith('[') and text.endswith(']'):
        return True
    
    return False


def has_instruction_pattern(element):
    """Check if element contains instruction text like (Sammanställning...)"""
    text = element.get_text(strip=True) if hasattr(element, 'get_text') else str(element)
    if is_placeholder_text(text):
        return True, element
    
    if hasattr(element, 'next_siblings'):
        for sibling in list(element.next_siblings)[:3]:
            if isinstance(sibling, NavigableString):
                text = str(sibling).strip()
                if is_placeholder_text(text):
                    return True, sibling
            elif hasattr(sibling, 'get_text'):
                text = sibling.get_text(strip=True)
                if is_placeholder_text(text):
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


def detect_text_based_sections(soup):
    """Detect sections in TEXT templates - FINAL VERSION"""
    sections = []
    seen_names = set()
    
    # Title words to skip (these are report titles, not sections)
    skip_titles = ['slutrapport', 'månadsrapport', 'rapport', 'document', 'report']
    
    # Priority 1: <strong> tags (most common for section headers)
    for strong_tag in soup.find_all('strong'):
        text = strong_tag.get_text(strip=True)
        
        # Skip empty or very short text
        if not text or len(text) < 2:
            continue
        
        # Skip if it's a title
        if text.lower() in skip_titles:
            log_debug(f"[ANALYZER]   Skipping title: {text}")
            continue
        
        # Skip if it's a placeholder like [Förnamn]
        if is_placeholder_text(text):
            log_debug(f"[ANALYZER]   Skipping placeholder: {text}")
            continue
        
        # Skip if already seen
        if text in seen_names:
            continue
        
        # Valid section header (2-150 characters)
        if len(text) < 150:
            # Find the parent container (usually <span>, <p>, or <div>)
            parent = strong_tag.parent
            
            # Look for instruction/placeholder elements AFTER the parent container
            instruction_elem = None
            current = parent if parent else strong_tag
            
            # Check siblings of the parent container
            search_elem = current.next_sibling
            checked = 0
            
            while search_elem and checked < 5:
                checked += 1
                
                if isinstance(search_elem, NavigableString):
                    text_content = str(search_elem).strip()
                    if text_content and is_placeholder_text(text_content):
                        instruction_elem = search_elem
                        current = search_elem
                        log_debug(f"[ANALYZER]     Found placeholder text: {text_content[:50]}")
                        break
                
                elif hasattr(search_elem, 'get_text'):
                    text_content = search_elem.get_text(strip=True)
                    
                    # Check if this element contains placeholder text
                    if text_content and is_placeholder_text(text_content):
                        instruction_elem = search_elem
                        current = search_elem
                        log_debug(f"[ANALYZER]     Found placeholder element: {text_content[:50]}")
                        break
                    
                    # Stop if we hit another section header
                    elif search_elem.name == 'strong':
                        break
                    
                    # Stop if we hit substantial content
                    elif len(text_content) > 50 and not is_placeholder_text(text_content):
                        break
                
                search_elem = search_elem.next_sibling
            
            sections.append({
                'name': text,
                'type': 'text',
                'header_element': strong_tag,
                'instruction_element': instruction_elem,
                'insert_after': current,
                'confidence': 'high' if instruction_elem else 'medium'
            })
            
            seen_names.add(text)
            log_debug(f"[ANALYZER]   Detected section: {text}")
    
    # Priority 2: <font> tags (fallback for older templates)
    if not sections:
        for font_tag in soup.find_all('font'):
            face = font_tag.get('face', '')
            size = font_tag.get('size', '')
            
            if 'Times New Roman' in face or size == '3':
                text = font_tag.get_text(strip=True)
                
                # Skip placeholders and titles
                if is_placeholder_text(text) or not text or text.lower() in skip_titles:
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
    
    # Priority 3: <span> tags (fallback)
    if not sections:
        for span_tag in soup.find_all('span'):
            style = span_tag.get('style', '')
            
            if 'Times New Roman' in style and '12pt' in style:
                text = span_tag.get_text(strip=True)
                
                # Skip placeholders and titles
                if is_placeholder_text(text) or not text or text.lower() in skip_titles:
                    continue
                
                if text and len(text) < 150 and text not in seen_names:
                    has_instruction, instruction_elem = has_instruction_pattern(span_tag)
                    insert_after = instruction_elem if instruction_elem else span_tag
                    
                    sections.append({
                        'name': text,
                        'type': 'text',
                        'header_element': span_tag,
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
    
    log_debug(f"[ANALYZER] Template type: {template_type}")
    log_debug(f"[ANALYZER] Total sections detected: {len(sections)}")
    
    return {
        'sections': sections,
        'template_type': template_type,
        'total_sections': len(sections),
        'soup': soup
    }