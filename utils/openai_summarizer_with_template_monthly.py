"""
OpenAI Summarizer for Monthly Reports (Månadsrapport)
Handles day-to-day journal entries and maps to template sections
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
                               client_id=0, cust_id=0, user_id=0):
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
    metadata_keywords = ['månadsrapport', 'slutrapport', 'dagens datum', 'förnamn', 'efternamn', 'personnummer']
    content_sections = [
        s for s in section_names 
        if not any(kw in s.lower() for kw in metadata_keywords)
    ]
    
    log_debug(f"[MONTHLY_SUMMARIZER] Content sections: {len(content_sections)}")
    
    # Build sections list
    sections_list = "\n".join([f"- {name}" for name in content_sections])
    
    # Create prompt
    prompt = f"""You are analyzing daily journal entries to create a monthly report (Månadsrapport).

DAILY JOURNAL ENTRIES (with or without headers):
{journal_context}

TEMPLATE SECTIONS (use EXACT names as JSON keys):
{sections_list}

YOUR TASK:
1. Read ALL journal entries and understand the content
2. Organize information into the template sections above
3. Create 3-8 bullet points per section (10-30 words each)
4. Match content to sections based on MEANING, not keywords
5. Include specific dates, names, activities, and facts
6. Highlight dates: {{{{HIGHLIGHT}}}}date{{{{/HIGHLIGHT}}}}
7. If NO content for a section, OMIT it from JSON completely
8. Write in professional svenska
9. DO NOT include instruction text or explanations

CONTENT MATCHING EXAMPLES:
- "Lycka pratar om mående" → "Känslo - och beteendemässig utveckling"
- "Kontaktade praktikansvarig" → "Utbildning"
- "Samtal med pappa Kent" → "Familj och sociala relationer"
- "Åt kvällsmat" → "Hälsa"

CRITICAL RULES:
- Use EXACT section names from template as JSON keys
- Combine information from ALL journal entries
- Each bullet must be specific with dates/names/activities
- Focus on facts and actions, not interpretations
- OMIT sections with no relevant content
- NO instruction text in output - ONLY bullet points

RETURN JSON:
{{
  "Känslo - och beteendemässig utveckling": [
    "{{{{HIGHLIGHT}}}}2025-11-08{{{{/HIGHLIGHT}}}} Specific activity with details",
    "Another bullet with concrete information"
  ],
  "Utbildning": [
    "Bullet about education/school/internship"
  ]
}}

Remember: Only include sections with actual content from journal entries.
"""

    return _execute_request(
        prompt, model, max_tokens, content_sections, documents, language,
        ip_address, client_int_doc_ids, journal_doc_ids, internal_doc_id,
        client_id, cust_id, user_id
    )


def _execute_request(prompt, model, max_tokens, section_names, documents, language,
                     ip_address, client_int_doc_ids, journal_doc_ids, internal_doc_id,
                     client_id, cust_id, user_id):
    """Execute OpenAI request"""
    
    try:
        start_time = time.time()
        
        log_debug(f"[MONTHLY_SUMMARIZER] Calling OpenAI API...")
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": f"You are an expert at analyzing journal entries and creating organized summaries in {language}. You understand day-to-day notes (with or without headers) and intelligently categorize content by template sections. You ONLY include sections with actual content - empty sections are omitted from JSON."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        
        elapsed = time.time() - start_time
        content = response.choices[0].message.content.strip()
        
        log_debug(f"[MONTHLY_SUMMARIZER] API call completed in {elapsed:.2f}s")
        log_debug(f"[MONTHLY_SUMMARIZER] Response: {content[:200]}...")
        
        # Parse JSON
        section_bullets = json.loads(content)
        
        # Filter placeholder content
        filtered_bullets = {}
        placeholders = ['', 'information saknas', 'ingen information', 'saknas', 'n/a', 'none']
        
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
            'intInternalDocId': internal_doc_id
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