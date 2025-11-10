"""
Template Mapper - IIS Compatible Version - FIXED
Maps AI-generated bullets to template sections
Handles both TABLE-based and TEXT-based templates
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


def create_bullet_html(bullets, soup):
    """Create HTML bullet list from text bullets"""
    ul = soup.new_tag('ul')
    ul['style'] = 'list-style:disc;padding-left:25px;line-height:1.8;margin:10px 0;'
    
    for bullet in bullets:
        # Handle if bullet is a list (nested structure from OpenAI)
        if isinstance(bullet, list):
            # Flatten nested list - join with line breaks
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
    """Map bullets to TEXT-based section - COMPLETE FIX"""
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
    
    # If no valid bullets after filtering, remove section
    if not filtered_bullets:
        log_debug(f"[MAPPER]   No valid content after filtering placeholders")
        return
    
    # Create content div with bullets
    content_div = soup.new_tag('div')
    content_div['style'] = 'margin:15px 0 25px 0;'
    
    bullet_list = create_bullet_html(filtered_bullets, soup)
    content_div.append(bullet_list)
    
    # Find insertion point - MUST be AFTER the header, not inside it
    target_element = None
    
    # Strategy: Insert after the header's parent container
    # Not inside the header element itself
    if header_element:
        # Get the parent that contains the header
        parent_container = header_element.parent
        
        # Find where to insert within the parent's children
        # We want to insert AFTER the header and any following <br> tags
        current = header_element
        next_sibling = header_element.next_sibling
        
        # Skip <br> tags and whitespace
        while next_sibling:
            if hasattr(next_sibling, 'name') and next_sibling.name == 'br':
                current = next_sibling
                next_sibling = next_sibling.next_sibling
            elif isinstance(next_sibling, NavigableString) and not str(next_sibling).strip():
                current = next_sibling
                next_sibling = next_sibling.next_sibling
            else:
                break
        
        target_element = current
    elif instruction_elem:
        target_element = instruction_elem
    elif insert_after:
        target_element = insert_after
    
    # Insert content AFTER target element (not inside it)
    if target_element:
        target_element.insert_after(content_div)
        log_debug(f"[MAPPER]   [SUCCESS] Inserted {len(filtered_bullets)} bullets after header")
    else:
        log_debug(f"[MAPPER]   [ERROR] No target element found for insertion")
        return
    
    # Remove ALL placeholder elements - (AI CONTENT), (...), [...]
    elements_to_remove = []
    
    # Start from the header and look at following siblings
    if header_element:
        check_elem = header_element.next_sibling
        
        while check_elem:
            should_remove = False
            next_check = check_elem.next_sibling
            
            # Stop if we hit the content we just inserted
            if check_elem == content_div:
                break
            
            # Check NavigableString (text nodes)
            if isinstance(check_elem, NavigableString):
                text = str(check_elem).strip()
                # Remove if it's a placeholder pattern
                if text and (text.startswith('(') or text.startswith('[')):
                    should_remove = True
            
            # Check element nodes
            elif hasattr(check_elem, 'get_text'):
                text = check_elem.get_text(strip=True)
                
                # Remove if contains placeholder text
                if text.startswith('(') and text.endswith(')'):
                    should_remove = True
                elif text.startswith('[') and text.endswith(']'):
                    should_remove = True
                elif text == '(AI CONTENT)':
                    should_remove = True
                
                # Stop if we hit another section header
                elif check_elem.name in ['strong', 'h1', 'h2', 'h3', 'h4']:
                    break
                
                # Stop if we hit a <div> with actual content (not our inserted div)
                elif check_elem.name == 'div' and check_elem != content_div:
                    div_text = check_elem.get_text(strip=True)
                    if div_text and not div_text.startswith('(') and not div_text.startswith('['):
                        break
            
            if should_remove:
                elements_to_remove.append(check_elem)
            
            check_elem = next_check
    
    # Remove instruction element if it exists and is separate from header
    if instruction_elem and instruction_elem != header_element and instruction_elem not in elements_to_remove:
        elements_to_remove.append(instruction_elem)
    
    # Execute removal
    for elem in elements_to_remove:
        try:
            if hasattr(elem, 'decompose'):
                elem.decompose()
            elif hasattr(elem, 'extract'):
                elem.extract()
        except Exception as e:
            log_debug(f"[MAPPER]   Error removing element: {e}")



def remove_table_section(section, soup):
    """Remove entire table row for empty sections"""
    header_cell = section.get('header_element')
    
    if not header_cell:
        return
    
    # Find the parent row
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
    
    # Collect all elements to remove
    elements_to_remove = []
    
    # Always remove the header element
    elements_to_remove.append(header_element)
    
    # Remove instruction element if it exists separately
    if instruction_elem and instruction_elem != header_element:
        elements_to_remove.append(instruction_elem)
    
    # Look for and remove trailing <br> tags and empty text nodes
    # We need to look both before and after the header for cleanup
    current = header_element
    elements_checked = 0
    max_elements_to_check = 10
    
    # Check previous siblings for leading <br> tags
    prev_elem = header_element.previous_sibling
    while prev_elem and elements_checked < max_elements_to_check:
        elements_checked += 1
        if (hasattr(prev_elem, 'name') and prev_elem.name == 'br') or \
           (isinstance(prev_elem, NavigableString) and not str(prev_elem).strip()):
            elements_to_remove.append(prev_elem)
        else:
            break
        prev_elem = prev_elem.previous_sibling if prev_elem.previous_sibling else None
    
    # Check next siblings for trailing <br> tags and empty content
    next_elem = header_element.next_sibling
    while next_elem and elements_checked < max_elements_to_check:
        elements_checked += 1
        next_next = next_elem.next_sibling
        
        if (hasattr(next_elem, 'name') and next_elem.name == 'br') or \
           (isinstance(next_elem, NavigableString) and not str(next_elem).strip()):
            elements_to_remove.append(next_elem)
        elif hasattr(next_elem, 'name') and next_elem.name in ['div', 'ul', 'ol']:
            # If we hit actual content elements, stop
            break
        else:
            # For other elements, check if they're empty or instructional
            if hasattr(next_elem, 'get_text'):
                text_content = next_elem.get_text(strip=True)
                if not text_content or any(keyword in text_content.lower() for keyword in ['sammanställning', 'kortbeskrivning', 'beskrivning']):
                    elements_to_remove.append(next_elem)
                else:
                    break
            else:
                break
        
        next_elem = next_next
    
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
            log_debug(f"[MAPPER]     Error removing element: {e}")
            continue
    
    log_debug(f"[MAPPER]     Removed {removed_count} elements for section: {header_text[:30]}")


def clean_up_html_spacing(html_content):
    """Clean up excessive spacing and line breaks in HTML"""
    
    # First pass: remove multiple consecutive <br/> tags
    html_content = re.sub(r'(<br\s*/?>\s*){2,}', '<br/><br/>', html_content)
    
    # Remove <br/> tags that are alone between sections
    html_content = re.sub(r'</div>\s*(<br\s*/?>\s*){1,}<div', '</div><div', html_content)
    
    # Remove <br/> tags immediately before closing div
    html_content = re.sub(r'(<br\s*/?>\s*)+</div>', '</div>', html_content)
    
    # Remove <br/> tags immediately after opening div
    html_content = re.sub(r'<div[^>]*>(\s*<br\s*/?>\s*)+', '<div style="width:650px;">', html_content)
    
    # Clean up the specific case where we have empty sections
    html_content = re.sub(r'<font face="Times New Roman" size="3">[^<]*<br/>\s*<span[^>]*>\([^<]*</span>\s*</font>\s*</div>', '</div>', html_content)
    
    # Remove empty font tags with just spaces
    html_content = re.sub(r'<font[^>]*>\s*</font>', '', html_content)
    
    # Clean up multiple blank lines
    html_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', html_content)
    
    return html_content


def map_bullets_to_template(template_html, section_bullets_dict, template_structure):
    """
    Main mapping function - inserts bullets into template
    
    IMPROVED LOGIC:
    1. For matched sections → insert bullets directly
    2. For unmatched sections → they should have been handled by generate_content_for_unmapped_sections()
    3. Sections with no content → remove from template
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
    
    # Debug: print all sections found
    for i, section in enumerate(sections):
        header_text = section.get('header_element').get_text(strip=True) if section.get('header_element') else 'No header'
        log_debug(f"[MAPPER] Section {i+1}: '{header_text}'")
    
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
    
    # Define placeholder texts
    placeholder_texts = ['', 'information saknas', 'information missing', 
                        'ingen information', 'no information', 'saknas', 'missing',
                        'n/a', 'none', 'nej', 'no']
    
    for section in sections:
        section_name = section['name']
        section_type = section['type']
        
        log_debug(f"[MAPPER] Processing section: '{section_name}'")
        
        # Normalize section name for matching
        section_normalized = re.sub(r'\s+', ' ', section_name.lower().strip())
        
        # Find matching bullets - try multiple matching strategies
        matched_bullets = None
        
        # Strategy 1: Exact match with normalized names
        for bullet_key, bullets in section_bullets_dict.items():
            bullet_normalized = re.sub(r'\s+', ' ', bullet_key.lower().strip())
            if section_normalized == bullet_normalized:
                matched_bullets = bullets
                log_debug(f"[MAPPER]   Found exact match: '{bullet_key}'")
                break
        
        # Strategy 2: Direct key access
        if not matched_bullets:
            matched_bullets = section_bullets_dict.get(section_name)
            if matched_bullets:
                log_debug(f"[MAPPER]   Found direct key match")
        
        # Strategy 3: Partial match
        if not matched_bullets:
            for bullet_key, bullets in section_bullets_dict.items():
                if section_normalized in bullet_key.lower() or bullet_key.lower() in section_normalized:
                    matched_bullets = bullets
                    log_debug(f"[MAPPER]   Found partial match: '{bullet_key}'")
                    break
        
        # Check if we have valid content
        has_content = False
        if matched_bullets:
            log_debug(f"[MAPPER]   Checking {len(matched_bullets)} bullets for content")
            for bullet in matched_bullets:
                bullet_text = str(bullet).strip()
                if bullet_text and bullet_text.lower() not in placeholder_texts:
                    has_content = True
                    log_debug(f"[MAPPER]   Found content: {bullet_text[:50]}...")
                    break
        
        if has_content:
            # Section has content - map it
            if section_type == 'table':
                map_table_section(section, matched_bullets, soup)
            else:
                map_text_section(section, matched_bullets, soup)
            
            mapped_count += 1
            log_debug(f"[MAPPER]   [MAPPED] '{section_name}' with {len(matched_bullets)} bullets")
        else:
            # No content - remove the section
            if section_type == 'table':
                remove_table_section(section, soup)
            else:
                remove_text_section(section, soup)
            
            removed_count += 1
            log_debug(f"[MAPPER]   [REMOVED] '{section_name}' - no content")
    
    # Final cleanup
    clean_html = str(soup)
    clean_html = clean_up_html_spacing(clean_html)
    
    log_debug(f"[MAPPER] Completed: {mapped_count} mapped, {removed_count} removed")
    log_separator()
    
    return clean_html