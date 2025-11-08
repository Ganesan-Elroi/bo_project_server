"""
Template Mapper - ENHANCED VERSION
Maps AI-generated bullets to template sections with:
- Fuzzy matching for section names
- Automatic instruction text removal
- Flexible template support
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


def remove_instruction_text(element):
    """
    Remove instruction text (content in parentheses) near an element
    """
    if not element:
        return
    
    # Check next siblings for instruction text
    next_elem = element.next_sibling
    elements_to_remove = []
    
    for _ in range(5):  # Check up to 5 next siblings
        if not next_elem:
            break
            
        if isinstance(next_elem, NavigableString):
            text = str(next_elem).strip()
            if text.startswith('(') and text.endswith(')'):
                elements_to_remove.append(next_elem)
        elif hasattr(next_elem, 'get_text'):
            text = next_elem.get_text(strip=True)
            if text.startswith('(') and text.endswith(')'):
                elements_to_remove.append(next_elem)
        
        next_elem = next_elem.next_sibling if hasattr(next_elem, 'next_sibling') else None
    
    # Remove collected instruction elements
    for elem in elements_to_remove:
        if hasattr(elem, 'decompose'):
            elem.decompose()
        elif hasattr(elem, 'extract'):
            elem.extract()
        log_debug(f"[MAPPER]     Removed instruction text")


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
    """Map bullets to TEXT-based section with instruction removal"""
    header_element = section.get('element')
    
    if not header_element or not section_bullets:
        return
    
    # Remove instruction text after header
    remove_instruction_text(header_element)
    
    # Create content div
    content_div = soup.new_tag('div')
    content_div['style'] = 'margin:15px 0 25px 0;'
    
    bullet_list = create_bullet_html(section_bullets, soup)
    content_div.append(bullet_list)
    
    # Insert after header
    header_element.insert_after(content_div)
    
    log_debug(f"[MAPPER]   [SUCCESS] Mapped text section")


def remove_table_section(section, soup):
    """Remove entire table row for empty sections"""
    header_cell = section.get('element')
    
    if not header_cell:
        return
    
    # Find the parent row
    parent_row = header_cell.find_parent('tr')
    
    if parent_row:
        parent_row.decompose()
        log_debug(f"[MAPPER]     Removed table row")


def remove_text_section(section, soup):
    """Remove header, instruction, and surrounding elements for empty text sections"""
    header_element = section.get('element')
    
    if not header_element:
        return
    
    header_text = header_element.get_text(strip=True)
    log_debug(f"[MAPPER]     Removing text section: {header_text[:50]}")
    
    # Collect all elements to remove
    elements_to_remove = [header_element]
    
    # Remove instruction text
    next_elem = header_element.next_sibling
    for _ in range(5):
        if not next_elem:
            break
            
        next_next = next_elem.next_sibling if hasattr(next_elem, 'next_sibling') else None
        
        if isinstance(next_elem, NavigableString):
            text = str(next_elem).strip()
            if not text or text.startswith('('):
                elements_to_remove.append(next_elem)
            else:
                break
        elif hasattr(next_elem, 'get_text'):
            text = next_elem.get_text(strip=True)
            if not text or text.startswith('(') or next_elem.name == 'br':
                elements_to_remove.append(next_elem)
            else:
                break
        else:
            break
        
        next_elem = next_next
    
    # Remove all collected elements
    for elem in elements_to_remove:
        try:
            if hasattr(elem, 'decompose'):
                elem.decompose()
            elif hasattr(elem, 'extract'):
                elem.extract()
        except:
            pass
    
    log_debug(f"[MAPPER]     Removed {len(elements_to_remove)} elements")


def fuzzy_match_section(ai_section_name, template_sections):
    """
    Fuzzy match AI-generated section name to template section
    Handles Swedish characters, spacing, and partial matches
    
    Returns:
        tuple: (matched_section, match_score)
    """
    if not template_sections:
        return None, 0
    
    ai_normalized = re.sub(r'\s+', ' ', ai_section_name.lower().strip())
    # Normalize Swedish characters for matching
    ai_normalized = ai_normalized.replace('å', 'a').replace('ä', 'a').replace('ö', 'o')
    ai_normalized = ai_normalized.replace('é', 'e').replace('è', 'e')
    
    best_match = None
    best_score = 0
    
    for template_section in template_sections:
        template_name = template_section['name']
        template_normalized = re.sub(r'\s+', ' ', template_name.lower().strip())
        template_normalized = template_normalized.replace('å', 'a').replace('ä', 'a').replace('ö', 'o')
        template_normalized = template_normalized.replace('é', 'e').replace('è', 'e')
        
        # Strategy 1: Exact match (100 points)
        if ai_normalized == template_normalized:
            return template_section, 100
        
        # Strategy 2: One contains the other (80 points)
        if ai_normalized in template_normalized:
            score = 80
            if score > best_score:
                best_match = template_section
                best_score = score
        elif template_normalized in ai_normalized:
            score = 75
            if score > best_score:
                best_match = template_section
                best_score = score
        
        # Strategy 3: Word overlap (0-70 points)
        ai_words = set(ai_normalized.split())
        template_words = set(template_normalized.split())
        
        # Remove common filler words
        filler_words = {'och', 'eller', 'i', 'på', 'för', 'till', 'av', 'med', 'om', 'från', 'den', 'det', 'en', 'ett'}
        ai_words = ai_words - filler_words
        template_words = template_words - filler_words
        
        if ai_words and template_words:
            common_words = ai_words & template_words
            if len(common_words) > 0:
                overlap_ratio = len(common_words) / max(len(ai_words), len(template_words))
                score = int(overlap_ratio * 70)
                if score > best_score:
                    best_match = template_section
                    best_score = score
    
    return best_match, best_score


def clean_up_html_spacing(html_content):
    """Clean up excessive spacing and line breaks in HTML"""
    
    # Remove multiple consecutive <br/> tags
    html_content = re.sub(r'(<br\s*/?>\s*){3,}', '<br/><br/>', html_content)
    
    # Remove <br/> tags between sections
    html_content = re.sub(r'</div>\s*(<br\s*/?>\s*)+<div', '</div><div', html_content)
    html_content = re.sub(r'</ul>\s*(<br\s*/?>\s*)+<', '</ul><', html_content)
    
    # Remove <br/> before closing tags
    html_content = re.sub(r'(<br\s*/?>\s*)+</div>', '</div>', html_content)
    html_content = re.sub(r'(<br\s*/?>\s*)+</td>', '</td>', html_content)
    
    # Remove <br/> after opening tags
    html_content = re.sub(r'<div[^>]*>(\s*<br\s*/?>\s*)+', '<div>', html_content)
    html_content = re.sub(r'<td[^>]*>(\s*<br\s*/?>\s*)+', '<td>', html_content)
    
    # Clean up multiple blank lines
    html_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', html_content)
    
    return html_content


def map_bullets_to_template(template_html, section_bullets_dict, template_structure):
    """
    Main mapping function - ENHANCED VERSION
    - Supports fuzzy matching
    - Removes instruction text
    - Handles flexible templates
    """
    log_separator()
    log_debug("[MAPPER] Starting enhanced bullet mapping")
    
    soup = template_structure.get('soup')
    sections = template_structure.get('sections', [])
    template_type = template_structure.get('template_type', 'unknown')
    
    # If no sections detected, try enhanced detection
    if not sections:
        log_debug("[MAPPER] No sections found, trying enhanced detection...")
        from utils.template_analyzer import extract_all_potential_sections
        sections = extract_all_potential_sections(template_html)
        log_debug(f"[MAPPER] Enhanced detection found {len(sections)} sections")
    
    if not soup:
        soup = BeautifulSoup(template_html, 'html.parser')
    
    log_debug(f"[MAPPER] Template type: {template_type}")
    log_debug(f"[MAPPER] Template sections: {len(sections)}")
    log_debug(f"[MAPPER] AI bullet groups: {len(section_bullets_dict)}")
    
    # Replace metadata placeholders
    template_str = str(soup)
    template_str = template_str.replace('[Dagens datum]', datetime.now().strftime('%Y-%m-%d'))
    template_str = template_str.replace('[Förnamn]', '')
    template_str = template_str.replace('[Efternamn]', '')
    template_str = template_str.replace('[Personnummer]', '')
    
    soup = BeautifulSoup(template_str, 'html.parser')
    
    # Re-detect sections after soup recreation
    if sections:
        from utils.template_analyzer import extract_all_potential_sections
        sections = extract_all_potential_sections(str(soup))
    
    mapped_count = 0
    removed_count = 0
    unmatched_ai_sections = []
    
    # Process each AI-generated section
    for ai_section_name, bullets in section_bullets_dict.items():
        log_debug(f"[MAPPER] Processing AI section: '{ai_section_name}'")
        
        # Validate bullets
        if not bullets or len(bullets) == 0:
            log_debug(f"[MAPPER]   Skipping - no bullets")
            continue
        
        # Find best matching template section using fuzzy matching
        matched_section, match_score = fuzzy_match_section(ai_section_name, sections)
        
        if matched_section and match_score >= 50:  # 50% threshold
            log_debug(f"[MAPPER]   Matched to: '{matched_section['name']}' (score: {match_score})")
            
            # Map bullets to template
            section_type = matched_section.get('type', 'text')
            
            if section_type == 'table_header':
                map_table_section(matched_section, bullets, soup)
            else:
                map_text_section(matched_section, bullets, soup)
            
            mapped_count += 1
            sections.remove(matched_section)  # Remove to avoid duplicate mapping
            
        else:
            log_debug(f"[MAPPER]   No match found (best score: {match_score})")
            unmatched_ai_sections.append(ai_section_name)
    
    # Remove unmapped template sections (sections with no content)
    for section in sections:
        section_name = section.get('name', 'Unknown')
        section_type = section.get('type', 'text')
        
        log_debug(f"[MAPPER] Removing empty section: '{section_name}'")
        
        if section_type == 'table_header':
            remove_table_section(section, soup)
        else:
            remove_text_section(section, soup)
        
        removed_count += 1
    
    # If there are unmatched AI sections and template had no/few sections,
    # append them as new sections
    if unmatched_ai_sections and len(template_structure.get('sections', [])) < 3:
        log_debug(f"[MAPPER] Template has few sections, appending {len(unmatched_ai_sections)} unmatched AI sections")
        
        # Find main content area
        main_div = soup.find('div', style=lambda s: s and 'width:650px' in s)
        if not main_div:
            main_div = soup.find('div')
        
        if main_div:
            for ai_section_name in unmatched_ai_sections:
                bullets = section_bullets_dict.get(ai_section_name, [])
                if bullets:
                    # Create section header
                    section_header = soup.new_tag('h3')
                    section_header.string = ai_section_name
                    section_header['style'] = 'font-family: Times New Roman; margin-top: 20px;'
                    
                    # Create bullet list
                    bullet_list = create_bullet_html(bullets, soup)
                    
                    # Append to main div
                    main_div.append(section_header)
                    main_div.append(bullet_list)
                    
                    mapped_count += 1
                    log_debug(f"[MAPPER]   Appended new section: '{ai_section_name}'")
    
    # Final cleanup
    clean_html = str(soup)
    clean_html = clean_up_html_spacing(clean_html)
    
    log_debug(f"[MAPPER] Completed: {mapped_count} mapped, {removed_count} removed")
    log_separator()
    
    return clean_html