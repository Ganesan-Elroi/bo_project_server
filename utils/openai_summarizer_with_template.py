"""
OpenAI Summarizer with Template Support - DEBUG VERSION
"""

from openai import OpenAI
import os
import json
import time
from db_model import model_pricing, log_to_database
from utils.config import Config

try:
    from save_logs import log_debug
    LOGGING_ENABLED = True
except:
    LOGGING_ENABLED = False
    def log_debug(msg):
        print(msg)  # Fallback to print

conf = Config()
client = OpenAI(api_key=conf.OPENAI_API_KEY)


def generate_section_specific_summaries(documents, section_names, model, max_tokens=4000, ip_address=None,
                                        client_int_doc_ids=None, journal_doc_ids=None, internal_doc_id=None,
                                        client_id=0, cust_id=0, user_id=0, report_type=None):
    """Generate summaries organized by template sections"""
    
    log_debug(f"[SUMMARIZER] ==================== ENTRY POINT ====================")
    log_debug(f"[SUMMARIZER] Function called: generate_section_specific_summaries")
    log_debug(f"[SUMMARIZER] report_type: '{report_type}'")
    log_debug(f"[SUMMARIZER] documents: {len(documents)}")
    log_debug(f"[SUMMARIZER] section_names: {len(section_names) if section_names else 'None'}")
    log_debug(f"[SUMMARIZER] model: {model}")
    
    try:
        # Route to appropriate function
        report_type_lower = report_type.lower() if report_type else ""
        log_debug(f"[SUMMARIZER] report_type_lower: '{report_type_lower}'")
        
        if report_type_lower in ["monthlyreport", "månadsrapport", "monthly", "manad"]:
            log_debug(f"[SUMMARIZER] >>> Routing to MONTHLY <<<")
            result = generate_monthly_report_summaries(
                documents, section_names, model, max_tokens, ip_address,
                client_int_doc_ids, journal_doc_ids, internal_doc_id,
                client_id, cust_id, user_id
            )
            log_debug(f"[SUMMARIZER] Monthly result: tokens={result.get('tokens', 0)}, sections={len(result.get('section_bullets', {}))}")
            return result
        else:
            log_debug(f"[SUMMARIZER] >>> Routing to SLUTRAPPORT <<<")
            result = generate_slutrapport_summaries(
                documents, section_names, model, max_tokens, ip_address,
                client_int_doc_ids, journal_doc_ids, internal_doc_id,
                client_id, cust_id, user_id
            )
            log_debug(f"[SUMMARIZER] Slutrapport result: tokens={result.get('tokens', 0)}, sections={len(result.get('section_bullets', {}))}")
            return result
    
    except Exception as e:
        log_debug(f"[SUMMARIZER] EXCEPTION in generate_section_specific_summaries: {e}")
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


def generate_monthly_report_summaries(documents, section_names, model, max_tokens=4000, ip_address=None,
                                      client_int_doc_ids=None, journal_doc_ids=None, internal_doc_id=None,
                                      client_id=0, cust_id=0, user_id=0):
    """Generate summaries for Monthly Report"""
    
    log_debug(f"[SUMMARIZER] [MONTHLY] ==================== MONTHLY FUNCTION ====================")
    log_debug(f"[SUMMARIZER] [MONTHLY] Entered generate_monthly_report_summaries")
    log_debug(f"[SUMMARIZER] [MONTHLY] Documents: {len(documents)}")
    log_debug(f"[SUMMARIZER] [MONTHLY] Section names: {len(section_names) if section_names else 0}")
    log_debug(f"[SUMMARIZER] [MONTHLY] Model: {model}")
    
    language = 'svenska'
    
    # Build journal context
    journal_context = ""
    for idx, doc in enumerate(documents, 1):
        doc_name = doc.get('name', f'Entry {idx}')
        doc_text = doc.get('text', '')[:8000]
        word_count = doc.get('text_info', {}).get('word_count', 0)
        created_date = doc.get('created_date', 'Unknown')
        
        journal_context += f"\n{'='*60}\n"
        journal_context += f"Entry {idx} - {created_date}\n"
        journal_context += f"({word_count} words)\n"
        journal_context += f"{'='*60}\n"
        journal_context += f"{doc_text}\n\n"
    
    log_debug(f"[SUMMARIZER] [MONTHLY] Journal context built: {len(journal_context)} chars")
    
    # Build sections list
    has_template_sections = section_names and len(section_names) > 0
    
    if has_template_sections:
        sections_list = "\n".join([f"- {name}" for name in section_names])
        log_debug(f"[SUMMARIZER] [MONTHLY] Using {len(section_names)} template sections")
    else:
        sections_list = "NO TEMPLATE SECTIONS"
        log_debug(f"[SUMMARIZER] [MONTHLY] No template sections - AI will create its own")
    
    # Build prompt
    prompt = f"""You are analyzing journal entries to create a monthly summary report (Månadsrapport).

        JOURNAL ENTRIES:
        {journal_context}

        TEMPLATE SECTIONS:
        {sections_list}

        YOUR TASK:
        1. Use ONLY the CONTENT sections from template as JSON keys
        2. IGNORE these metadata fields: "Månadsrapport", "Dagens datum", "Förnamn", "Efternamn", "Personnummer"
        3. Create 3-8 bullet points per CONTENT section (10-30 words each)
        4. Include specific dates, names, facts, and activities from journals
        5. Highlight dates: {{{{HIGHLIGHT}}}}date{{{{/HIGHLIGHT}}}}
        6. If NO relevant content exists for a section, OMIT it completely from JSON
        7. Write in professional svenska
        8. DO NOT include any instruction text in parentheses - ONLY bullet points

        CONTENT SECTIONS TO USE (ignore any metadata sections):
        {", ".join([s for s in section_names if s.lower() not in ['månadsrapport', 'dagens datum', 'förnamn efternamn', 'förnamn', 'efternamn', 'personnummer']]) if has_template_sections else "Create appropriate Swedish section names"}

        CRITICAL RULES:
        - Use EXACT content section names from template as JSON keys
        - DO NOT create sections for "Månadsrapport", "Dagens datum", "Förnamn", "Efternamn"
        - Combine information from ALL journal entries
        - Each bullet must have specific details (dates, names, activities)
        - Focus on facts and concrete actions
        - OMIT sections with no relevant information
        - NO instruction text or explanations in output

        RETURN JSON FORMAT:
        {{
        "Känslo - och beteendemässig utveckling": [
            "Specific bullet with {{{{HIGHLIGHT}}}}date{{{{/HIGHLIGHT}}}} and details"
        ],
        "Utbildning": [
            "Bullet point"
        ]
        }}

        Remember: Only include CONTENT sections with actual information. Omit metadata and empty sections.
        """

    log_debug(f"[SUMMARIZER] [MONTHLY] Prompt built: {len(prompt)} chars")
    log_debug(f"[SUMMARIZER] [MONTHLY] About to call _execute_openai_request")
    
    result = _execute_openai_request(
        prompt, model, max_tokens, section_names, documents, language,
        ip_address, client_int_doc_ids, journal_doc_ids, internal_doc_id,
        client_id, cust_id, user_id, "MONTHLY"
    )
    
    log_debug(f"[SUMMARIZER] [MONTHLY] Returned from _execute_openai_request")
    log_debug(f"[SUMMARIZER] [MONTHLY] Result tokens: {result.get('tokens', 0)}")
    log_debug(f"[SUMMARIZER] [MONTHLY] Result sections: {len(result.get('section_bullets', {}))}")
    
    return result


def generate_slutrapport_summaries(documents, section_names, model, max_tokens=4000, ip_address=None,
                                   client_int_doc_ids=None, journal_doc_ids=None, internal_doc_id=None,
                                   client_id=0, cust_id=0, user_id=0):
    """Generate summaries for Slutrapport"""
    
    log_debug(f"[SUMMARIZER] [SLUTRAPPORT] ==================== SLUTRAPPORT FUNCTION ====================")
    log_debug(f"[SUMMARIZER] [SLUTRAPPORT] This should NOT be called for Månadsrapport!")
    
    # ... (rest of function - same as before)
    return {
        'section_bullets': {},
        'tokens': 0,
        'time': 0,
        'input_cost': 0,
        'output_cost': 0,
        'total_cost': 0
    }


def _execute_openai_request(prompt, model, max_tokens, section_names, documents, language,
                            ip_address, client_int_doc_ids, journal_doc_ids, internal_doc_id,
                            client_id, cust_id, user_id, report_label):
    """Execute OpenAI request"""
    
    log_debug(f"[SUMMARIZER] [{report_label}] ==================== OPENAI REQUEST ====================")
    log_debug(f"[SUMMARIZER] [{report_label}] Entered _execute_openai_request")
    log_debug(f"[SUMMARIZER] [{report_label}] Model: {model}")
    log_debug(f"[SUMMARIZER] [{report_label}] Max tokens: {max_tokens}")
    log_debug(f"[SUMMARIZER] [{report_label}] Prompt length: {len(prompt)}")
    
    try:
        start_time = time.time()
        
        log_debug(f"[SUMMARIZER] [{report_label}] Calling OpenAI API NOW...")
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": f"You are an expert at creating summaries in {language}."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        
        elapsed = time.time() - start_time
        
        log_debug(f"[SUMMARIZER] [{report_label}] API call completed in {elapsed:.2f}s")
        
        content = response.choices[0].message.content.strip()
        log_debug(f"[SUMMARIZER] [{report_label}] Response length: {len(content)} chars")
        log_debug(f"[SUMMARIZER] [{report_label}] Response preview: {content[:200]}...")
        
        section_bullets = json.loads(content)
        log_debug(f"[SUMMARIZER] [{report_label}] Parsed {len(section_bullets)} sections")
        
        usage = response.usage
        log_debug(f"[SUMMARIZER] [{report_label}] Tokens used: {usage.total_tokens}")
        
        # Calculate costs
        INPUT_COST_PER_1M = 0.15
        OUTPUT_COST_PER_1M = 0.60
        
        input_cost = (usage.prompt_tokens / 1_000_000) * INPUT_COST_PER_1M
        output_cost = (usage.completion_tokens / 1_000_000) * OUTPUT_COST_PER_1M
        total_cost = input_cost + output_cost
        
        result = {
            'section_bullets': section_bullets,
            'tokens': usage.total_tokens,
            'input_tokens': usage.prompt_tokens,
            'output_tokens': usage.completion_tokens,
            'time': elapsed,
            'input_cost': round(input_cost, 6),
            'output_cost': round(output_cost, 6),
            'total_cost': round(total_cost, 6)
        }
        
        log_debug(f"[SUMMARIZER] [{report_label}] Returning result with {usage.total_tokens} tokens")
        
        # Log to database
        try:
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
            log_debug(f"[SUMMARIZER] [{report_label}] Database logging completed")
        except Exception as db_error:
            log_debug(f"[SUMMARIZER] [{report_label}] Database logging failed: {db_error}")
        
        return result
        
    except Exception as e:
        log_debug(f"[SUMMARIZER] [{report_label}] EXCEPTION: {e}")
        import traceback
        log_debug(f"[SUMMARIZER] [{report_label}] Traceback:\n{traceback.format_exc()}")
        
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