# utils/template_mapper_vardplan.py
"""
Template Mapper for Vårdplan
Maps AI-generated bullets to vårdplan template
UNIFIED VERSION - handles multiple template formats
"""

from bs4 import BeautifulSoup, NavigableString, Tag
import re
from datetime import datetime

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
    
    if text.startswith('(') and text.endswith(')'):
        return True
    
    if text.startswith('[') and text.endswith(']'):
        return True
    
    return False


def create_bullets(bullets, soup):
    """Create HTML bullet list"""
    ul = soup.new_tag('ul')
    ul['style'] = 'list-style:disc;padding-left:25px;line-height:1.8;margin:10px 0;'
    
    for bullet in bullets:
        bullet_text = ' '.join(str(b) for b in bullet) if isinstance(bullet, list) else str(bullet)
        
        li = soup.new_tag('li')
        li['style'] = 'margin-bottom:8px;'
        
        # Highlight dates
        bullet_html = bullet_text.replace('{{HIGHLIGHT}}', '<span style="background:#fbbf24;padding:2px 6px;border-radius:3px;">')
        bullet_html = bullet_html.replace('{{/HIGHLIGHT}}', '</span>')
        
        li.append(BeautifulSoup(bullet_html, 'html.parser'))
        ul.append(li)
    
    return ul


def is_template_placeholder_text(text):
    """Check if text is template placeholder content that should be removed"""
    if not text:
        return False
    
    text = text.strip()
    
    # Empty or whitespace only
    if not text:
        return True
    
    # Bracketed placeholders
    if is_placeholder_text(text):
        return True
    
    # Template instruction phrases (Swedish)
    instruction_patterns = [
        r'^Beskriv',
        r'^Kan även',
        r'^Hur har det',
        r'^Planering',
        r'^Upppföljning kommer',
        r'\(var,?\s*när\)',
        r'^\.\.\.\.\.\.',
        r'^-\s*Att x\s',  # Template bullets starting with "- Att x"
    ]
    
    for pattern in instruction_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False


def remove_placeholders_after_element(element, soup):
    """
    Remove ALL placeholder content after given element until we hit the bullet list
    Includes: (text), [text], plain instructions, template bullets
    """
    if not element:
        return 0
    
    removed = 0
    current = element.next_sibling
    checked = 0
    max_check = 30  # Increased to handle more content
    
    while current and checked < max_check:
        checked += 1
        next_elem = current.next_sibling
        should_remove = False
        
        # Check NavigableString (plain text)
        if isinstance(current, NavigableString):
            text = str(current).strip()
            
            # Remove if empty, bracketed, or instruction text
            if not text or is_template_placeholder_text(text):
                should_remove = True
        
        # Check element nodes
        elif hasattr(current, 'name'):
            if current.name == 'br':
                should_remove = True
            
            elif current.name in ['span', 'div', 'p']:
                text = current.get_text(strip=True)
                
                # Stop if we hit our inserted bullet list (has <ul> inside)
                if current.find('ul'):
                    # Check if this is OUR bullet list (has style attribute)
                    ul = current.find('ul')
                    if ul and ul.get('style'):
                        break
                
                # Remove if empty, bracketed, or instruction text
                if not text or is_template_placeholder_text(text):
                    should_remove = True
                
                # Remove if very long (likely old template content)
                elif len(text) > 300:
                    should_remove = True
            
            elif current.name in ['strong', 'b']:
                # Check if this is another section header (ALL CAPS or > 10 chars)
                header_text = current.get_text(strip=True)
                if header_text and (header_text.isupper() or len(header_text) > 10):
                    # This is the next section, stop here
                    break
                else:
                    # Small bold text, might be sub-header, remove
                    should_remove = True
        
        if should_remove:
            try:
                if hasattr(current, 'decompose'):
                    current.decompose()
                elif hasattr(current, 'extract'):
                    current.extract()
                removed += 1
            except:
                pass
        
        current = next_elem
    
    return removed


def replace_metadata_in_soup(soup):
    """Replace metadata placeholders directly in soup object"""
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    replacements = {
        '[Dagens datum]': current_date,
        '[DAGENS DATUM]': current_date,
        '[Förnamn]': '',
        '[FÖRNAMN]': '',
        '[Efternamn]': '',
        '[EFTERNAMN]': '',
        '[Personnummer]': '',
        '[PERSONNUMMER]': '',
        '[DOKUMENTNAMN]': '',
        '[Namn]': '',
        '[NAMN]': '',
    }
    
    for element in soup.find_all(string=True):
        original_text = str(element)
        modified_text = original_text
        
        for old, new in replacements.items():
            modified_text = modified_text.replace(old, new)
        
        if modified_text != original_text:
            element.replace_with(modified_text)


def map_inline_table_section(section, bullets, soup):
    """
    Map bullets to INLINE TABLE section
    For vårdplan templates where headers and content are in same cell
    """
    header_element = section['header_element']
    
    # Create bullet wrapper
    bullet_wrapper = soup.new_tag('div')
    bullet_wrapper['style'] = 'margin:10px 0;'
    bullet_wrapper.append(create_bullets(bullets, soup))
    
    # Find insertion point - after the header element
    insert_point = header_element
    
    # If header is inside a span, use the span's parent
    if header_element.parent and header_element.parent.name == 'span':
        insert_point = header_element.parent
    
    try:
        # Insert bullets after the header
        insert_point.insert_after(bullet_wrapper)
        
        # Remove placeholder text after insertion
        removed = remove_placeholders_after_element(bullet_wrapper, soup)
        
        log_debug(f"  [MAPPED] {len(bullets)} bullets (inline_table), removed {removed} placeholders")
        return True
        
    except Exception as e:
        log_debug(f"  [ERROR] Could not insert bullets: {e}")
        return False


def map_text_section(section, bullets, soup):
    """
    Map bullets to TEXT section
    For text-based templates outside tables
    """
    header_element = section['header_element']
    
    # Create bullet wrapper
    bullet_wrapper = soup.new_tag('div')
    bullet_wrapper['style'] = 'margin:10px 0 20px 0;'
    bullet_wrapper.append(create_bullets(bullets, soup))
    
    # Find parent container
    parent = header_element.parent
    
    try:
        if parent:
            # Insert after parent container
            parent.insert_after(bullet_wrapper)
        else:
            # Fallback: insert after header
            header_element.insert_after(bullet_wrapper)
        
        # Remove placeholders
        removed = remove_placeholders_after_element(bullet_wrapper, soup)
        
        log_debug(f"  [MAPPED] {len(bullets)} bullets (text), removed {removed} placeholders")
        return True
        
    except Exception as e:
        log_debug(f"  [ERROR] Could not insert bullets: {e}")
        return False


def remove_inline_table_section(section, soup):
    """Remove section header and placeholders for inline table sections"""
    header_element = section['header_element']
    
    try:
        # Remove placeholders first
        removed = remove_placeholders_after_element(header_element, soup)
        
        # Remove the header element itself
        if header_element.parent and header_element.parent.name == 'span':
            header_element.parent.decompose()
        else:
            header_element.decompose()
        
        log_debug(f"  [REMOVED] Header and {removed} placeholders")
        return True
        
    except Exception as e:
        log_debug(f"  [ERROR] Could not remove section: {e}")
        return False


def remove_text_section(section, soup):
    """Remove section header and placeholders for text sections"""
    header_element = section['header_element']
    
    try:
        # Remove placeholders first
        removed = remove_placeholders_after_element(header_element, soup)
        
        # Remove parent container if exists
        if header_element.parent:
            header_element.parent.decompose()
        else:
            header_element.decompose()
        
        log_debug(f"  [REMOVED] Header and {removed} placeholders")
        return True
        
    except Exception as e:
        log_debug(f"  [ERROR] Could not remove section: {e}")
        return False


def map_vardplan_bullets(template_html, section_bullets, template_structure):
    """
    Map bullets to vårdplan template
    UNIFIED VERSION - handles all template types
    
    Args:
        template_html: Original template HTML
        section_bullets: Dict of {section_name: [bullets]}
        template_structure: Output from analyze_vardplan_template()
        
    Returns:
        str: Final HTML with bullets mapped
    """
    
    log_debug("[VARDPLAN_MAPPER] Starting mapping...")
    
    soup = template_structure.get('soup')
    sections = template_structure.get('sections', [])
    template_type = template_structure.get('template_type', 'unknown')
    
    if not soup:
        soup = BeautifulSoup(template_html, 'html.parser')
    
    log_debug(f"[VARDPLAN_MAPPER] Template type: {template_type}")
    log_debug(f"[VARDPLAN_MAPPER] Sections: {len(sections)}")
    log_debug(f"[VARDPLAN_MAPPER] Bullet groups: {len(section_bullets)}")
    
    # Replace metadata
    replace_metadata_in_soup(soup)
    
    # Re-analyze to get updated section references
    from utils.template_analyzer_vardplan import analyze_vardplan_template
    
    updated_analysis = analyze_vardplan_template(str(soup))
    sections = updated_analysis['sections']
    soup = updated_analysis['soup']
    
    log_debug(f"[VARDPLAN_MAPPER] After re-analysis: {len(sections)} sections")
    
    mapped = 0
    removed = 0
    
    # Process each section
    for section in sections:
        section_name = section.get('name', '')
        section_type = section.get('type', 'unknown')
        
        if not section_name:
            continue
        
        log_debug(f"[VARDPLAN_MAPPER] Processing: {section_name}")
        
        # Find matching bullets (fuzzy match)
        matched_bullets = None
        section_norm = re.sub(r'\s+', ' ', section_name.lower().strip())
        
        for bullet_key, bullets in section_bullets.items():
            bullet_norm = re.sub(r'\s+', ' ', bullet_key.lower().strip())
            
            if section_norm == bullet_norm or \
               section_norm in bullet_norm or \
               bullet_norm in section_norm:
                matched_bullets = bullets
                log_debug(f"  Matched: {bullet_key}")
                break
        
        # Check if we have valid content
        has_content = False
        if matched_bullets:
            placeholder_texts = ['', 'information saknas', 'information saknas i dokumenten',
                               'ingen information', 'saknas', 'n/a', 'none', 'nej', 'no']
            
            for bullet in matched_bullets:
                bullet_text = str(bullet).strip().lower()
                if bullet_text and bullet_text not in placeholder_texts:
                    has_content = True
                    break
        
        # Map or remove section
        if has_content:
            success = False
            
            if section_type == 'inline_table':
                success = map_inline_table_section(section, matched_bullets, soup)
            elif section_type == 'text':
                success = map_text_section(section, matched_bullets, soup)
            
            if success:
                mapped += 1
        else:
            success = False
            
            if section_type == 'inline_table':
                success = remove_inline_table_section(section, soup)
            elif section_type == 'text':
                success = remove_text_section(section, soup)
            
            if success:
                removed += 1
    
    # Convert to HTML
    html = str(soup)
    
    # Final cleanup
    html = re.sub(r'(<br\s*/?>\s*){3,}', '<br/><br/>', html)
    html = re.sub(r'<span>\s*</span>', '', html)
    html = re.sub(r'<p[^>]*>\s*</p>', '', html)
    html = re.sub(r'<div[^>]*>\s*</div>', '', html)
    
    # Verify bullets in final HTML
    bullet_count = html.count('<li')
    log_debug(f"[VARDPLAN_MAPPER] Final HTML contains {bullet_count} <li> tags")
    
    if bullet_count > 0:
        log_debug(f"[VARDPLAN_MAPPER] ✓ SUCCESS: {bullet_count} bullets inserted")
    else:
        log_debug(f"[VARDPLAN_MAPPER] ⚠ WARNING: NO bullets in final HTML!")
    
    log_debug(f"[VARDPLAN_MAPPER] Done: {mapped} mapped, {removed} removed")
    
    return html