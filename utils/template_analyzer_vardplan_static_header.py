# utils/template_analyzer_vardplan.py
"""
Template Analyzer for Vårdplan
Detects sections in vårdplan templates - supports multiple structures
UNIFIED VERSION - works for any template format
"""

from bs4 import BeautifulSoup, NavigableString
import re

try:
    from save_logs import log_debug
except:
    def log_debug(msg):
        pass


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


def is_metadata_keyword(text):
    """Check if text is a metadata/static header keyword"""
    if not text:
        return False
    
    text = text.lower().strip()
    
    # Static headers that should not get bullets
    static_headers = [
        'vårdplan', 'genomförandeplan', 'slutrapport', 'månadsrapport',
        'socialsekreterare', 'konsulent', 'närvarande', 'handläggare',
        'medhandläggare', 'ansvarig handläggare', 
        'handling upprättad', 'dagens datum', 'datum',
        'förnamn', 'efternamn', 'personnummer', 'namn',
        'barnet', 'vårdnadshavare', 'telefon', 'mobil', 'e-post',
        'folkbokföringsadress', 'fullständig adress',
        'underskrift', 'namnförtydligande'
    ]
    
    # Check if text matches any static header
    for header in static_headers:
        if text == header or text.startswith(header + ':'):
            return True
    
    return False


def detect_bold_sections_in_cell(soup):
    """
    Detect sections marked with bold text inside table cells
    For Vårdplan templates where all content is in ONE cell with bold headers
    """
    sections = []
    seen_names = set()
    
    log_debug("[ANALYZER] Detecting bold sections in cells...")
    
    # Find all table cells
    for table in soup.find_all('table'):
        for cell in table.find_all(['td', 'th']):
            # Look for bold elements (strong, b, or font-weight: bold)
            bold_elements = []
            
            # Method 1: <strong> and <b> tags
            bold_elements.extend(cell.find_all(['strong', 'b']))
            
            # Method 2: Spans with font-weight: bold
            for span in cell.find_all('span', style=True):
                style = span.get('style', '')
                if 'font-weight' in style and 'bold' in style:
                    bold_elements.append(span)
            
            # Process each bold element
            for bold in bold_elements:
                text = bold.get_text(strip=True)
                
                # Skip if empty or too long
                if not text or len(text) < 2 or len(text) > 150:
                    continue
                
                # Skip dates (YYYY-MM-DD format)
                if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
                    log_debug(f"  [SKIP] Date: {text}")
                    continue
                
                # Skip metadata/static headers
                if is_metadata_keyword(text):
                    log_debug(f"  [SKIP] Static header: {text}")
                    continue
                
                # Skip placeholders
                if is_placeholder_text(text):
                    log_debug(f"  [SKIP] Placeholder: {text}")
                    continue
                
                # Skip duplicates
                if text in seen_names:
                    continue
                
                # This is a valid section header
                sections.append({
                    'name': text,
                    'type': 'inline_table',
                    'header_element': bold,
                    'content_cell': cell,
                    'confidence': 'high'
                })
                
                seen_names.add(text)
                log_debug(f"  [FOUND] {text}")
    
    return sections


def detect_text_based_sections(soup):
    """
    Detect sections in text-based templates
    For templates without tables
    """
    sections = []
    seen_names = set()
    
    log_debug("[ANALYZER] Detecting text-based sections...")
    
    # Look for <strong> tags outside of tables
    for strong_tag in soup.find_all('strong'):
        # Skip if inside a table (already handled)
        if strong_tag.find_parent('table'):
            continue
        
        text = strong_tag.get_text(strip=True)
        
        # Skip empty, too short, or too long
        if not text or len(text) < 2 or len(text) > 150:
            continue
        
        # Skip metadata
        if is_metadata_keyword(text):
            log_debug(f"  [SKIP] Static header: {text}")
            continue
        
        # Skip placeholders
        if is_placeholder_text(text):
            continue
        
        # Skip duplicates
        if text in seen_names:
            continue
        
        sections.append({
            'name': text,
            'type': 'text',
            'header_element': strong_tag,
            'confidence': 'high'
        })
        
        seen_names.add(text)
        log_debug(f"  [FOUND] {text}")
    
    return sections


def analyze_vardplan_template(template_html):
    """
    Analyze vårdplan template to detect sections
    Works for multiple template formats
    
    Returns:
        dict: {
            'template_type': str,
            'sections': list,
            'soup': BeautifulSoup object,
            'total_sections': int
        }
    """
    
    log_debug("[VARDPLAN_ANALYZER] Starting template analysis...")
    
    soup = BeautifulSoup(template_html, 'html.parser')
    
    # Strategy 1: Look for bold sections inside table cells (most common for vårdplan)
    inline_sections = detect_bold_sections_in_cell(soup)
    
    # Strategy 2: Look for text-based sections (fallback)
    text_sections = detect_text_based_sections(soup)
    
    # Determine template type
    if inline_sections:
        template_type = 'inline_table'
        sections = inline_sections
        log_debug(f"[VARDPLAN_ANALYZER] Template type: inline_table")
    elif text_sections:
        template_type = 'text'
        sections = text_sections
        log_debug(f"[VARDPLAN_ANALYZER] Template type: text")
    else:
        template_type = 'unknown'
        sections = []
        log_debug(f"[VARDPLAN_ANALYZER] Template type: unknown")
    
    log_debug(f"[VARDPLAN_ANALYZER] Found {len(sections)} sections total")
    
    if sections:
        log_debug(f"[VARDPLAN_ANALYZER] Section names: {[s['name'] for s in sections]}")
    
    return {
        'template_type': template_type,
        'sections': sections,
        'soup': soup,
        'total_sections': len(sections)
    }