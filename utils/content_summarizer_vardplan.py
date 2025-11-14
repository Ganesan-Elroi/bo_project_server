# utils/content_summarizer_vardplan.py
"""
Content Summarizer for Vårdplan
Generates structured summaries from journal entries for vårdplan sections
WITH DATABASE LOGGING AND MODEL PRICING - ENGLISH PROMPTS
"""

import json
import re
import time
from datetime import datetime

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


def highlight_dates(text):
    """Add highlight markers around dates"""
    # Match dates in format YYYY-MM-DD
    text = re.sub(
        r'\b(\d{4}-\d{2}-\d{2})\b',
        r'{{HIGHLIGHT}}\1{{/HIGHLIGHT}}',
        text
    )
    return text


def summarize_vardplan_content(journal_entries, template_sections, model='gpt-4o-mini',
                               max_tokens=3000, ip_address=None, client_int_doc_ids=None,
                               journal_doc_ids=None, internal_doc_id=None, client_id=None,
                               cust_id=None, user_id=None, report_type=None, client_name=None, 
                               client_pnr=None):
                               
    log_debug("[VARDPLAN_SUMMARIZER] Processing journal entries")
    log_debug(f"[VARDPLAN_SUMMARIZER] Template sections: {len(template_sections)}")
    log_debug(f"[VARDPLAN_SUMMARIZER] Model: {model}")
    
    # Build context from journal entries
    context_parts = []
    for entry in journal_entries:
        date = entry.get('date', 'Unknown date')
        content = entry.get('content', '')
        context_parts.append(f"[{date}]\n{content}")
    
    context = "\n\n---\n\n".join(context_parts)
    
    log_debug(f"[VARDPLAN_SUMMARIZER] Built context: {len(context)} characters")
    log_debug(f"[VARDPLAN_SUMMARIZER] Content sections: {len(template_sections)}")
    
    # Build sections list for prompt
    sections_list = "\n".join([f"- {section}" for section in template_sections])
    
    # Build prompt in ENGLISH
    prompt = f"""You are a professional social worker creating a care plan (vårdplan) summary from journal entries.

**JOURNAL ENTRIES:**
{context}

**CARE PLAN SECTIONS (use EXACT names as JSON keys):**
{sections_list}

**INSTRUCTIONS:**
1. Create 2-4 concise bullet points for EACH section above based on the journal entries
2. Include specific dates when relevant (format: YYYY-MM-DD)
3. Focus on:
   - Goals and planned interventions
   - Client's needs and situation
   - Concrete actions and follow-up
   - Responsible persons/contacts
4. Be concise and fact-based
5. If information is missing for a section, still write 1-2 relevant points based on available information
6. Write in Swedish (svenska)
7. Highlight dates using: {{{{HIGHLIGHT}}}}YYYY-MM-DD{{{{/HIGHLIGHT}}}}

**METADATA FIELDS (for table header - replace with provided values):**
- DOKUMENTNAMN: Replace with "{report_type}" (care plan name in 2 words, single line)
- Dagens datum: Replace with today's date
- Förnamn Efternamn: Replace with "{client_name}"
- Personnummer: Replace with "{client_pnr}"

**OUTPUT FORMAT (STRICT JSON ONLY):**
{{
  "Section Name 1": [
    "Bullet point 1 with relevant information",
    "Bullet point 2 with date if applicable {{{{HIGHLIGHT}}}}YYYY-MM-DD{{{{/HIGHLIGHT}}}}"
  ],
  "Section Name 2": [
    "Bullet point 1...",
    "Bullet point 2..."
  ]
}}

**CRITICAL RULES:**
- Respond ONLY with valid JSON
- No additional text before or after JSON
- Use EXACT section names from the list above as JSON keys
- Each bullet point should be 10-40 words
- Include dates, names, and specific activities
- Write professionally in Swedish

Return ONLY the JSON object:"""
    
    try:
        
        log_debug("[VARDPLAN_SUMMARIZER] Calling OpenAI API...")
        start_time = time.time()
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert social worker creating care plan summaries. You write concise, relevant summaries in Swedish based on journal entries. You ALWAYS respond with valid JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        
        elapsed = time.time() - start_time
        
        log_debug(f"[VARDPLAN_SUMMARIZER] API call completed in {elapsed:.2f}s")
        
        # Extract response
        response_text = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        response_text = re.sub(r'```json\s*', '', response_text)
        response_text = re.sub(r'```\s*', '', response_text)
        response_text = response_text.strip()
        
        log_debug(f"[VARDPLAN_SUMMARIZER] Response: {response_text[:200]}...")
        
        # Parse JSON
        section_bullets = json.loads(response_text)
        
        # Filter placeholder content
        filtered_bullets = {}
        placeholders = [
            '', 
            'information saknas', 
            'information saknas i dokumenten',
            'ingen information', 
            'saknas', 
            'n/a', 
            'none',
            'nej',
            'no',
            'information missing',
            'no information'
        ]
        
        for section_name, bullets in section_bullets.items():
            if not bullets:
                continue
            
            # Check if bullets have real content
            has_content = any(
                str(b).strip() and str(b).strip().lower() not in placeholders 
                for b in bullets
            )
            
            if has_content:
                # Highlight dates in all bullets
                filtered_bullets[section_name] = [highlight_dates(bullet) for bullet in bullets]
        
        section_bullets = filtered_bullets
        
        # Count bullets
        total_bullets = sum(len(bullets) for bullets in section_bullets.values())
        
        log_debug(f"[VARDPLAN_SUMMARIZER] Success: {len(section_bullets)} sections, {total_bullets} bullets")
        
        # Get token usage
        usage = response.usage
        log_debug(f"[VARDPLAN_SUMMARIZER] Tokens: {usage.total_tokens}")
        
        # Calculate costs
        INPUT_COST = 0.15 / 1_000_000  # gpt-4o-mini default
        OUTPUT_COST = 0.60 / 1_000_000
        
        input_cost = usage.prompt_tokens * INPUT_COST
        output_cost = usage.completion_tokens * OUTPUT_COST
        total_cost = input_cost + output_cost
        
        # Check for custom model pricing
        if model not in ["gpt-4o-mini"]:
            pricing = model_pricing(model)
            if pricing:
                input_cost = (usage.prompt_tokens / 1_000_000) * pricing["inputCostPerM"]
                output_cost = (usage.completion_tokens / 1_000_000) * pricing["outputCostPerM"]
                total_cost = input_cost + output_cost
                log_debug(f"[VARDPLAN_SUMMARIZER] Using custom pricing for {model}")
        
        log_debug(f"[VARDPLAN_SUMMARIZER] Cost: ${total_cost:.6f}")
        
        # Log to database
        log_to_database({
            'cid': cust_id,
            'user_id': user_id,
            'client_id': client_id,
            'document_count': len(journal_entries),
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
            'chrRerportType': report_type
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
        
    except json.JSONDecodeError as e:
        log_debug(f"[VARDPLAN_SUMMARIZER] JSON parse error: {e}")
        log_debug(f"[VARDPLAN_SUMMARIZER] Response was: {response_text}")
        
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
        
    except Exception as e:
        log_debug(f"[VARDPLAN_SUMMARIZER] ERROR: {e}")
        import traceback
        log_debug(f"[VARDPLAN_SUMMARIZER] Traceback:\n{traceback.format_exc()}")
        
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