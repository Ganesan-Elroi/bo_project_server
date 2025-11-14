# openai_summarizer_bullets.py
"""
OpenAI Summarizer - Bullet Points Mode with Dynamic Headers
Generates organized summaries with AI-generated section headers
Used when NO template is provided
"""

from openai import OpenAI
import os
import json
import time
from db_model import model_pricing, log_to_database
from utils.config import Config

conf = Config()

try:
    from save_logs import log_debug
    LOGGING_ENABLED = True
except:
    LOGGING_ENABLED = False
    def log_debug(msg):
        pass

# Initialize OpenAI client
client = OpenAI(api_key=conf.OPENAI_API_KEY)


def process_documents_bullets(documents, chunk_size=5, ip_address=None, model='gpt-4o-mini', 
                              max_tokens=4000, client_int_doc_ids=None, journal_doc_ids=None, 
                              internal_doc_id=None, client_id=0, cust_id=0, user_id=0, report_type=None):
    """
    Process diverse/unpredictable documents and generate organized summaries with dynamic headers
    
    This function is called when NO template is provided. The AI will:
    1. Analyze document content
    2. Identify main themes/topics
    3. Create appropriate section headers
    4. Organize bullets under those headers
    
    Args:
        documents (list): List of processed documents
        chunk_size (int): Number of documents to process at once
        ip_address (str): IP address for logging
        model (str): OpenAI model to use
        max_tokens (int): Maximum output tokens
        client_int_doc_ids: Client internal document IDs
        journal_doc_ids: Journal document IDs
        internal_doc_id: Internal document ID
        client_id (int): Client ID
        cust_id (int): Customer ID
        user_id (int): User ID
        
    Returns:
        dict: Results with organized sections (headers + bullets) and metadata
    """
    language = 'svenska'
    
    log_debug(f"[BULLET_SUMMARIZER] Processing {len(documents)} documents (NO TEMPLATE MODE)")
    log_debug(f"[BULLET_SUMMARIZER] Model: {model}, Max tokens: {max_tokens}")
    
    if not documents:
        log_debug("[BULLET_SUMMARIZER] [WARNING] No documents to process")
        return {
            'status': 'error',
            'error': 'No documents to process',
            'organized_summary': [],
            'html_output': ''
        }
    
    # Build document context
    doc_context = ""
    for idx, doc in enumerate(documents, 1):
        doc_name = doc.get('name', f'Document {idx}')
        doc_text = doc.get('text', '')[:8000]  # Limit per doc to stay within token limits
        word_count = doc.get('text_info', {}).get('word_count', 0)
        created_date = doc.get('created_date', 'Unknown date')
        
        doc_context += f"\n{'='*60}\n"
        doc_context += f"Document {idx}: {doc_name}\n"
        doc_context += f"Date: {created_date} | Words: {word_count}\n"
        doc_context += f"{'='*60}\n"
        doc_context += f"{doc_text}\n\n"
    
    # Prompt for AI to create dynamic headers and organized content
    prompt = f"""You are analyzing diverse documents to create a well-organized summary report in {language}.

DOCUMENTS:
{doc_context}

TASK:
Analyze ALL documents and create an organized summary with appropriate section headers based on the actual content.

INSTRUCTIONS:
1. Identify the 4-8 most important themes/topics across ALL documents
2. Create a descriptive Swedish section header for each theme (e.g., "HÄLSA OCH VÅRD", "UTBILDNING", "BETEENDE OCH UTVECKLING", "SOCIALA RELATIONER")
3. Under each header, provide 3-8 bullet points (15-40 words each)
4. Include specific dates, names, facts, and important details
5. Highlight dates by wrapping them: {{{{HIGHLIGHT}}}}date{{{{/HIGHLIGHT}}}}
6. Combine related information from multiple documents
7. Use professional svenska
8. Section headers should be in ALL CAPS and descriptive

RETURN FORMAT (JSON):
{{
  "sections": [
    {{
      "header": "DESCRIPTIVE SECTION NAME IN CAPS",
      "bullets": [
        "Bullet point 1 with specific details and facts",
        "Bullet point 2 with dates and information",
        "Bullet point 3..."
      ]
    }},
    {{
      "header": "ANOTHER RELEVANT SECTION",
      "bullets": [
        "Bullet point 1",
        "Bullet point 2"
      ]
    }}
  ]
}}

**CRITICAL REQUIREMENTS**:
- Create 4-8 sections based on actual document content
- Headers should reflect the ACTUAL topics found in the documents
- Each section must have 3-8 substantive bullet points
- All content must be in svenska
- Include ALL important information from the documents
- Do not create empty or generic sections
"""

    try:
        start_time = time.time()
        
        log_debug("[BULLET_SUMMARIZER] Calling OpenAI API for dynamic header generation...")
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": f"You are an expert at analyzing diverse documents and creating well-organized summaries with appropriate section headers in {language}. You identify key themes and organize information logically."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        
        elapsed = time.time() - start_time
        content = response.choices[0].message.content.strip()
        
        # Parse JSON response
        result = json.loads(content)
        sections = result.get('sections', [])
        
        # Calculate statistics
        total_bullets = sum(len(section.get('bullets', [])) for section in sections)
        usage = response.usage
        
        log_debug(f"[BULLET_SUMMARIZER] [SUCCESS] Generated in {elapsed:.1f}s")
        log_debug(f"[BULLET_SUMMARIZER] [STATS] Sections: {len(sections)} | Total bullets: {total_bullets}")
        log_debug(f"[BULLET_SUMMARIZER] [STATS] Tokens: {usage.total_tokens}")
        
        # Log section headers
        for section in sections:
            header = section.get('header', 'Unknown')
            bullet_count = len(section.get('bullets', []))
            log_debug(f"[BULLET_SUMMARIZER]   - {header}: {bullet_count} bullets")
        
        # Calculate costs
        INPUT_COST_PER_1M = 0.15
        OUTPUT_COST_PER_1M = 0.60
        
        input_cost = (usage.prompt_tokens / 1_000_000) * INPUT_COST_PER_1M
        output_cost = (usage.completion_tokens / 1_000_000) * OUTPUT_COST_PER_1M
        total_cost = input_cost + output_cost
        
        # Adjust pricing for different models
        if model not in ["gpt-4o-mini"]:
            pricing = model_pricing(model)
            if pricing:
                input_cost = (usage.prompt_tokens / 1_000_000) * pricing["inputCostPerM"]
                output_cost = (usage.completion_tokens / 1_000_000) * pricing["outputCostPerM"]
                total_cost = input_cost + output_cost
        
        log_debug(f"[BULLET_SUMMARIZER] [COST] Input: ${input_cost:.6f}, Output: ${output_cost:.6f}, Total: ${total_cost:.6f}")
        
        # Generate HTML output
        html_output = generate_html_from_sections(sections)
        
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
            'intInternalDocId': internal_doc_id,
            'chrReportType': report_type
        }
        log_to_database(log_data)
        log_debug("[BULLET_SUMMARIZER] Database logging completed")
        
        return {
            'status': 'success',
            'organized_summary': sections,  # Structured sections with headers
            'html_output': html_output,     # Ready-to-use HTML
            'section_count': len(sections),
            'bullet_count': total_bullets,
            'tokens': usage.total_tokens,
            'input_tokens': usage.prompt_tokens,
            'output_tokens': usage.completion_tokens,
            'time': elapsed,
            'input_cost': round(input_cost, 6),
            'output_cost': round(output_cost, 6),
            'total_cost': round(total_cost, 6)
        }
        
    except json.JSONDecodeError as e:
        log_debug(f"[BULLET_SUMMARIZER] [ERROR] JSON parsing error: {e}")
        log_debug(f"[BULLET_SUMMARIZER] [ERROR] Raw response: {content[:500]}")
        return {
            'status': 'error',
            'error': f'Failed to parse AI response: {str(e)}',
            'organized_summary': [],
            'html_output': ''
        }
        
    except Exception as e:
        log_debug(f"[BULLET_SUMMARIZER] [ERROR] Error: {e}")
        import traceback
        log_debug(f"[BULLET_SUMMARIZER] [ERROR] Traceback:\n{traceback.format_exc()}")
        
        return {
            'status': 'error',
            'error': str(e),
            'organized_summary': [],
            'html_output': '',
            'tokens': 0,
            'input_tokens': 0,
            'output_tokens': 0,
            'time': 0
        }


def generate_html_from_sections(sections):
    """
    Generate formatted HTML from sections with headers and bullets
    
    Args:
        sections (list): List of section dictionaries with 'header' and 'bullets'
        
    Returns:
        str: Formatted HTML string
    """
    html_parts = []
    
    html_parts.append('<div style="font-family: Verdana, Arial, sans-serif; max-width: 800px; margin: 20px;">')
    
    for section in sections:
        header = section.get('header', 'UNKNOWN SECTION')
        bullets = section.get('bullets', [])
        
        if not bullets:
            continue
        
        # Section header
        html_parts.append(f'<div style="margin-top: 25px; margin-bottom: 10px;">')
        html_parts.append(f'<strong style="font-size: 11pt;">{header}</strong>')
        html_parts.append('</div>')
        
        # Bullet list
        html_parts.append('<ul style="list-style-type: disc; padding-left: 25px; line-height: 1.8; margin: 10px 0;">')
        
        for bullet in bullets:
            # Handle date highlighting
            bullet_html = str(bullet).replace('{{HIGHLIGHT}}', '<span style="background-color: #fbbf24; padding: 2px 6px; border-radius: 3px;">')
            bullet_html = bullet_html.replace('{{/HIGHLIGHT}}', '</span>')
            
            html_parts.append(f'<li style="margin-bottom: 8px;">{bullet_html}</li>')
        
        html_parts.append('</ul>')
    
    html_parts.append('</div>')
    
    return '\n'.join(html_parts)