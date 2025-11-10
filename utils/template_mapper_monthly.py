"""
Template Mapper for Monthly Reports
Maps AI bullets to template and removes instructions
FIXED: NavigableString parent handling
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
        # NavigableString uses .parent (singular)
        return element.parent if hasattr(element, 'parent') else None
    elif isinstance(element, Tag):
        # Tag also uses .parent
        return element.parent if hasattr(element, 'parent') else None
    else:
        # Fallback
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


def map_monthly_bullets(template_html, section_bullets, template_structure):
    """
    Map bullets to monthly template
    """
    
    log_debug("[MONTHLY_MAPPER] Starting mapping...")
    
    soup = template_structure.get('soup')
    sections = template_structure.get('sections', [])
    
    if not soup:
        soup = BeautifulSoup(template_html, 'html.parser')
    
    log_debug(f"[MONTHLY_MAPPER] Sections: {len(sections)}, Bullets: {len(section_bullets)}")
    
    # Replace metadata
    html = str(soup)
    html = html.replace('[Dagens datum]', datetime.now().strftime('%Y-%m-%d'))
    html = html.replace('[Förnamn]', '').replace('[Efternamn]', '').replace('[Personnummer]', '')
    soup = BeautifulSoup(html, 'html.parser')
    
    # Re-detect sections
    from utils.template_analyzer_monthly import analyze_monthly_template
    template_structure = analyze_monthly_template(str(soup))
    sections = template_structure['sections']
    
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
        
        if matched_bullets and len(matched_bullets) > 0:
            # Map bullets
            element = section['element']
            remove_instructions(element)
            
            # Create bullet list
            bullet_list = create_bullets(matched_bullets, soup)
            
            # Insert based on type
            if section_type == 'table':
                content_cell = section.get('content_element')
                if content_cell:
                    content_cell.clear()
                    content_cell.append(bullet_list)
                    mapped += 1
                    log_debug(f"  [MAPPED] {len(matched_bullets)} bullets")
            else:
                # TEXT TYPE: Handle NavigableString properly
                insert_element = element
                
                if isinstance(element, NavigableString):
                    # Get the actual parent Tag
                    try:
                        parents = list(element.parents) if hasattr(element, 'parents') else []
                        if parents:
                            insert_element = parents[0]
                            log_debug(f"  [INFO] Using parent {insert_element.name} for NavigableString")
                        else:
                            log_debug(f"  [WARNING] Could not get parent for NavigableString")
                            # Try to create a wrapper and insert
                            wrapper = soup.new_tag('div')
                            wrapper['style'] = 'margin:10px 0;'
                            wrapper.append(bullet_list)
                            
                            # Try to replace the NavigableString with the wrapper
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
                
                # Now insert_element is a Tag, wrap bullets in div
                bullet_div = soup.new_tag('div')
                bullet_div['style'] = 'margin:10px 0 20px 0;'
                bullet_div.append(bullet_list)
                
                # Insert after the element
                try:
                    insert_element.insert_after(bullet_div)
                    mapped += 1
                    log_debug(f"  [MAPPED] {len(matched_bullets)} bullets")
                except Exception as e:
                    log_debug(f"  [WARNING] Could not insert: {e}")

        else:
            # Remove section
            element = section['element']
            remove_instructions(element)
            
            try:
                if section_type == 'table':
                    # For table sections, remove the row
                    if isinstance(element, NavigableString):
                        # Can't process NavigableString in tables, skip
                        log_debug(f"  [SKIP] Cannot remove NavigableString from table")
                    else:
                        row = element.find_parent('tr') if hasattr(element, 'find_parent') else None
                        if row:
                            row.decompose()
                        elif hasattr(element, 'decompose'):
                            element.decompose()
                else:
                    # For text sections
                    if isinstance(element, NavigableString):
                        # NavigableString: try to extract it (safer than decompose)
                        try:
                            element.extract()
                        except:
                            # If extract fails, try getting parent and removing that
                            try:
                                # Use list() to get all parents and take first one
                                parents = list(element.parents) if hasattr(element, 'parents') else []
                                if parents:
                                    parent = parents[0]
                                    if hasattr(parent, 'decompose'):
                                        parent.decompose()
                            except:
                                log_debug(f"  [SKIP] Could not remove NavigableString")
                                pass
                    else:
                        # Regular Tag element
                        if hasattr(element, 'decompose'):
                            element.decompose()
                
                removed += 1
                log_debug(f"  [REMOVED] No content")
            except Exception as e:
                log_debug(f"  [WARNING] Could not remove element: {e}")
    
    # Final cleanup - remove ALL Verdana 8pt spans (instructions)
    html = str(soup)
    
    # Remove Verdana instruction spans
    html = re.sub(r'<span style="font-family: Verdana; font-size: 8pt;">.*?</span>', '', html, flags=re.DOTALL)
    html = re.sub(r'<span style="font-family: Verdana;">.*?</span>', '', html, flags=re.DOTALL)
    
    # Remove instruction text in parentheses (long ones)
    html = re.sub(r'\([^)]{100,}\)', '', html)
    
    # Remove specific instruction keywords
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
    
    # Clean up excessive breaks and empty spans
    html = re.sub(r'(<br\s*/?>\s*){3,}', '<br/><br/>', html)
    html = re.sub(r'<span>\s*</span>', '', html)
    html = re.sub(r'<span><br/></span>', '', html)
    html = re.sub(r'\n\s*\n\s*\n+', '\n\n', html)
    
    log_debug(f"[MONTHLY_MAPPER] Done: {mapped} mapped, {removed} removed")
    
    return html