# openai_summarizer_bullets.py
"""
OpenAI Summarizer - Bullet Points Mode - IIS Compatible Version
Generates bullet point summaries without templates
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
                              internal_doc_id=None, client_id=0, cust_id=0, user_id=0):
    """
    Process documents and generate bullet point summaries
    
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
        dict: Results with bullet summaries and metadata
    """
    language = 'svenska'
    
    log_debug(f"[BULLET_SUMMARIZER] Processing {len(documents)} documents")
    log_debug(f"[BULLET_SUMMARIZER] Model: {model}, Chunk size: {chunk_size}")
    
    if not documents:
        log_debug("[BULLET_SUMMARIZER] [WARNING] No documents to process")
        return {
            'status': 'error',
            'error': 'No documents to process',
            'bullet_summaries': []
        }
    
    # Build document context
    doc_context = ""
    for idx, doc in enumerate(documents, 1):
        doc_name = doc.get('name', f'Document {idx}')
        doc_text = doc.get('text', '')[:8000]  # Limit per doc
        word_count = doc.get('text_info', {}).get('word_count', 0)
        
        doc_context += f"\n{'='*60}\n"
        doc_context += f"Document {idx}: {doc_name} ({word_count} words)\n"
        doc_context += f"{'='*60}\n"
        doc_context += f"{doc_text}\n\n"
    
    prompt = f"""You are analyzing multiple documents to create a comprehensive summary.

DOCUMENTS:
{doc_context}

TASK:
Create a well-organized bullet point summary of ALL the documents above in {language}.

INSTRUCTIONS:
1. Create 10-20 comprehensive bullet points covering ALL documents
2. Organize bullets by themes or topics
3. Each bullet should be 15-40 words
4. Include specific dates, names, facts, and important details
5. Highlight dates by wrapping them in {{{{HIGHLIGHT}}}}date{{{{/HIGHLIGHT}}}}
6. Combine related information from multiple documents
7. Focus on key facts, decisions, actions, and outcomes

RETURN FORMAT (JSON):
{{
  "summary_bullets": [
    "Bullet point 1 with important information",
    "Bullet point 2 with key details and dates",
    ...
  ]
}}

Remember:
- Combine information from ALL documents
- Focus on facts and specific details
- Use clear, professional svenska
- 10-20 bullets total
"""

    try:
        start_time = time.time()
        
        log_debug("[BULLET_SUMMARIZER] Calling OpenAI API...")
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": f"You are an expert at analyzing documents and creating comprehensive summaries in svenska."
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
        result = json.loads(content)
        bullets = result.get('summary_bullets', [])
        
        # Calculate stats
        usage = response.usage
        
        log_debug(f"[BULLET_SUMMARIZER] [SUCCESS] Generated in {elapsed:.1f}s")
        log_debug(f"[BULLET_SUMMARIZER] [STATS] Tokens: {usage.total_tokens} | Bullets: {len(bullets)}")
        
        # Calculate costs
        INPUT_COST_PER_1M = 0.15
        OUTPUT_COST_PER_1M = 0.60
        
        input_cost = (usage.prompt_tokens / 1_000_000) * INPUT_COST_PER_1M
        output_cost = (usage.completion_tokens / 1_000_000) * OUTPUT_COST_PER_1M
        total_cost = input_cost + output_cost
        
        # Pricing for model
        if model not in ["gpt-4o-mini"]:
            pricing = model_pricing(model)
            if pricing:
                input_cost = (usage.prompt_tokens / 1_000_000) * pricing["inputCostPerM"]
                output_cost = (usage.completion_tokens / 1_000_000) * pricing["outputCostPerM"]
                total_cost = input_cost + output_cost
        
        log_debug(f"[BULLET_SUMMARIZER] [COST] Input: ${input_cost:.6f}, Output: ${output_cost:.6f}, Total: ${total_cost:.6f}")
        
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
        log_debug("[BULLET_SUMMARIZER] Database logging completed")
        
        return {
            'status': 'success',
            'bullet_summaries': bullets,
            'tokens': usage.total_tokens,
            'input_tokens': usage.prompt_tokens,
            'output_tokens': usage.completion_tokens,
            'time': elapsed,
            'input_cost': round(input_cost, 6),
            'output_cost': round(output_cost, 6),
            'total_cost': round(total_cost, 6)
        }
        
    except Exception as e:
        log_debug(f"[BULLET_SUMMARIZER] [ERROR] Error: {e}")
        import traceback
        log_debug(f"[BULLET_SUMMARIZER] [ERROR] Traceback:\n{traceback.format_exc()}")
        
        return {
            'status': 'error',
            'error': str(e),
            'bullet_summaries': [],
            'tokens': 0,
            'input_tokens': 0,
            'output_tokens': 0,
            'time': 0
        }