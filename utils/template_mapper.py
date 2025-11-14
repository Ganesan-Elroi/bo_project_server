"""
Template Mapper - FINAL VERSION
Maps AI-generated bullets to template sections
Removes ANY placeholder text in (...) or [...]
"""

from bs4 import BeautifulSoup, NavigableString
import re
from datetime import datetime

try:
    from save_logs import log_debug, log_separator
    LOGGING_ENABLED = True
except:
    LOGGING_ENABLED = False
    def log_debug(msg):
        pass
    def log_separator(char='=', length=70):
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


def create_bullet_html(bullets, soup):
    """Create HTML bullet list from text bullets"""
    ul = soup.new_tag('ul')
    ul['style'] = 'list-style:disc;padding-left:25px;line-height:1.8;margin:10px 0;'
    
    for bullet in bullets:
        # Handle if bullet is a list (nested structure from OpenAI)
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


def map_table_section(section, section_bullets, soup):
    """Map bullets to TABLE-based section"""
    content_cell = section.get('content_element')
    
    if not content_cell or not section_bullets:
        return
    
    # Clear existing placeholder content
    content_cell.clear()
    
    # Create and insert bullet list
    bullet_list = create_bullet_html(section_bullets, soup)
    content_cell.append(bullet_list)
    
    log_debug(f"[MAPPER]   [SUCCESS] Mapped table section")


def map_text_section(section, section_bullets, soup):
    """Map bullets to TEXT-based section - FINAL VERSION"""
    insert_after = section.get('insert_after')
    instruction_elem = section.get('instruction_element')
    header_element = section.get('header_element')
    
    if not section_bullets:
        return
    
    # Filter out placeholder bullets
    placeholder_texts = ['information saknas', 'information missing', 
                        'ingen information', 'no information', 'saknas', 'missing',
                        'n/a', 'none', 'nej', 'no']
    
    filtered_bullets = []
    for bullet in section_bullets:
        bullet_text = str(bullet).strip().lower()
        if bullet_text and bullet_text not in placeholder_texts:
            filtered_bullets.append(bullet)
    
    if not filtered_bullets:
        log_debug(f"[MAPPER]   No valid content after filtering")
        return
    
    # Create content div
    content_div = soup.new_tag('div')
    content_div['style'] = 'margin:15px 0 25px 0;'
    
    bullet_list = create_bullet_html(filtered_bullets, soup)
    content_div.append(bullet_list)
    
    # Find the outermost parent container of the header
    # We want to insert AFTER this container, not inside it
    parent_container = header_element.parent
    
    # FIXED: Check if parent_container is the root BeautifulSoup object
    # If so, use the header_element itself as the insertion point
    from bs4 import BeautifulSoup as BS4
    if isinstance(parent_container, BS4):
        # Parent is the root document, insert after header_element directly
        header_element.insert_after(content_div)
        log_debug(f"[MAPPER]   Inserted {len(filtered_bullets)} bullets after header (parent is root)")
        search_start = header_element
    elif parent_container:
        # Normal case: parent is a Tag element
        parent_container.insert_after(content_div)
        log_debug(f"[MAPPER]   Inserted {len(filtered_bullets)} bullets after parent container")
        search_start = parent_container
    else:
        # Fallback: no parent found
        header_element.insert_after(content_div)
        log_debug(f"[MAPPER]   Inserted {len(filtered_bullets)} bullets after header (no parent)")
        search_start = header_element
    
    # Remove ALL placeholder elements after the insertion point
    # Placeholders are ANY text matching (...) or [...]
    elements_to_remove = []
    check_elem = search_start.next_sibling
    checked_count = 0
    max_check = 20  # Safety limit
    
    while check_elem and checked_count < max_check:
        checked_count += 1
        next_check = check_elem.next_sibling
        should_remove = False
        
        # Skip our inserted content
        if check_elem == content_div:
            check_elem = next_check
            continue
        
        # Check NavigableString (text nodes)
        if isinstance(check_elem, NavigableString):
            text = str(check_elem).strip()
            if text and is_placeholder_text(text):
                should_remove = True
                log_debug(f"[MAPPER]     Found placeholder text: {text[:50]}")
        
        # Check element nodes
        elif hasattr(check_elem, 'get_text'):
            text = check_elem.get_text(strip=True)
            
            # Stop if we hit another section header
            if check_elem.name == 'strong':
                if text and len(text) > 3 and text.isupper():
                    log_debug(f"[MAPPER]     Stopping at next section: {text}")
                    break
            
            # Check if this is a <p> or <div> with ANOTHER section header inside
            if check_elem.name in ['p', 'div']:
                # Look for strong tags inside
                inner_strong = check_elem.find('strong')
                if inner_strong:
                    inner_text = inner_strong.get_text(strip=True)
                    if inner_text and len(inner_text) > 3 and inner_text.isupper():
                        log_debug(f"[MAPPER]     Stopping at container with next section: {inner_text}")
                        break
            
            # Check if entire element is a placeholder
            if text and is_placeholder_text(text):
                should_remove = True
                log_debug(f"[MAPPER]     Found placeholder element: {text[:30]}")
            
            # Special handling for divs and paragraphs
            elif check_elem.name in ['div', 'p']:
                # Count how many descendants have real content vs placeholders
                has_real_content = False
                has_placeholder_content = False
                
                # Check all text descendants
                for desc in check_elem.descendants:
                    if isinstance(desc, NavigableString):
                        desc_text = str(desc).strip()
                        if desc_text:
                            if is_placeholder_text(desc_text):
                                has_placeholder_content = True
                            elif len(desc_text) > 5:  # Significant text
                                has_real_content = True
                                break
                    elif hasattr(desc, 'name') and desc.name == 'strong':
                        # Check if it's a section header
                        desc_text = desc.get_text(strip=True)
                        if desc_text and desc_text.isupper() and len(desc_text) > 3:
                            has_real_content = True
                            break
                
                # Remove if it only has placeholder content
                if has_placeholder_content and not has_real_content:
                    should_remove = True
                    log_debug(f"[MAPPER]     Container has only placeholders: {text[:30]}")
                elif has_real_content:
                    # This element has real content, stop searching
                    log_debug(f"[MAPPER]     Stopping at real content container")
                    break
        
        if should_remove:
            elements_to_remove.append(check_elem)
        
        check_elem = next_check
    
    # Remove all collected placeholder elements
    removed_count = 0
    for elem in elements_to_remove:
        try:
            if hasattr(elem, 'decompose'):
                elem.decompose()
                removed_count += 1
            elif hasattr(elem, 'extract'):
                elem.extract()
                removed_count += 1
        except Exception as e:
            log_debug(f"[MAPPER]     Error removing: {e}")
    
    log_debug(f"[MAPPER]   [SUCCESS] Removed {removed_count} placeholder elements")

def remove_table_section(section, soup):
    """Remove entire table row for empty sections"""
    header_cell = section.get('header_element')
    
    if not header_cell:
        return
    
    parent_row = header_cell.find_parent('tr')
    
    if parent_row:
        parent_row.decompose()
        log_debug(f"[MAPPER]     Removed table row")


def remove_text_section(section, soup):
    """Remove header, instruction, and surrounding elements for empty text sections"""
    header_element = section.get('header_element')
    instruction_elem = section.get('instruction_element')
    
    if not header_element:
        return
    
    header_text = header_element.get_text(strip=True) if header_element.get_text(strip=True) else 'Empty header'
    log_debug(f"[MAPPER]     Removing text section: {header_text[:50]}")
    
    elements_to_remove = []
    
    # Remove the parent container of the header
    parent = header_element.parent
    if parent:
        elements_to_remove.append(parent)
    else:
        elements_to_remove.append(header_element)
    
    # Look for following placeholder elements
    search_start = parent if parent else header_element
    check_elem = search_start.next_sibling
    checked_count = 0
    
    while check_elem and checked_count < 10:
        checked_count += 1
        next_check = check_elem.next_sibling
        
        if isinstance(check_elem, NavigableString):
            text = str(check_elem).strip()
            if not text or is_placeholder_text(text):
                elements_to_remove.append(check_elem)
        elif hasattr(check_elem, 'get_text'):
            text = check_elem.get_text(strip=True)
            if not text or is_placeholder_text(text):
                elements_to_remove.append(check_elem)
            elif check_elem.name in ['strong', 'h1', 'h2']:
                break
        
        check_elem = next_check
    
    # Remove all collected elements
    removed_count = 0
    for elem in elements_to_remove:
        try:
            if hasattr(elem, 'decompose'):
                elem.decompose()
                removed_count += 1
            elif hasattr(elem, 'extract'):
                elem.extract()
                removed_count += 1
        except Exception as e:
            log_debug(f"[MAPPER]     Error: {e}")
    
    log_debug(f"[MAPPER]     Removed {removed_count} elements")


def clean_up_html_spacing(html_content):
    """Clean up excessive spacing and line breaks in HTML"""
    
    # Remove multiple consecutive <br/> tags
    html_content = re.sub(r'(<br\s*/?>\s*){3,}', '<br/><br/>', html_content)
    
    # Remove <br/> between sections
    html_content = re.sub(r'</div>\s*(<br\s*/?>\s*)+<div', '</div><div', html_content)
    
    # Remove <br/> before closing div
    html_content = re.sub(r'(<br\s*/?>\s*)+</div>', '</div>', html_content)
    
    # Remove empty divs
    html_content = re.sub(r'<div[^>]*>\s*</div>', '', html_content)
    
    # Clean up empty spans
    html_content = re.sub(r'<span[^>]*>\s*</span>', '', html_content)
    
    # Clean up multiple blank lines
    html_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', html_content)
    
    return html_content


def map_bullets_to_template(template_html, section_bullets_dict, template_structure):
    """
    Main mapping function - inserts bullets into template and removes placeholders
    """
    log_separator()
    log_debug("[MAPPER] Starting bullet mapping")
    
    soup = template_structure.get('soup')
    sections = template_structure.get('sections', [])
    template_type = template_structure.get('template_type', 'unknown')
    
    if not soup:
        soup = BeautifulSoup(template_html, 'html.parser')
    
    log_debug(f"[MAPPER] Template type: {template_type}")
    log_debug(f"[MAPPER] Detected sections: {len(sections)}")
    log_debug(f"[MAPPER] Bullet groups received: {len(section_bullets_dict)}")
    
    # Replace metadata placeholders
    template_str = str(soup)
    template_str = template_str.replace('[Dagens datum]', datetime.now().strftime('%Y-%m-%d'))
    template_str = template_str.replace('[Förnamn]', '')
    template_str = template_str.replace('[Efternamn]', '')
    template_str = template_str.replace('[Personnummer]', '')
    
    soup = BeautifulSoup(template_str, 'html.parser')
    
    # Re-detect sections after soup recreation
    if template_type == 'table':
        from utils.template_analyzer import detect_table_based_sections
        sections = detect_table_based_sections(soup)
    elif template_type == 'text':
        from utils.template_analyzer import detect_text_based_sections
        sections = detect_text_based_sections(soup)
    
    # Map each section
    mapped_count = 0
    removed_count = 0
    
    for section in sections:
        section_name = section['name']
        section_type = section['type']
        
        log_debug(f"[MAPPER] Processing section: '{section_name}'")
        
        # Find matching bullets
        matched_bullets = None
        section_normalized = re.sub(r'\s+', ' ', section_name.lower().strip())
        
        # Try exact match
        for bullet_key, bullets in section_bullets_dict.items():
            bullet_normalized = re.sub(r'\s+', ' ', bullet_key.lower().strip())
            if section_normalized == bullet_normalized:
                matched_bullets = bullets
                log_debug(f"[MAPPER]   Found exact match: '{bullet_key}'")
                break
        
        # Try direct key access
        if not matched_bullets:
            matched_bullets = section_bullets_dict.get(section_name)
            if matched_bullets:
                log_debug(f"[MAPPER]   Found direct match")
        
        # Try partial match
        if not matched_bullets:
            for bullet_key, bullets in section_bullets_dict.items():
                if section_normalized in bullet_key.lower() or bullet_key.lower() in section_normalized:
                    matched_bullets = bullets
                    log_debug(f"[MAPPER]   Found partial match: '{bullet_key}'")
                    break
        
        # Check if we have valid content
        has_content = False
        if matched_bullets:
            placeholder_texts = ['', 'information saknas', 'information missing', 
                               'ingen information', 'no information', 'saknas', 'missing',
                               'n/a', 'none', 'nej', 'no']
            
            for bullet in matched_bullets:
                bullet_text = str(bullet).strip().lower()
                if bullet_text and bullet_text not in placeholder_texts:
                    has_content = True
                    break

        
        if has_content:
            # Map the section with content
            if section_type == 'table':
                map_table_section(section, matched_bullets, soup)
            else:
                map_text_section(section, matched_bullets, soup)
            mapped_count += 1
            log_debug(f"[MAPPER]   [MAPPED] '{section_name}'")

        else:
            # No content - remove the section
            if section_type == 'table':
                remove_table_section(section, soup)
            else:
                remove_text_section(section, soup)
            
            removed_count += 1
            log_debug(f"[MAPPER]   [REMOVED] '{section_name}'")
    
    # Final cleanup
    clean_html = str(soup)
    clean_html = clean_up_html_spacing(clean_html)
    
    log_debug(f"[MAPPER] Completed: {mapped_count} mapped, {removed_count} removed")
    log_separator()
    
    return clean_html