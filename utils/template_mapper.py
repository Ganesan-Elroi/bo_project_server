"""
Template Mapper - Inserts AI summaries and removes instructions
"""

from bs4 import BeautifulSoup, NavigableString
import re
from datetime import datetime

try:
    from save_logs import log_debug, log_separator
except:
    def log_debug(msg):
        pass
    def log_separator(char='=', length=70):
        pass


def is_instruction_text(text):
    """Check if text is instruction"""
    text = str(text).strip()
    return text.startswith('(') and ')' in text and len(text) > 20


def create_bullet_html(bullets, soup):
    """Create HTML bullet list"""
    ul = soup.new_tag('ul')
    ul['style'] = 'list-style:disc;padding-left:25px;line-height:1.8;margin:10px 0;'
    
    for bullet in bullets:
        if isinstance(bullet, list):
            bullet_text = ' '.join(str(b) for b in bullet if b)
        else:
            bullet_text = str(bullet)
        
        li = soup.new_tag('li')
        li['style'] = 'margin-bottom:8px;'
        
        # Handle date highlighting
        bullet_html = bullet_text.replace('{{HIGHLIGHT}}', '<span style="background:#fbbf24;padding:2px 6px;border-radius:3px;">')
        bullet_html = bullet_html.replace('{{/HIGHLIGHT}}', '</span>')
        
        li.append(BeautifulSoup(bullet_html, 'html.parser'))
        ul.append(li)
    
    return ul


def remove_instructions_after_element(element):
    """Remove instruction text after an element"""
    if not element:
        return
    
    # Remove next siblings if they're instructions
    next_elem = element.next_sibling
    removed_count = 0
    
    for _ in range(10):  # Check up to 10 siblings
        if not next_elem:
            break
        
        next_next = next_elem.next_sibling if hasattr(next_elem, 'next_sibling') else None
        should_remove = False
        
        if isinstance(next_elem, NavigableString):
            text = str(next_elem).strip()
            # Remove if it's instruction text or just whitespace/br
            if is_instruction_text(text) or not text:
                should_remove = True
        elif hasattr(next_elem, 'name'):
            if next_elem.name == 'br':
                should_remove = True
            elif next_elem.name == 'span':
                text = next_elem.get_text(strip=True)
                if is_instruction_text(text):
                    should_remove = True
        
        if should_remove:
            try:
                if hasattr(next_elem, 'decompose'):
                    next_elem.decompose()
                elif hasattr(next_elem, 'extract'):
                    next_elem.extract()
                removed_count += 1
            except:
                pass
        else:
            # Stop when we hit non-instruction content
            break
        
        next_elem = next_next
    
    if removed_count > 0:
        log_debug(f"    Removed {removed_count} instruction elements")


def map_section_with_bullets(section, bullets, soup):
    """Map bullets to any section type"""
    element = section.get('element')
    section_type = section.get('type')
    
    if not element or not bullets:
        return False
    
    # Remove instructions after this section
    remove_instructions_after_element(element)
    
    # Handle table sections differently
    if section_type == 'table_header':
        content_cell = section.get('content_element')
        if content_cell:
            content_cell.clear()
            bullet_list = create_bullet_html(bullets, soup)
            content_cell.append(bullet_list)
            log_debug(f"    Mapped to table cell")
            return True
    
    # For text sections, insert bullets after the header
    bullet_div = soup.new_tag('div')
    bullet_div['style'] = 'margin:10px 0 20px 0;'
    bullet_list = create_bullet_html(bullets, soup)
    bullet_div.append(bullet_list)
    
    # Insert after element
    element.insert_after(bullet_div)
    log_debug(f"    Inserted bullets after element")
    
    return True


def remove_section_completely(section, soup):
    """Remove a section and its instructions"""
    element = section.get('element')
    if not element:
        return
    
    # Remove the element and following instructions
    remove_instructions_after_element(element)
    
    # Remove the element itself
    try:
        if hasattr(element, 'decompose'):
            element.decompose()
        elif hasattr(element, 'extract'):
            element.extract()
        log_debug(f"    Removed section element")
    except:
        pass


def fuzzy_match_section(ai_name, template_sections):
    """Fuzzy match AI section name to template section"""
    if not template_sections:
        return None, 0
    
    ai_normalized = re.sub(r'\s+', ' ', ai_name.lower().strip())
    ai_normalized = ai_normalized.replace('å', 'a').replace('ä', 'a').replace('ö', 'o')
    
    best_match = None
    best_score = 0
    
    for section in template_sections:
        template_name = section['name']
        template_normalized = re.sub(r'\s+', ' ', template_name.lower().strip())
        template_normalized = template_normalized.replace('å', 'a').replace('ä', 'a').replace('ö', 'o')
        
        # Exact match
        if ai_normalized == template_normalized:
            return section, 100
        
        # Substring match
        if ai_normalized in template_normalized or template_normalized in ai_normalized:
            score = 80
            if score > best_score:
                best_match = section
                best_score = score
        
        # Word overlap
        ai_words = set(ai_normalized.split()) - {'och', 'i', 'på', 'för', 'till', 'av', 'med'}
        template_words = set(template_normalized.split()) - {'och', 'i', 'på', 'för', 'till', 'av', 'med'}
        
        if ai_words and template_words:
            common = ai_words & template_words
            if common:
                score = int((len(common) / max(len(ai_words), len(template_words))) * 70)
                if score > best_score:
                    best_match = section
                    best_score = score
    
    return best_match, best_score


def map_bullets_to_template(template_html, section_bullets_dict, template_structure):
    """
    Main mapping function - inserts AI summaries and removes instructions
    """
    log_separator()
    log_debug("[MAPPER] Starting bullet mapping")
    
    soup = template_structure.get('soup')
    sections = template_structure.get('sections', [])
    
    if not soup:
        soup = BeautifulSoup(template_html, 'html.parser')
    
    if not sections:
        from utils.template_analyzer import extract_all_potential_sections
        sections = extract_all_potential_sections(str(soup))
    
    log_debug(f"[MAPPER] Template sections: {len(sections)}")
    log_debug(f"[MAPPER] AI bullet groups: {len(section_bullets_dict)}")
    
    # Replace metadata
    template_str = str(soup)
    template_str = template_str.replace('[Dagens datum]', datetime.now().strftime('%Y-%m-%d'))
    template_str = template_str.replace('[Förnamn]', '')
    template_str = template_str.replace('[Efternamn]', '')
    template_str = template_str.replace('[Personnummer]', '')
    soup = BeautifulSoup(template_str, 'html.parser')
    
    # Re-detect sections
    from utils.template_analyzer import extract_all_potential_sections
    sections = extract_all_potential_sections(str(soup))
    
    mapped_count = 0
    removed_count = 0
    
    # Map each AI section
    for ai_name, bullets in section_bullets_dict.items():
        log_debug(f"[MAPPER] Processing: '{ai_name}'")
        
        if not bullets:
            continue
        
        # Find matching template section
        matched, score = fuzzy_match_section(ai_name, sections)
        
        if matched and score >= 50:
            log_debug(f"  Matched to: '{matched['name']}' (score: {score})")
            if map_section_with_bullets(matched, bullets, soup):
                mapped_count += 1
                sections.remove(matched)
        else:
            log_debug(f"  No match (best score: {score})")
    
    # Remove unmapped sections
    for section in sections:
        log_debug(f"[MAPPER] Removing empty: '{section['name']}'")
        remove_section_completely(section, soup)
        removed_count += 1
    
    # Cleanup
    html = str(soup)
    html = re.sub(r'(<br\s*/?>\s*){3,}', '<br/><br/>', html)
    html = re.sub(r'\n\s*\n\s*\n+', '\n\n', html)
    
    log_debug(f"[MAPPER] Done: {mapped_count} mapped, {removed_count} removed")
    log_separator()
    
    return html


def remove_instructions_after_element(element):
    """Remove instruction text after an element"""
    if not element:
        return
    
    # Remove next siblings if they're instructions
    next_elem = element.next_sibling
    removed_count = 0
    
    for _ in range(15):  # Check up to 15 siblings (increased from 10)
        if not next_elem:
            break
        
        next_next = next_elem.next_sibling if hasattr(next_elem, 'next_sibling') else None
        should_remove = False
        
        if isinstance(next_elem, NavigableString):
            text = str(next_elem).strip()
            # Remove if it's instruction text or just whitespace
            if is_instruction_text(text) or not text or len(text) < 3:
                should_remove = True
        elif hasattr(next_elem, 'name'):
            if next_elem.name == 'br':
                should_remove = True
            elif next_elem.name in ['span', 'div', 'p']:
                text = next_elem.get_text(strip=True)
                # Remove if contains instruction text
                if is_instruction_text(text):
                    should_remove = True
                # Also check for common instruction patterns
                elif any(keyword in text.lower() for keyword in [
                    'underrubrik:', 'målen som står', 'genomförandeplanen',
                    'samtal/', 'frekvens', 'anpassad studiegång'
                ]):
                    should_remove = True
        
        if should_remove:
            try:
                if hasattr(next_elem, 'decompose'):
                    next_elem.decompose()
                elif hasattr(next_elem, 'extract'):
                    next_elem.extract()
                removed_count += 1
            except:
                pass
        else:
            # If we hit actual content (not instruction), stop
            if hasattr(next_elem, 'name') and next_elem.name in ['ul', 'ol', 'div']:
                break
        
        next_elem = next_next
    
    if removed_count > 0:
        log_debug(f"    Removed {removed_count} instruction elements")