# utils/template_mapper_monthly.py
"""
Template Mapper for Monthly Reports
Maps AI bullets to template and removes instructions
FIXED: Properly removes headers when no content or only placeholder content is available
IMPROVED: Handles all edge cases for header removal
"""

from bs4 import BeautifulSoup, NavigableString, Tag
import re
from datetime import datetime

try:
    from save_logs import log_debug
except:
    def log_debug(msg):
        pass


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


def get_parent_element(element):
    """
    Safely get parent element, handling both Tag and NavigableString
    
    Args:
        element: BeautifulSoup element (Tag or NavigableString)
        
    Returns:
        Parent Tag element or None
    """
    if element is None:
        return None
    
    if isinstance(element, NavigableString):
        return element.parent if hasattr(element, 'parent') else None
    elif isinstance(element, Tag):
        return element.parent if hasattr(element, 'parent') else None
    else:
        return getattr(element, 'parent', None)


def remove_instructions(element):
    """Remove instruction text after element"""
    if not element:
        return
    
    if isinstance(element, (Tag, NavigableString)):
        next_elem = getattr(element, "next_sibling", None)
    else:
        next_elem = None

    removed = 0
    
    for _ in range(15):
        if not next_elem:
            break
        
        next_next = next_elem.next_sibling if hasattr(next_elem, 'next_sibling') else None
        should_remove = False
        
        if isinstance(next_elem, NavigableString):
            text = str(next_elem).strip()
            if not text or text.startswith('('):
                should_remove = True
        elif hasattr(next_elem, 'name'):
            if next_elem.name == 'br':
                should_remove = True
            elif next_elem.name in ['span', 'div']:
                text = next_elem.get_text(strip=True)
                if text.startswith('(') or any(kw in text.lower() for kw in [
                    'underrubrik:', 'målen som står', 'genomförandeplanen',
                    'samtal/', 'frekvens', 'anpassad', 'närvaro', 'dygnsrytm'
                ]):
                    should_remove = True
        
        if should_remove:
            try:
                if hasattr(next_elem, 'decompose'):
                    next_elem.decompose()
                else:
                    next_elem.extract()
                removed += 1
            except:
                pass
        else:
            if hasattr(next_elem, 'name') and next_elem.name in ['ul', 'div']:
                break
        
        next_elem = next_next
    
    if removed > 0:
        log_debug(f"    Removed {removed} instruction elements")


def remove_header_element(element):
    """
    Remove a header element and its container if appropriate
    
    Args:
        element: The header element to remove
        
    Returns:
        bool: True if successfully removed, False otherwise
    """
    try:
        if isinstance(element, NavigableString):
            # Try to get parent container
            parents = list(element.parents) if hasattr(element, 'parents') else []
            if parents:
                parent = parents[0]
                if hasattr(parent, 'decompose'):
                    parent.decompose()
                    return True
                else:
                    element.extract()
                    return True
            else:
                element.extract()
                return True
        else:
            # For <strong>, <b>, <span> headers - remove the container
            if hasattr(element, 'name') and element.name in ['strong', 'b', 'span']:
                # Find the parent container (<p>, <div>, etc.)
                parent_container = element.find_parent(['p', 'div', 'td'])
                
                if parent_container:
                    # Check if parent ONLY contains this header (no other content)
                    parent_text = parent_container.get_text(strip=True)
                    header_text = element.get_text(strip=True)
                    
                    # Also check if parent only contains whitespace, &nbsp;, or nested empty tags
                    parent_html = str(parent_container)
                    parent_content_only = re.sub(r'<[^>]+>', '', parent_html)
                    parent_content_only = parent_content_only.replace('&nbsp;', '').strip()
                    
                    # If parent text matches header text OR parent has no real content
                    if (parent_text == header_text or 
                        len(parent_text) < len(header_text) + 10 or
                        len(parent_content_only) == 0):
                        # Parent mostly contains just the header, safe to remove
                        parent_container.decompose()
                        return True
                    else:
                        # Parent has other content, just remove the header
                        element.decompose()
                        return True
                else:
                    # No parent found, remove element directly
                    element.decompose()
                    return True
            else:
                # Other element types
                if hasattr(element, 'decompose'):
                    element.decompose()
                    return True
        return False
    except Exception as e:
        log_debug(f"  [ERROR] Could not remove header: {e}")
        return False


def replace_metadata_in_soup(soup):
    """Replace metadata placeholders directly in soup object"""
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # Find all text nodes and replace metadata
    for element in soup.find_all(string=True):
        original_text = str(element)
        modified_text = original_text
        
        # Replace metadata
        modified_text = modified_text.replace('[Dagens datum]', current_date)
        modified_text = modified_text.replace('[DAGENS DATUM]', current_date)
        modified_text = modified_text.replace('[Förnamn]', '')
        modified_text = modified_text.replace('[FÖRNAMN]', '')
        modified_text = modified_text.replace('[Efternamn]', '')
        modified_text = modified_text.replace('[EFTERNAMN]', '')
        modified_text = modified_text.replace('[Personnummer]', '')
        modified_text = modified_text.replace('[PERSONNUMMER]', '')
        modified_text = modified_text.replace('[DOKUMENTNAMN]', '')
        
        # Only replace if changed
        if modified_text != original_text:
            element.replace_with(modified_text)
            log_debug(f"[MAPPER] Replaced metadata: {original_text[:50]} -> {modified_text[:50]}")


def map_monthly_bullets(template_html, section_bullets, template_structure):
    """
    Map bullets to monthly template
    FIXED: Properly removes headers for all empty/placeholder cases
    """
    
    log_debug("[MONTHLY_MAPPER] Starting mapping...")
    
    # Get soup from template_structure (already analyzed)
    soup = template_structure.get('soup')
    original_sections = template_structure.get('sections', [])
    
    if not soup:
        soup = BeautifulSoup(template_html, 'html.parser')
    
    log_debug(f"[MONTHLY_MAPPER] Sections: {len(original_sections)}, Bullets: {len(section_bullets)}")
    
    # Replace metadata DIRECTLY in the soup object
    replace_metadata_in_soup(soup)
    
    # NOW re-analyze the SAME soup object to get updated section references
    from utils.template_analyzer_monthly import analyze_monthly_template
    
    # Re-analyze but keep using the SAME soup object
    updated_analysis = analyze_monthly_template(str(soup))
    sections = updated_analysis['sections']
    
    # CRITICAL: Get the soup from updated analysis (this is the SAME object we've been modifying)
    soup = updated_analysis['soup']
    
    log_debug(f"[MONTHLY_MAPPER] After re-analysis: {len(sections)} sections")
    
    mapped = 0
    removed = 0
    
    for section in sections:
        section_name = section['name']
        section_type = section['type']
        
        log_debug(f"[MONTHLY_MAPPER] Processing: {section_name}")
        
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
        
        # ===== FILTER OUT PLACEHOLDER CONTENT =====
        has_real_content = False
        
        if matched_bullets and len(matched_bullets) > 0:
            # Check if bullets contain REAL content (not just placeholders)
            placeholder_texts = [
                '', 'information saknas', 'information saknas i dokumenten', 
                'ingen information', 'no information', 'saknas', 'missing',
                'n/a', 'none', 'nej', 'no'
            ]
            
            original_count = len(matched_bullets)
            real_bullets = []
            for bullet in matched_bullets:
                bullet_text = str(bullet).strip().lower()
                # Keep bullet only if it has real content (not a placeholder)
                if bullet_text and bullet_text not in placeholder_texts:
                    real_bullets.append(bullet)
            
            # If no real content after filtering, treat as empty section
            if len(real_bullets) == 0:
                log_debug(f"  [SKIP] All {original_count} bullets are placeholders - will remove header")
                matched_bullets = None
                has_real_content = False
            else:
                # Use real bullets only
                matched_bullets = real_bullets
                has_real_content = True
                if len(real_bullets) < original_count:
                    log_debug(f"  [FILTERED] {len(real_bullets)} real bullets (removed {original_count - len(real_bullets)} placeholders)")
        
        if has_real_content and matched_bullets and len(matched_bullets) > 0:
            # Map bullets
            element = section['element']
            remove_instructions(element)
            
            # Create bullet list
            bullet_list = create_bullets(matched_bullets, soup)
            
            insertion_success = False
            
            # Insert based on type
            if section_type == 'table':
                content_cell = section.get('content_element')
                if content_cell:
                    content_cell.clear()
                    content_cell.append(bullet_list)
                    insertion_success = True
                    mapped += 1
                    log_debug(f"  [MAPPED] {len(matched_bullets)} bullets (table)")
            else:
                # TEXT TYPE: ROBUST INSERTION
                insert_element = element
                
                if isinstance(element, NavigableString):
                    try:
                        parents = list(element.parents) if hasattr(element, 'parents') else []
                        if parents:
                            insert_element = parents[0]
                            log_debug(f"  [INFO] Using parent {insert_element.name} for NavigableString")
                        else:
                            log_debug(f"  [WARNING] Could not get parent for NavigableString")
                            wrapper = soup.new_tag('div')
                            wrapper['style'] = 'margin:10px 0;'
                            wrapper.append(bullet_list)
                            
                            try:
                                element.replace_with(wrapper)
                                insertion_success = True
                                mapped += 1
                                log_debug(f"  [MAPPED] {len(matched_bullets)} bullets (replaced string)")
                                continue
                            except:
                                log_debug(f"  [SKIP] Could not map bullets")
                                continue
                    except Exception as e:
                        log_debug(f"  [ERROR] Getting parent: {e}")
                        continue
                
                # If element is <strong>/<b> inside <p>, use <p> as insert point
                if hasattr(insert_element, 'name') and insert_element.name in ['strong', 'b']:
                    parent_container = insert_element.find_parent(['p', 'div', 'span'])
                    if parent_container:
                        insert_element = parent_container
                        log_debug(f"  [INFO] Using parent container <{parent_container.name}>")
                
                # Wrap bullets in div
                bullet_div = soup.new_tag('div')
                bullet_div['style'] = 'margin:10px 0 20px 0;'
                bullet_div.append(bullet_list)
                
                # ROBUST INSERTION
                try:
                    parent = insert_element.parent
                    
                    if not parent:
                        log_debug(f"  [ERROR] No parent for insert_element")
                        continue
                    
                    # Get children list
                    children = list(parent.children)
                    
                    try:
                        index = children.index(insert_element)
                    except ValueError:
                        log_debug(f"  [ERROR] Element not in parent's children")
                        continue
                    
                    # Insert at next position
                    parent.insert(index + 1, bullet_div)
                    
                    # VERIFY insertion
                    new_children = list(parent.children)
                    if bullet_div in new_children:
                        insertion_success = True
                        mapped += 1
                        log_debug(f"  [MAPPED] {len(matched_bullets)} bullets - VERIFIED")
                    else:
                        log_debug(f"  [ERROR] Bullets NOT in soup after insertion!")
                        
                        # Fallback: try insert_after
                        try:
                            insert_element.insert_after(bullet_div)
                            verify = list(parent.children)
                            if bullet_div in verify:
                                insertion_success = True
                                mapped += 1
                                log_debug(f"  [MAPPED] {len(matched_bullets)} bullets via insert_after")
                        except Exception as e2:
                            log_debug(f"  [FAILED] Both methods failed: {e2}")
                        
                except Exception as e:
                    log_debug(f"  [ERROR] Insertion error: {e}")
            
            # POST-INSERTION VERIFICATION: If insertion failed, remove the header
            if not insertion_success:
                log_debug(f"  [WARNING] Bullet insertion failed for '{section_name}' - removing header")
                if remove_header_element(element):
                    removed += 1
                    log_debug(f"  [REMOVED] Header removed after insertion failure")

        else:
            # ===== NO CONTENT OR PLACEHOLDER ONLY - REMOVE HEADER =====
            element = section['element']
            remove_instructions(element)
            
            log_debug(f"  [NO_CONTENT] Removing header for '{section_name}'")
            
            try:
                if section_type == 'table':
                    # For table headers, remove the entire row
                    if isinstance(element, NavigableString):
                        log_debug(f"  [SKIP] Cannot remove NavigableString from table")
                    else:
                        row = element.find_parent('tr') if hasattr(element, 'find_parent') else None
                        if row:
                            row.decompose()
                            removed += 1
                            log_debug(f"  [REMOVED] Table row (no content)")
                        elif hasattr(element, 'decompose'):
                            element.decompose()
                            removed += 1
                            log_debug(f"  [REMOVED] Table element (no content)")
                else:
                    # Remove the header element
                    if remove_header_element(element):
                        removed += 1
                        log_debug(f"  [REMOVED] Header (no content/placeholder only)")
                
            except Exception as e:
                log_debug(f"  [WARNING] Could not remove header: {e}")
    
    # NOW convert the soup to HTML string (AFTER all modifications)
    html = str(soup)
    
    # ===== TELERIK-SPECIFIC CLEANUP =====
    log_debug("[CLEANUP] Starting Telerik-specific cleanup...")
    
    # 1. Remove Verdana spans (Telerik metadata)
    html = re.sub(r'<span style="font-family: Verdana; font-size: 8pt;">.*?</span>', '', html, flags=re.DOTALL)
    html = re.sub(r'<span style="font-family: Verdana;">.*?</span>', '', html, flags=re.DOTALL)
    
    # 2. Remove instruction text in parentheses (long instructions)
    html = re.sub(r'\([^)]{100,}\)', '', html)
    
    # 3. Remove specific instruction patterns
    instruction_patterns = [
        r'\(Underrubrik:.*?\)',
        r'\(Målen som står i genomförandeplanen.*?\)',
        r'\(Anhörigintroduktion.*?\)',
        r'\(Samtal/.*?\)',
        r'<span[^>]*>.*?genomförandeplanen.*?</span>',
        r'<span[^>]*>\(.*?planerade\.\)</span>'
    ]
    
    for pattern in instruction_patterns:
        html = re.sub(pattern, '', html, flags=re.DOTALL|re.IGNORECASE)
    
    # 4. Remove empty paragraphs with &nbsp; (Telerik spacers)
    html = re.sub(r'<p[^>]*>\s*&nbsp;\s*</p>', '', html)
    html = re.sub(r'<p[^>]*>&nbsp;</p>', '', html)
    
    # 5. Remove empty paragraphs (various forms)
    html = re.sub(r'<p[^>]*>\s*</p>', '', html)
    
    # 6. Remove paragraphs with only empty strong tags
    html = re.sub(r'<p[^>]*>\s*<strong[^>]*>\s*</strong>\s*</p>', '', html)
    html = re.sub(r'<p[^>]*>\s*<strong[^>]*>&nbsp;</strong>\s*</p>', '', html)
    
    # 7. Remove nested empty strong tags (Telerik sometimes creates these)
    html = re.sub(r'<strong[^>]*>\s*<strong[^>]*>\s*</strong>\s*</strong>', '', html)
    html = re.sub(r'<strong[^>]*>&nbsp;</strong>', '', html)
    html = re.sub(r'<strong[^>]*>\s*</strong>', '', html)
    
    # 8. Remove empty spans
    html = re.sub(r'<span>\s*</span>', '', html)
    html = re.sub(r'<span><br/></span>', '', html)
    html = re.sub(r'<span[^>]*>\s*</span>', '', html)
    html = re.sub(r'<span[^>]*>&nbsp;</span>', '', html)
    
    # 9. Clean up excessive line breaks (from Telerik)
    html = re.sub(r'(<br\s*/?>\s*){3,}', '<br/><br/>', html)
    
    # 10. Clean up excessive newlines in source
    html = re.sub(r'\n\s*\n\s*\n+', '\n\n', html)
    
    # 11. FINAL PASS: Remove any remaining empty paragraphs after all cleanup
    # This catches paragraphs that became empty after other removals
    for _ in range(3):  # Run multiple times to catch nested cases
        html = re.sub(r'<p[^>]*>\s*</p>', '', html)
        html = re.sub(r'<p[^>]*>\s*&nbsp;\s*</p>', '', html)
        html = re.sub(r'<p[^>]*>\s*<strong[^>]*>\s*</strong>\s*</p>', '', html)
    
    log_debug("[CLEANUP] Telerik cleanup completed")
    
    # VERIFY bullets are in final HTML
    if '<ul' in html and '<li' in html:
        bullet_count = html.count('<li')
        log_debug(f"[MONTHLY_MAPPER] ✓ Final HTML contains {bullet_count} <li> tags")
    else:
        log_debug(f"[MONTHLY_MAPPER] ✗ WARNING: Final HTML has NO bullets!")
        log_debug(f"[MONTHLY_MAPPER] HTML preview (first 1500 chars):")
        log_debug(html[:1500])
    
    log_debug(f"[MONTHLY_MAPPER] Done: {mapped} mapped, {removed} removed")
    
    return html