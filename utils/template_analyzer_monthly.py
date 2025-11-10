"""
Template Analyzer for Monthly Reports
Detects sections in templates and filters metadata
"""

from bs4 import BeautifulSoup, NavigableString
import re

try:
    from save_logs import log_debug
except:
    def log_debug(msg):
        pass


def is_instruction(text):
    """Check if text is instruction"""
    text = str(text).strip()
    return text.startswith('(') and ')' in text and len(text) > 20


def analyze_monthly_template(template_html):
    """
    Analyze monthly report template
    
    Returns:
        dict: {sections, template_type, total_sections, soup}
    """
    
    soup = BeautifulSoup(template_html, 'html.parser')
    
    log_debug("[MONTHLY_ANALYZER] Starting template analysis...")
    
    sections = []
    seen = set()
    
    # Blacklist metadata sections
    blacklist = [
        'månadsrapport', 'slutrapport', 'rapport',
        'dagens datum', 'förnamn', 'efternamn', 'personnummer'
    ]
    
    # Strategy 1: Find spans with Times New Roman
    for span in soup.find_all('span'):
        style = span.get('style', '')
        
        if 'times new roman' in style.lower():
            text = span.get_text(strip=True)
            
            # Filter: reasonable length, not instruction, not blacklisted
            if text and 5 < len(text) < 150 and text not in seen:
                if is_instruction(text):
                    continue
                
                text_lower = text.lower()
                if any(kw in text_lower for kw in blacklist):
                    log_debug(f"  [SKIP] Blacklisted: {text}")
                    continue
                
                # Check if followed by instruction
                next_elem = span.find_next_sibling()
                has_instruction = False
                if next_elem:
                    next_text = next_elem.get_text(strip=True)
                    if next_text.startswith('('):
                        has_instruction = True
                
                sections.append({
                    'name': text,
                    'element': span,
                    'type': 'text',
                    'confidence': 'high' if has_instruction else 'medium'
                })
                seen.add(text)
                log_debug(f"  [FOUND] {text}")
    
    # Strategy 2: Bold/Strong text
    for tag in soup.find_all(['b', 'strong']):
        text = tag.get_text(strip=True)
        
        if text and 5 < len(text) < 100 and text not in seen:
            if is_instruction(text):
                continue
            
            text_lower = text.lower()
            if any(kw in text_lower for kw in blacklist):
                continue
            
            sections.append({
                'name': text,
                'element': tag,
                'type': 'bold',
                'confidence': 'high'
            })
            seen.add(text)
            log_debug(f"  [FOUND] {text}")
    
    # Strategy 3: Table headers (gray background)
    for td in soup.find_all('td'):
        style = td.get('style', '').lower()
        
        if 'background-color: #cccccc' in style or 'rgb(204, 204, 204)' in style:
            text = td.get_text(strip=True)
            
            if text and text not in seen:
                if any(kw in text.lower() for kw in blacklist):
                    continue
                
                sections.append({
                    'name': text,
                    'element': td,
                    'content_element': td.find_next_sibling('td'),
                    'type': 'table',
                    'confidence': 'high'
                })
                seen.add(text)
                log_debug(f"  [FOUND] {text}")
    
    # Strategy 4: Detect plain section titles (standalone text nodes)
    for text_node in soup.find_all(string=True):
        text = text_node.strip()
        if not text or len(text) < 3:
            continue

        # Skip metadata or paragraphs
        if any(kw in text.lower() for kw in blacklist):
            continue

        # Likely a section title if followed by <br/> or empty line
        # next_elem = text_node.next_sibling
        next_elem = getattr(text_node, "next_sibling", None)

        if next_elem and getattr(next_elem, 'name', None) == 'br':
            if text not in seen:
                sections.append({
                    'name': text,
                    'element': text_node,
                    'type': 'text',
                    'confidence': 'low'
                })
                seen.add(text)
                log_debug(f"  [FOUND plain section] {text}")


    log_debug(f"[MONTHLY_ANALYZER] Found {len(sections)} sections")
    
    # Determine template type
    table_count = sum(1 for s in sections if s['type'] == 'table')
    text_count = len(sections) - table_count
    
    if table_count > 0 and text_count == 0:
        template_type = 'table'
    elif text_count > 0 and table_count == 0:
        template_type = 'text'
    else:
        template_type = 'mixed'
    
    return {
        'sections': sections,
        'template_type': template_type,
        'total_sections': len(sections),
        'soup': soup
    }