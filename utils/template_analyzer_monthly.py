# utils/template_analyzer_monthly.py
"""
Template Analyzer for Monthly Reports
IMPROVED: Better detection to catch ALL section headers including short ones like "Hälsa"
FIXED: Removed overly aggressive filtering that was skipping valid headers
"""

from bs4 import BeautifulSoup, NavigableString
import re

try:
    from save_logs import log_debug
except:
    def log_debug(msg):
        pass


# Shared metadata keywords constant
METADATA_KEYWORDS = [
    'månadsrapport', 'slutrapport', 'rapport',
    'dagens datum', 'förnamn', 'efternamn', 'personnummer'
]


def is_instruction(text):
    """Check if text is instruction"""
    text = str(text).strip()
    return text.startswith('(') and ')' in text and len(text) > 20


def is_metadata(text):
    """Check if text is metadata (dates, names, PNR, placeholders)"""
    text = str(text).strip()
    
    # Check if it's a placeholder in brackets like [DOKUMENTNAMN]
    if text.startswith('[') and text.endswith(']'):
        return True
    
    # Check if it's a date (YYYY-MM-DD)
    if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
        return True
    
    # Check if it's a personal number (YYMMDD-XXXX)
    if re.match(r'^\d{6}-[A-Z0-9]{4}$', text):
        return True
    
    # Check if it's a concatenated name (no spaces, mixed case)
    if re.match(r'^[A-Z][a-z]+[A-Z][a-z]+$', text):
        return True
    
    # Check against keywords
    if any(kw in text.lower() for kw in METADATA_KEYWORDS):
        return True
    
    return False


def analyze_monthly_template(template_html):
    """
    Analyze monthly report template
    IMPROVED: Better detection to find ALL headers including "Hälsa"
    
    Returns:
        dict: {sections, template_type, total_sections, soup}
    """
    
    soup = BeautifulSoup(template_html, 'html.parser')
    
    log_debug("[MONTHLY_ANALYZER] Starting template analysis...")
    
    sections = []
    seen = set()
    
    # Strategy 1: Find <strong> tags (most reliable for headers)
    for strong in soup.find_all(['strong', 'b']):
        # Get text - handle nested structure
        inner_html = strong.decode_contents()
        
        # Split by <br/> tags in case multiple headers in one tag
        parts = re.split(r'<br\s*/?>', inner_html, flags=re.IGNORECASE)
        
        for part in parts:
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', '', part).strip()
            
            # CRITICAL: Changed minimum length from 5 to 3 to catch "Hälsa" (5 chars)
            if text and 3 <= len(text) < 100 and text not in seen:
                # Filter metadata and instructions
                if is_instruction(text) or is_metadata(text):
                    log_debug(f"  [SKIP] Metadata/instruction: {text}")
                    continue
                
                sections.append({
                    'name': text,
                    'element': strong,
                    'type': 'bold',
                    'confidence': 'high'
                })
                seen.add(text)
                log_debug(f"  [FOUND] Template header: {text}")
    
    # Strategy 2: Table headers (gray background) - only if in template table
    for td in soup.find_all('td'):
        style = td.get('style', '').lower()
        
        if 'background-color: #cccccc' in style or 'rgb(204, 204, 204)' in style:
            text = td.get_text(strip=True)
            
            if text and text not in seen and len(text) >= 3:
                if is_metadata(text):
                    log_debug(f"  [SKIP] Metadata: {text}")
                    continue
                
                sections.append({
                    'name': text,
                    'element': td,
                    'content_element': td.find_next_sibling('td'),
                    'type': 'table',
                    'confidence': 'high'
                })
                seen.add(text)
                log_debug(f"  [FOUND] Table header: {text}")
    
    # Strategy 3: Standalone text in template paragraphs
    for p in soup.find_all('p'):
        style = p.get('style', '')
        
        # Only check paragraphs with template styling (width: 650px)
        if 'width: 650px' not in style and 'width:650px' not in style:
            continue
        
        # Get direct text children only
        for child in p.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                
                # Changed: minimum 3 chars instead of 5
                if not text or len(text) < 3 or len(text) > 50:
                    continue
                
                if text in seen:
                    continue
                
                # Skip metadata
                if is_metadata(text):
                    continue
                
                # IMPROVED: More lenient check - only skip if text is EXACTLY part of existing
                # Don't skip "Hälsa" just because it might be similar to something else
                is_duplicate = False
                for existing_section in seen:
                    # Only skip if EXACT match or this text is substring of existing
                    if text == existing_section:
                        is_duplicate = True
                        break
                    # Be more specific: only skip if this is clearly a fragment
                    if len(text) < 5 and text.lower() in existing_section.lower():
                        log_debug(f"  [SKIP] Fragment of '{existing_section}': {text}")
                        is_duplicate = True
                        break
                
                if is_duplicate:
                    continue
                
                # Check if this text is ONLY significant content in paragraph
                p_text = p.get_text(strip=True)
                # Allow some flexibility - paragraph can have a bit more text
                if len(p_text) <= len(text) + 10:
                    sections.append({
                        'name': text,
                        'element': child,
                        'type': 'text',
                        'confidence': 'medium'
                    })
                    seen.add(text)
                    log_debug(f"  [FOUND] Text header: {text}")

    log_debug(f"[MONTHLY_ANALYZER] Found {len(sections)} template sections")
    
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