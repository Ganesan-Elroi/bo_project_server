"""
OpenAI Summarizer with Template Support - IIS Compatible Version
Generates section-specific bullets based on detected template sections
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
        pass

conf = Config()
# Initialize OpenAI client
client = OpenAI(api_key=conf.OPENAI_API_KEY)


def generate_section_specific_summaries(documents, section_names, model, max_tokens=4000, ip_address=None,
                                        client_int_doc_ids=None, journal_doc_ids=None, internal_doc_id=None,
                                        client_id=0, cust_id=0, user_id=0, report_type=None):
    """
    Generate summaries organized by template sections
    
    Args:
        documents (list): List of processed documents
        section_names (list): List of section names from template
        model (str): OpenAI model to use
        max_tokens (int): Maximum output tokens
        ip_address (str): IP address for logging
        client_int_doc_ids: Client internal document IDs
        journal_doc_ids: Journal document IDs
        internal_doc_id: Internal document ID
        client_id (int): Client ID
        cust_id (int): Customer ID
        user_id (int): User ID
        report_type (str): Type of report ('SlutReport' or 'MonthlyReport')
        
    Returns:
        dict: {section_name: [bullets]} plus metadata
    """
    
    # Route to appropriate function based on report type
    if report_type == "MonthlyReport":
        return generate_monthly_report_summaries(
            documents, section_names, model, max_tokens, ip_address,
            client_int_doc_ids, journal_doc_ids, internal_doc_id,
            client_id, cust_id, user_id
        )
    else:
        # Default: Slutrapport (existing functionality)
        return generate_slutrapport_summaries(
            documents, section_names, model, max_tokens, ip_address,
            client_int_doc_ids, journal_doc_ids, internal_doc_id,
            client_id, cust_id, user_id
        )


def generate_slutrapport_summaries(documents, section_names, model, max_tokens=4000, ip_address=None,
                                   client_int_doc_ids=None, journal_doc_ids=None, internal_doc_id=None,
                                   client_id=0, cust_id=0, user_id=0):
    """
    Generate summaries for Slutrapport (Final Report)
    Original functionality - unchanged
    """
    language = 'svenska'
    
    log_debug(f"[SUMMARIZER] [SLUTRAPPORT] Generating AI summaries for {len(section_names)} sections")
    log_debug(f"[SUMMARIZER] Model: {model}, Max tokens: {max_tokens}")
    
    # Build document context
    doc_context = ""
    for idx, doc in enumerate(documents, 1):
        doc_name = doc.get('name', f'Document {idx}')
        doc_text = doc.get('text', '')[:6000]  # Limit per doc
        word_count = doc.get('text_info', {}).get('word_count', 0)
        
        doc_context += f"\n{'='*60}\n"
        doc_context += f"Document {idx}: {doc_name} ({word_count} words)\n"
        doc_context += f"{'='*60}\n"
        doc_context += f"{doc_text}\n\n"
    
    # Build sections list for prompt
    sections_list = "\n".join([f"- {name}" for name in section_names])
    
    prompt = f"""You are analyzing multiple documents to create a combined summary report.

DOCUMENTS:
{doc_context}

TEMPLATE SECTIONS (USE THESE EXACT NAMES AS JSON KEYS):
{sections_list}

TASK:
For EACH section above, extract and summarize relevant information from ALL documents.
Provide all summaries in {language}.

INSTRUCTIONS:
1. Create 5-10 comprehensive bullet points per section
2. Combine information from all documents into each section
3. Each bullet should be 10-30 words
4. Include specific dates, names, facts
5. **CRITICAL**: If no relevant information exists for a section, DO NOT include that section in the JSON response at all (omit it completely)
6. Highlight dates by wrapping them in {{{{HIGHLIGHT}}}}date{{{{/HIGHLIGHT}}}}

CRITICAL: Use the EXACT section names from the list above as JSON keys (copy them exactly, including Swedish characters).

RETURN FORMAT (JSON):
{{
  "Section Name 1": [
    "Bullet point 1 with details from documents",
    "Bullet point 2 combining info from multiple docs",
    ...
  ],
  "Section Name 2": [
    "Bullet point 1",
    ...
  ]
}}

**IMPORTANT**: Only include sections that have actual content from the documents. If a section has no relevant information, completely omit it from the JSON (don't include the key at all).

Remember:
- Use EXACT section names as keys (copy-paste from the list above)
- Combine ALL documents into each section
- Focus on facts and specific details
- Use clear, professional svenska
- 5-10 bullets per section (more if section is complex)
- **OMIT sections with no relevant information - don't include them in JSON at all**
"""

    return _execute_openai_request(
        prompt, model, max_tokens, section_names, documents, language,
        ip_address, client_int_doc_ids, journal_doc_ids, internal_doc_id,
        client_id, cust_id, user_id, "SLUTRAPPORT"
    )


def generate_monthly_report_summaries(documents, section_names, model, max_tokens=4000, ip_address=None,
                                      client_int_doc_ids=None, journal_doc_ids=None, internal_doc_id=None,
                                      client_id=0, cust_id=0, user_id=0):
    """
    Generate summaries for Monthly Report (Månadsrapport)
    ENHANCED: Works with ANY template structure, with or without sections
    """
    language = 'svenska'
    
    log_debug(f"[SUMMARIZER] [MONTHLY] Generating AI summaries")
    log_debug(f"[SUMMARIZER] Documents: {len(documents)}")
    log_debug(f"[SUMMARIZER] Template sections detected: {len(section_names)}")
    log_debug(f"[SUMMARIZER] Model: {model}, Max tokens: {max_tokens}")
    
    # Build journal entries context
    journal_context = ""
    for idx, doc in enumerate(documents, 1):
        doc_name = doc.get('name', f'Journal Entry {idx}')
        doc_text = doc.get('text', '')[:8000]  # Increased limit
        word_count = doc.get('text_info', {}).get('word_count', 0)
        created_date = doc.get('created_date', 'Unknown date')
        
        journal_context += f"\n{'='*60}\n"
        journal_context += f"Journal Entry {idx} - {created_date}\n"
        journal_context += f"({word_count} words)\n"
        journal_context += f"{'='*60}\n"
        journal_context += f"{doc_text}\n\n"
    
    # Build sections list
    if section_names and len(section_names) > 0:
        sections_list = "\n".join([f"- {name}" for name in section_names])
        has_template_sections = True
    else:
        sections_list = "NO TEMPLATE SECTIONS DETECTED"
        has_template_sections = False
    
    # Enhanced prompt for flexible matching
    prompt = f"""You are analyzing journal entries to create a monthly summary report (Månadsrapport).

JOURNAL ENTRIES:
{journal_context}

TEMPLATE SECTIONS:
{sections_list}

INSTRUCTIONS:
{"1. Use the EXACT template section names above as JSON keys" if has_template_sections else "1. Since no template sections exist, create appropriate sections based on journal content"}
2. Create 3-8 bullet points per section (10-30 words each)
3. Include specific dates, names, facts, and activities from journals
4. Highlight dates: {{{{HIGHLIGHT}}}}date{{{{/HIGHLIGHT}}}}
5. If NO relevant content exists for a section, OMIT it completely from JSON
6. Write in professional svenska
7. DO NOT include any instruction text or explanations - ONLY bullet points

{f'''MATCHING GUIDELINES (for template sections):
- "Känslo - och beteendemässig utveckling" / "Emotional development" → discussions about mood, feelings, behavior, psychological state
- "Utbildning" / "Education" → school activities, studies, classes, homework, academic progress
- "Familj och sociala relationer" / "Family and social relations" → family calls, visits, social interactions, relationships
- "Hälsa" / "Health" → meals, sleep, medical visits, daily routines, physical wellbeing
- "Andra viktiga händelser" / "Other important events" → events not fitting other categories''' if has_template_sections else '''SUGGESTED SECTIONS (since template has none):
- "Dagliga aktiviteter" → daily activities, routines, interactions
- "Skola och utbildning" → school-related content
- "Familjerelationer" → family contacts and visits
- "Hälsa och välmående" → health, meals, mood
- "Behandling och utveckling" → therapy, group sessions, personal development
- "Praktik och framtidsplanering" → internships, future planning'''}

CRITICAL RULES:
- {"Use EXACT section names from template as JSON keys (copy them exactly)" if has_template_sections else "Create clear, professional section names in svenska"}
- Combine information from ALL journal entries into each section
- Each bullet must be substantive with specific details
- Focus on facts, dates, actions, and outcomes
- OMIT sections with no relevant information

RETURN JSON FORMAT:
{{
  "{"Exact Section Name From Template" if has_template_sections else "Dagliga aktiviteter"}": [
    "Specific bullet point with details and {{{{HIGHLIGHT}}}}date{{{{/HIGHLIGHT}}}} if applicable",
    "Another bullet with concrete information from journals",
    "..."
  ],
  "{"Another Template Section" if has_template_sections else "Familjerelationer"}": [
    "Bullet point 1",
    "..."
  ]
}}

Remember: Only include sections with actual content. Empty sections must be completely omitted.
"""

    return _execute_openai_request(
        prompt, model, max_tokens, section_names, documents, language,
        ip_address, client_int_doc_ids, journal_doc_ids, internal_doc_id,
        client_id, cust_id, user_id, "MONTHLY"
    )


def _execute_openai_request(prompt, model, max_tokens, section_names, documents, language,
                            ip_address, client_int_doc_ids, journal_doc_ids, internal_doc_id,
                            client_id, cust_id, user_id, report_label):
    """
    Common function to execute OpenAI request and process response
    """
    try:
        start_time = time.time()
        
        log_debug(f"[SUMMARIZER] [{report_label}] Calling OpenAI API...")
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": f"You are an expert at analyzing documents and creating organized summaries in {language}. You extract information from multiple documents and organize it by predefined sections. You ONLY include sections in your response when relevant information exists - sections without content are completely omitted from the JSON output."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        
        elapsed = time.time() - start_time
        content = response.choices[0].message.content.strip()
        
        # Parse JSON
        section_bullets = json.loads(content)
        
        # Filter out any sections with empty or placeholder content
        filtered_bullets = {}
        placeholder_texts = ['', 'information saknas', 'information missing', 
                           'ingen information', 'no information', 'saknas', 'missing',
                           'n/a', 'none', 'nej', 'no']
        
        for section_name, bullets in section_bullets.items():
            # Check if bullets list is empty
            if not bullets:
                log_debug(f"[SUMMARIZER] [{report_label}] Filtering out '{section_name}': empty bullets list")
                continue
            
            # Check if bullets contain only whitespace or placeholder text
            has_real_content = False
            for bullet in bullets:
                bullet_text = str(bullet).strip().lower()
                if bullet_text and bullet_text not in placeholder_texts:
                    has_real_content = True
                    break
            
            if has_real_content:
                filtered_bullets[section_name] = bullets
            else:
                log_debug(f"[SUMMARIZER] [{report_label}] Filtering out '{section_name}': only placeholder content")
        
        # Use filtered bullets instead
        section_bullets = filtered_bullets
        
        # Calculate stats
        usage = response.usage
        total_bullets = sum(len(bullets) for bullets in section_bullets.values())
        
        log_debug(f"[SUMMARIZER] [{report_label}] [SUCCESS] Generated in {elapsed:.1f}s")
        log_debug(f"[SUMMARIZER] [{report_label}] [STATS] Tokens: {usage.total_tokens} | Bullets: {total_bullets}")
        log_debug(f"[SUMMARIZER] [{report_label}] [STATS] Sections with content: {len(section_bullets)}/{len(section_names)}")
        
        # Calculate costs
        INPUT_COST_PER_1M = 0.15
        OUTPUT_COST_PER_1M = 0.60
        
        input_cost = (usage.prompt_tokens / 1_000_000) * INPUT_COST_PER_1M
        output_cost = (usage.completion_tokens / 1_000_000) * OUTPUT_COST_PER_1M
        total_cost = input_cost + output_cost
        
        # Pricing For model
        if model not in ["gpt-4o-mini"]:
            pricing = model_pricing(model)
            if pricing:
                input_cost = (usage.prompt_tokens / 1_000_000) * pricing["inputCostPerM"]
                output_cost = (usage.completion_tokens / 1_000_000) * pricing["outputCostPerM"]
                total_cost = input_cost + output_cost
        
        log_debug(f"[SUMMARIZER] [{report_label}] [COST] Input: ${input_cost:.6f}, Output: ${output_cost:.6f}, Total: ${total_cost:.6f}")
        
        # Log to database
        log_data = {
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
        }
        log_to_database(log_data)
        log_debug(f"[SUMMARIZER] [{report_label}] Database logging completed")
        
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
        log_debug(f"[SUMMARIZER] [{report_label}] [ERROR] Error: {e}")
        import traceback
        log_debug(f"[SUMMARIZER] [{report_label}] [ERROR] Traceback:\n{traceback.format_exc()}")
        
        # Return empty dict (no sections)
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