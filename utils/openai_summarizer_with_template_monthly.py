# utils/openai_summarizer_with_template_monthly.py
"""
OpenAI Summarizer for Monthly Reports (Månadsrapport)
Handles day-to-day journal entries and maps to template sections
FIXED: Much stricter prompts to prevent AI from inventing sections
"""

from openai import OpenAI
import json
import time
from db_model import model_pricing, log_to_database
from utils.config import Config

try:
    from save_logs import log_debug
except:
    def log_debug(msg):
        pass

conf = Config()
client = OpenAI(api_key=conf.OPENAI_API_KEY)


def generate_monthly_summaries(documents, section_names, model, max_tokens=6000, ip_address=None,
                               client_int_doc_ids=None, journal_doc_ids=None, internal_doc_id=None,
                               client_id=0, cust_id=0, user_id=0, report_type=None, client_name=None, client_pnr=None):
    """
    Generate summaries for Monthly Report from day-to-day journal entries
    
    Args:
        documents: List of journal entries (daily notes)
        section_names: Template section headers
        model: OpenAI model
        max_tokens: Max output tokens
        
    Returns:
        dict: {section_bullets, tokens, costs, etc.}
    """
    
    language = 'svenska'
    
    # Shared metadata keywords
    metadata_keywords = [
        'månadsrapport', 'slutrapport', 'rapport',
        'dagens datum', 'förnamn', 'efternamn', 'personnummer'
    ]
    
    log_debug(f"[MONTHLY_SUMMARIZER] Processing {len(documents)} journal entries")
    log_debug(f"[MONTHLY_SUMMARIZER] Template sections: {len(section_names)}")
    log_debug(f"[MONTHLY_SUMMARIZER] Model: {model}")
    
    # Build journal context from day notes
    journal_context = ""
    for idx, doc in enumerate(documents, 1):
        doc_name = doc.get('name', f'Note {idx}')
        doc_text = doc.get('text', '')[:8000]
        word_count = doc.get('text_info', {}).get('word_count', 0)
        created_date = doc.get('created_date', 'Unknown')
        
        journal_context += f"\n{'='*60}\n"
        journal_context += f"Day Note {idx} - {created_date}\n"
        journal_context += f"({word_count} words)\n"
        journal_context += f"{'='*60}\n"
        journal_context += f"{doc_text}\n\n"
    
    log_debug(f"[MONTHLY_SUMMARIZER] Built context: {len(journal_context)} characters")
    
    # Filter out metadata sections
    content_sections = [
        s for s in section_names 
        if not any(kw in s.lower() for kw in metadata_keywords)
    ]
    
    log_debug(f"[MONTHLY_SUMMARIZER] Content sections: {len(content_sections)}")
    
    # Build sections list with numbering for clarity
    sections_list = "\n".join([f"{i+1}. {name}" for i, name in enumerate(content_sections)])
    
    # Create prompt with MUCH STRICTER instructions
    prompt = f"""You are analyzing daily journal entries to create a monthly report (Månadsrapport).

DAILY JOURNAL ENTRIES (with or without headers):
{journal_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  CRITICAL: USE THESE EXACT SECTION NAMES - DO NOT MODIFY ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TEMPLATE SECTIONS (COPY EXACTLY AS JSON KEYS):
{sections_list}

TOTAL SECTIONS: {len(content_sections)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⛔ ABSOLUTE RULES - SYSTEM WILL FAIL IF YOU BREAK THESE ⛔
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ✋ USE EXACT SECTION NAMES - Copy character-by-character including:
   - Exact spelling
   - Exact capitalization
   - Exact spaces and punctuation
   - Special characters like å, ä, ö

2. ✋ DO NOT modify section names:
   ❌ WRONG: "Känslo - och beteendemässig utveckling"
   ✅ RIGHT: "Känslor och Beteende"
   
   ❌ WRONG: "Skola/sysselsättning"
   ✅ RIGHT: "Skola och/eller annan sysselsättning"

3. ✋ DO NOT add sections not in the list above:
   ❌ WRONG: Adding "Hälsa" because you see health content
   ❌ WRONG: Adding "Utbildning" or any other section
   ✅ RIGHT: Use ONLY the {len(content_sections)} sections listed above

4. ✋ DO NOT translate, improve, or professionalize section names:
   ❌ WRONG: Making names sound more formal
   ✅ RIGHT: Copy EXACTLY as shown

5. ✋ If no relevant content exists for a section:
   - OMIT that section completely from JSON
   - DO NOT include it with empty array
   - DO NOT include it with placeholder text

6. ✋ JSON KEYS MUST MATCH EXACTLY:
   - Compare your JSON keys with the template list above
   - Every character must be identical
   - If unsure, copy-paste the section name

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

YOUR TASK:
1. Read ALL journal entries and understand the content
2. Create 3-8 bullet points per section (10-30 words each)
3. Match content to sections based on MEANING
4. Include specific dates, names, activities, and facts
5. Highlight dates: {{{{HIGHLIGHT}}}}date{{{{/HIGHLIGHT}}}}
6. Write in professional svenska
7. Include information from both original and corrected text
8. Use ONLY sections with actual content - omit empty sections

CONTENT MATCHING EXAMPLES:
- "Lycka pratar om mående" → Use the section about emotions from list above
- "Kontaktade praktikansvarig" → Use the section about education/work from list above
- "Samtal med pappa Kent" → Use the section about family/social from list above
- "Åt kvällsmat" → Use appropriate section from list above

-- Table Header Metadata (SEPARATE from sections):
    - DOKUMENTNAMN: Replace with "{report_type}" in two words on single line
    - Dagens datum: Today's date
    - Förnamn Efternamn: {client_name}
    - Personnummer: {client_pnr}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RETURN JSON (use EXACT section names from template above):
{{
  "Känslor och Beteende": [
    "{{{{HIGHLIGHT}}}}2025-11-08{{{{/HIGHLIGHT}}}} Specific activity with details",
    "Another bullet with concrete information"
  ],
  "Boende och ekonomi": [
    "Bullet about housing/economy"
  ]
}}

⚠️  REMINDER: Your JSON must have MAXIMUM {len(content_sections)} sections (only those listed above).
⚠️  Use EXACT names - the system does strict string matching!
⚠️  Do NOT invent new sections or modify existing section names!
"""

    return _execute_request(
        prompt, model, max_tokens, content_sections, documents, language,
        ip_address, client_int_doc_ids, journal_doc_ids, internal_doc_id,
        client_id, cust_id, user_id, report_type
    )


def generate_content_for_unmapped_monthly_sections(unmapped_sections, documents, model, max_tokens=6000,
                                                   ip_address=None, client_int_doc_ids=None, 
                                                   journal_doc_ids=None, internal_doc_id=None,
                                                   client_id=0, cust_id=0, user_id=0,
                                                   report_type=None, client_name=None, client_pnr=None):
    """
    Generate content for monthly template sections missed in first pass
    
    Args:
        unmapped_sections (list): Section names that need content
        documents (list): Original journal entries
        model (str): OpenAI model
        max_tokens (int): Max output tokens
        
    Returns:
        dict: {section_bullets, tokens, costs, etc.}
    """
    language = 'svenska'
    
    log_debug(f"[UNMAPPED_MONTHLY] Generating content for {len(unmapped_sections)} sections")
    log_debug(f"[UNMAPPED_MONTHLY] Sections: {unmapped_sections}")
    
    # Build journal context
    journal_context = ""
    for idx, doc in enumerate(documents, 1):
        doc_name = doc.get('name', f'Entry {idx}')
        doc_text = doc.get('text', '')[:6000]
        word_count = doc.get('text_info', {}).get('word_count', 0)
        created_date = doc.get('created_date', 'Unknown')
        
        journal_context += f"\n{'='*60}\n"
        journal_context += f"Journal Entry {idx} - {created_date}\n"
        journal_context += f"({word_count} words)\n"
        journal_context += f"{'='*60}\n"
        journal_context += f"{doc_text}\n\n"
    
    # Build sections list with numbering
    sections_list = "\n".join([f"{i+1}. {name}" for i, name in enumerate(unmapped_sections)])
    
    # Create prompt with STRICT instructions
    prompt = f"""You are analyzing journal entries to fill missing monthly report sections.

JOURNAL ENTRIES:
{journal_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  CRITICAL: USE THESE EXACT SECTION NAMES - DO NOT MODIFY ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TEMPLATE SECTIONS TO FILL (USE EXACT NAMES AS JSON KEYS):
{sections_list}

TOTAL SECTIONS TO FILL: {len(unmapped_sections)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⛔ ABSOLUTE RULES ⛔
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ✋ YOU MUST FILL ALL {len(unmapped_sections)} SECTIONS ABOVE
2. ✋ USE EXACT NAMES - Copy character-by-character from list above
3. ✋ DO NOT modify, translate, or improve section names
4. ✋ DO NOT add any sections not in the list above
5. ✋ Your JSON must have EXACTLY {len(unmapped_sections)} keys

INSTRUCTIONS:
1. Create 3-8 bullet points per section (10-30 words each)
2. Extract ANY related information from journal entries
3. Match content based on MEANING, not exact keywords
4. If truly no related content exists after thorough search, use "Information saknas i dokumenten"
5. Highlight dates: {{{{HIGHLIGHT}}}}date{{{{/HIGHLIGHT}}}}
6. Use EXACT section names as JSON keys
7. Write in professional svenska
8. Include information from both original and corrected text

-- Table Header Metadata:
    - DOKUMENTNAMN: Replace with "{report_type}" in two words on single line
    - Dagens datum: Today's date
    - Förnamn Efternamn: {client_name}
    - Personnummer: {client_pnr}

CONTENT MATCHING EXAMPLES:
- "Lycka pratar om känslor" → Map to emotions section from list above
- "Telefonsamtal med skolan" → Map to education section from list above
- "Träffade mamma" → Map to family/social section from list above

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RETURN JSON WITH ALL {len(unmapped_sections)} SECTIONS (use EXACT names from list above):
{{
  "Exact Section Name 1": ["bullet 1", "bullet 2", ...],
  "Exact Section Name 2": ["bullet 1", "bullet 2", ...]
}}

⚠️  CRITICAL: Copy section names EXACTLY from the list above!
⚠️  Your JSON must contain EXACTLY {len(unmapped_sections)} keys!
⚠️  Do NOT modify section names in ANY way!
"""

    return _execute_request(
        prompt, model, max_tokens, unmapped_sections, documents, language,
        ip_address, client_int_doc_ids, journal_doc_ids, internal_doc_id,
        client_id, cust_id, user_id, report_type
    )


def _execute_request(prompt, model, max_tokens, section_names, documents, language,
                     ip_address, client_int_doc_ids, journal_doc_ids, internal_doc_id,
                     client_id, cust_id, user_id, report_type):
    """Execute OpenAI request (shared function)"""
    
    try:
        start_time = time.time()
        
        log_debug(f"[MONTHLY_SUMMARIZER] Calling OpenAI API...")
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": f"You are an expert at analyzing journal entries and creating organized summaries in {language}. You MUST use EXACT section names from the template without any modifications. You understand that the system does strict string matching and will fail if section names don't match exactly. You NEVER add sections that aren't explicitly listed in the template."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Lower temperature for more deterministic output
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        
        elapsed = time.time() - start_time
        content = response.choices[0].message.content.strip()
        
        log_debug(f"[MONTHLY_SUMMARIZER] API call completed in {elapsed:.2f}s")
        log_debug(f"[MONTHLY_SUMMARIZER] Response: {content[:200]}...")
        
        # Parse JSON
        section_bullets = json.loads(content)
        
        # ===== VALIDATE: Remove sections NOT in template =====
        validated_bullets = {}
        for section_name, bullets in section_bullets.items():
            # Check if this section exists in the template (case-sensitive exact match)
            if section_name in section_names:
                validated_bullets[section_name] = bullets
            else:
                # Try case-insensitive and whitespace-normalized match
                section_normalized = ' '.join(section_name.split()).strip()
                matched = False
                for template_section in section_names:
                    template_normalized = ' '.join(template_section.split()).strip()
                    if section_normalized.lower() == template_normalized.lower():
                        # Use the template's exact name
                        validated_bullets[template_section] = bullets
                        matched = True
                        log_debug(f"[VALIDATION] Corrected section name: '{section_name}' → '{template_section}'")
                        break
                
                if not matched:
                    log_debug(f"[VALIDATION] ⚠️ REMOVED non-template section: '{section_name}'")
        
        section_bullets = validated_bullets
        # ===== END VALIDATION =====
        
        # Filter placeholder content
        filtered_bullets = {}
        placeholders = ['', 'information saknas', 'information saknas i dokumenten', 
                       'ingen information', 'saknas', 'n/a', 'none']
        
        for section_name, bullets in section_bullets.items():
            if not bullets:
                continue
            
            has_content = any(
                str(b).strip() and str(b).strip().lower() not in placeholders 
                for b in bullets
            )
            
            if has_content:
                filtered_bullets[section_name] = bullets
        
        section_bullets = filtered_bullets
        
        # Calculate stats
        usage = response.usage
        total_bullets = sum(len(b) for b in section_bullets.values())
        
        log_debug(f"[MONTHLY_SUMMARIZER] Success: {len(section_bullets)} sections, {total_bullets} bullets")
        log_debug(f"[MONTHLY_SUMMARIZER] Tokens: {usage.total_tokens}")
        
        # Calculate costs
        INPUT_COST = 0.15 / 1_000_000
        OUTPUT_COST = 0.60 / 1_000_000
        
        input_cost = usage.prompt_tokens * INPUT_COST
        output_cost = usage.completion_tokens * OUTPUT_COST
        total_cost = input_cost + output_cost
        
        # Check model pricing
        if model not in ["gpt-4o-mini"]:
            pricing = model_pricing(model)
            if pricing:
                input_cost = (usage.prompt_tokens / 1_000_000) * pricing["inputCostPerM"]
                output_cost = (usage.completion_tokens / 1_000_000) * pricing["outputCostPerM"]
                total_cost = input_cost + output_cost
        
        log_debug(f"[MONTHLY_SUMMARIZER] Cost: ${total_cost:.6f}")
        
        # Log to database
        log_to_database({
            'cid': cust_id,
            'user_id': user_id,
            'client_id': client_id,
            'document_count': len(documents),
            'prompt_tokens': usage.prompt_tokens,
            'completion_tokens': usage.completion_tokens,
            'total_tokens': usage.total_tokens,
            'model': model,
            'api_calls': 1,
            'input_cost': input_cost,
            'output_cost': output_cost,
            'total_cost': total_cost,
            'ip_address': ip_address or 'N/A',
            'processing_time': elapsed,
            'chrClientIntDocIds': client_int_doc_ids,
            'chrJournalDocIds': journal_doc_ids,
            'intInternalDocId': internal_doc_id,
            'chrReportType': report_type
        })
        
        return {
            'section_bullets': section_bullets,
            'tokens': usage.total_tokens,
            'input_tokens': usage.prompt_tokens,
            'output_tokens': usage.completion_tokens,
            'time': elapsed,
            'input_cost': round(input_cost, 6),
            'output_cost': round(output_cost, 6),
            'total_cost': round(total_cost, 6)
        }
        
    except Exception as e:
        log_debug(f"[MONTHLY_SUMMARIZER] ERROR: {e}")
        import traceback
        log_debug(traceback.format_exc())
        
        return {
            'section_bullets': {},
            'tokens': 0,
            'input_tokens': 0,
            'output_tokens': 0,
            'time': 0,
            'input_cost': 0,
            'output_cost': 0,
            'total_cost': 0
        }