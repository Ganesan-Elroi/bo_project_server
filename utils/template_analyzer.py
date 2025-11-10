# utils/template_analyzer.py
"""
Template Analyzer - Works with ANY template structure
Detects section headers in HTML templates
"""

from bs4 import BeautifulSoup, NavigableString
import re

try:
    from save_logs import log_debug
except:
    def log_debug(msg):
        pass


def is_instruction_text(text):
    """Check if text is instruction (in parentheses)"""
    text = str(text).strip()
    return text.startswith('(') and ')' in text


def extract_all_potential_sections(template_html):
    """Extract ALL potential section headers from template"""
    soup = BeautifulSoup(template_html, 'html.parser')
    
    potential_sections = []
    seen_texts = set()
    
    log_debug("[TEMPLATE_ANALYZER] Starting section detection...")
    
    # *** ADD THIS BLACKLIST ***
    blacklist_patterns = [
        'månadsrapport', 'slutrapport', 'rapport',
        'dagens datum', 'förnamn', 'efternamn', 'personnummer',
        '[dagens datum]', '[förnamn]', '[efternamn]', '[personnummer]'
    ]
    
    for element in soup.find_all(string=True):
        # Skip if parent is script/style
        if element.parent and element.parent.name in ['script', 'style', 'meta', 'link', 'title']:
            continue
        
        text = str(element).strip()
        
        # Skip empty, seen, or instruction text
        if not text or len(text) < 5 or text in seen_texts:
            continue
        
        if is_instruction_text(text):
            continue
        
        # *** ADD THIS CHECK ***
        text_lower = text.lower()
        if any(pattern in text_lower for pattern in blacklist_patterns):
            log_debug(f"  [SKIP] Blacklisted: '{text}'")
            continue
        
        # *** ADD THIS CHECK ***
        # Skip if it's just a date or looks like metadata
        if len(text) <= 15 and (
            text.replace('-', '').replace('/', '').isdigit() or  # Date like 2025-11-10
            text.count('-') == 2 or  # Date format
            text.strip() in ['pageno', ' ']  # Empty or placeholder
        ):
            continue

        
        # Look for section header patterns
        is_section_header = False
        confidence = 'low'
        parent = element.parent
        
        # Pattern 1: Text looks like a section name (short, no periods)
        word_count = len(text.split())
        if 2 <= word_count <= 15:
            # Check if followed by instruction text
            if parent:
                next_sibling = parent.find_next_sibling()
                if next_sibling:
                    next_text = next_sibling.get_text(strip=True)
                    if next_text.startswith('('):
                        is_section_header = True
                        confidence = 'high'
        
        # Pattern 2: Inside span with Times New Roman
        if parent and parent.name == 'span':
            parent_style = parent.get('style', '')
            if 'times new roman' in parent_style.lower():
                if word_count <= 15 and not text.endswith('.'):
                    is_section_header = True
                    confidence = 'medium'
        
        # Pattern 3: Specific known section names (Swedish templates)
        section_keywords = [
            'känslo', 'beteende', 'utveckling', 'utbildning', 'skola',
            'familj', 'social', 'relationer', 'hälsa', 'händelser',
            'behandling', 'aktiviteter', 'mående'
        ]
        
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in section_keywords):
            if word_count <= 15:
                is_section_header = True
                if confidence == 'low':
                    confidence = 'medium'
        
        if is_section_header:
            # Find the best parent element for this section
            insert_element = parent
            
            # Try to find a better parent (span with styling)
            check_parent = parent
            for _ in range(3):
                if check_parent and check_parent.name in ['span', 'div']:
                    style = check_parent.get('style', '')
                    if 'font-family' in style.lower() or 'font-size' in style.lower():
                        insert_element = check_parent
                        break
                check_parent = check_parent.parent if check_parent else None
            
            potential_sections.append({
                'name': text,
                'confidence': confidence,
                'element': insert_element or parent,
                'type': 'text_section'
            })
            seen_texts.add(text)
            log_debug(f"  [SECTION] Found: '{text[:50]}' (confidence: {confidence})")
    
    # Also check for bold/strong sections
    for tag in soup.find_all(['b', 'strong']):
        text = tag.get_text(strip=True)
        if text and 5 < len(text) < 100 and text not in seen_texts:
            if not is_instruction_text(text):
                potential_sections.append({
                    'name': text,
                    'confidence': 'high',
                    'element': tag,
                    'type': 'bold_section'
                })
                seen_texts.add(text)
                log_debug(f"  [BOLD] Found: '{text[:50]}'")
    
    # Check for table headers
    for td in soup.find_all('td'):
        style = td.get('style', '').lower()
        if 'background-color: #cccccc' in style or 'background-color: rgb(204, 204, 204)' in style:
            text = td.get_text(strip=True)
            if text and text not in seen_texts and not is_instruction_text(text):
                potential_sections.append({
                    'name': text,
                    'confidence': 'high',
                    'element': td,
                    'content_element': td.find_next_sibling('td'),
                    'type': 'table_header'
                })
                seen_texts.add(text)
                log_debug(f"  [TABLE] Found: '{text[:50]}'")
    
    log_debug(f"[TEMPLATE_ANALYZER] Total sections found: {len(potential_sections)}")
    
    # Sort by confidence
    high_conf = [s for s in potential_sections if s['confidence'] == 'high']
    medium_conf = [s for s in potential_sections if s['confidence'] == 'medium']
    low_conf = [s for s in potential_sections if s['confidence'] == 'low']
    
    return high_conf + medium_conf + low_conf


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