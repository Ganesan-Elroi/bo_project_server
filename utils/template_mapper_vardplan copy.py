# utils/template_mapper_vardplan.py
"""
Template Mapper for Vårdplan
Maps AI-generated bullets to vårdplan template
FIXED: Now properly inserts bullets for ALL sections, not just the last one
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
            elif next_elem.name in ['span', 'div', 'p']:
                text = next_elem.get_text(strip=True)
                if text.startswith('(') or len(text) > 100:
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


def replace_metadata_in_soup(soup):
    """Replace metadata placeholders directly in soup object"""
    current_date = datetime.now().strftime('%Y-%m-%d')
    
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
        modified_text = modified_text.replace('[Namn]', '')
        modified_text = modified_text.replace('[NAMN]', '')
        
        if modified_text != original_text:
            element.replace_with(modified_text)
            log_debug(f"[MAPPER] Replaced metadata: {original_text[:50]} -> {modified_text[:50]}")


def map_vardplan_bullets(template_html, section_bullets, template_structure):
    """
    Map bullets to vårdplan template
    FIXED: Now properly inserts bullets for ALL sections
    
    Args:
        template_html: Original template HTML
        section_bullets: Dict of {section_name: [bullets]}
        template_structure: Output from analyze_vardplan_template()
        
    Returns:
        str: Final HTML with bullets mapped
    """
    
    log_debug("[VARDPLAN_MAPPER] Starting mapping...")
    
    soup = template_structure.get('soup')
    original_sections = template_structure.get('sections', [])
    
    if not soup:
        soup = BeautifulSoup(template_html, 'html.parser')
    
    log_debug(f"[VARDPLAN_MAPPER] Sections: {len(original_sections)}, Bullets: {len(section_bullets)}")
    
    # Replace metadata DIRECTLY in soup object
    replace_metadata_in_soup(soup)
    
    # Re-analyze to get updated section references
    from utils.template_analyzer_vardplan import analyze_vardplan_template
    
    updated_analysis = analyze_vardplan_template(str(soup))
    sections = updated_analysis['sections']
    soup = updated_analysis['soup']
    
    log_debug(f"[VARDPLAN_MAPPER] After re-analysis: {len(sections)} sections")
    
    mapped = 0
    removed = 0
    
    # CRITICAL FIX: Process each section individually and insert bullets immediately
    for section in sections:
        section_name = section['name']
        section_type = section['type']
        
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
        
        if matched_bullets and len(matched_bullets) > 0:
            element = section['element']
            remove_instructions(element)
            
            # Create bullet list
            bullet_list = create_bullets(matched_bullets, soup)
            
            if section_type == 'table':
                # TABLE TYPE - Insert into cell
                content_cell = section.get('content_element')
                if content_cell:
                    # CRITICAL: Find the section header element in the cell
                    # Then insert bullets AFTER it, not replace entire cell
                    
                    # Find where to insert (after the header element)
                    insert_point = element
                    
                    # If element is inside a span, get the parent span
                    if element.parent and element.parent.name == 'span':
                        insert_point = element.parent
                    
                    # Create a wrapper div for bullets
                    bullet_wrapper = soup.new_tag('div')
                    bullet_wrapper['style'] = 'margin:10px 0;'
                    bullet_wrapper.append(bullet_list)
                    
                    # Insert bullets after the header
                    try:
                        insert_point.insert_after(bullet_wrapper)
                        mapped += 1
                        log_debug(f"  [MAPPED] {len(matched_bullets)} bullets (table) - AFTER header")
                    except Exception as e:
                        log_debug(f"  [ERROR] Could not insert bullets: {e}")
                        # Fallback: append to cell
                        try:
                            content_cell.append(bullet_wrapper)
                            mapped += 1
                            log_debug(f"  [MAPPED] {len(matched_bullets)} bullets (table) - APPENDED")
                        except Exception as e2:
                            log_debug(f"  [ERROR] Fallback failed: {e2}")
            else:
                # TEXT TYPE - Insert after element
                insert_element = element
                
                if isinstance(element, NavigableString):
                    try:
                        parents = list(element.parents) if hasattr(element, 'parents') else []
                        if parents:
                            insert_element = parents[0]
                            log_debug(f"  [INFO] Using parent {insert_element.name} for NavigableString")
                        else:
                            wrapper = soup.new_tag('div')
                            wrapper['style'] = 'margin:10px 0;'
                            wrapper.append(bullet_list)
                            
                            try:
                                element.replace_with(wrapper)
                                mapped += 1
                                log_debug(f"  [MAPPED] {len(matched_bullets)} bullets (replaced string)")
                                continue
                            except:
                                log_debug(f"  [SKIP] Could not map bullets")
                                continue
                    except Exception as e:
                        log_debug(f"  [ERROR] Getting parent: {e}")
                        continue
                
                if hasattr(insert_element, 'name') and insert_element.name in ['strong', 'b']:
                    parent_container = insert_element.find_parent(['p', 'div', 'span'])
                    if parent_container:
                        insert_element = parent_container
                        log_debug(f"  [INFO] Using parent container <{parent_container.name}>")
                
                bullet_div = soup.new_tag('div')
                bullet_div['style'] = 'margin:10px 0 20px 0;'
                bullet_div.append(bullet_list)
                
                try:
                    parent = insert_element.parent
                    
                    if not parent:
                        log_debug(f"  [ERROR] No parent for insert_element")
                        continue
                    
                    children = list(parent.children)
                    
                    try:
                        index = children.index(insert_element)
                    except ValueError:
                        log_debug(f"  [ERROR] Element not in parent's children")
                        continue
                    
                    parent.insert(index + 1, bullet_div)
                    
                    new_children = list(parent.children)
                    if bullet_div in new_children:
                        mapped += 1
                        log_debug(f"  [MAPPED] {len(matched_bullets)} bullets - VERIFIED")
                    else:
                        log_debug(f"  [ERROR] Bullets NOT in soup after insertion!")
                        
                        try:
                            insert_element.insert_after(bullet_div)
                            verify = list(parent.children)
                            if bullet_div in verify:
                                mapped += 1
                                log_debug(f"  [MAPPED] {len(matched_bullets)} bullets via insert_after")
                        except Exception as e2:
                            log_debug(f"  [FAILED] Both methods failed: {e2}")
                        
                except Exception as e:
                    log_debug(f"  [ERROR] Insertion error: {e}")

        else:
            # Remove section (no content)
            element = section['element']
            remove_instructions(element)
            
            try:
                if section_type == 'table':
                    # For table sections without content, just remove the header
                    # Keep the cell structure
                    if hasattr(element, 'decompose'):
                        element.decompose()
                    elif isinstance(element, NavigableString):
                        try:
                            element.extract()
                        except:
                            pass
                else:
                    if isinstance(element, NavigableString):
                        try:
                            element.extract()
                        except:
                            try:
                                parents = list(element.parents) if hasattr(element, 'parents') else []
                                if parents and hasattr(parents[0], 'decompose'):
                                    parents[0].decompose()
                            except:
                                pass
                    else:
                        if hasattr(element, 'name') and element.name in ['strong', 'b']:
                            parent_container = element.find_parent(['p', 'div', 'span'])
                            if parent_container:
                                parent_container.decompose()
                            else:
                                element.decompose()
                        else:
                            if hasattr(element, 'decompose'):
                                element.decompose()
                
                removed += 1
                log_debug(f"  [REMOVED] No content")
            except Exception as e:
                log_debug(f"  [WARNING] Could not remove: {e}")
    
    # Convert to HTML string
    html = str(soup)
    
    # Final cleanup
    html = re.sub(r'<span style="font-family: Verdana; font-size: 8pt;">.*?</span>', '', html, flags=re.DOTALL)
    html = re.sub(r'<span style="font-family: Verdana;">.*?</span>', '', html, flags=re.DOTALL)
    html = re.sub(r'\([^)]{100,}\)', '', html)
    
    html = re.sub(r'(<br\s*/?>\s*){3,}', '<br/><br/>', html)
    html = re.sub(r'<span>\s*</span>', '', html)
    html = re.sub(r'<p[^>]*>\s*</p>', '', html)
    html = re.sub(r'<p[^>]*>\s*<strong[^>]*>\s*</strong>\s*</p>', '', html)
    
    # VERIFY bullets in final HTML
    bullet_count = html.count('<li')
    log_debug(f"[VARDPLAN_MAPPER] Final HTML contains {bullet_count} <li> tags")
    
    if bullet_count > 0:
        log_debug(f"[VARDPLAN_MAPPER] ✓ SUCCESS: {bullet_count} bullets inserted")
    else:
        log_debug(f"[VARDPLAN_MAPPER] ✗ ERROR: NO bullets in final HTML!")
        log_debug(f"[VARDPLAN_MAPPER] HTML preview (first 1500 chars):")
        log_debug(html[:1500])
    
    log_debug(f"[VARDPLAN_MAPPER] Done: {mapped} mapped, {removed} removed")
    
    return html