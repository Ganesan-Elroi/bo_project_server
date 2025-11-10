#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
POST Method Handler for AI Summary Generation - IIS COMPATIBLE VERSION
WITH EXTERNAL FILE PROCESSING
"""

import sys
import os
import json
import time
from datetime import datetime

# Simple import suppression
import warnings
warnings.filterwarnings('ignore')

SUCCESSFUL_IMPORTS = True 

try:
    import pyodbc
    from save_logs import log_debug
    from convert_html_to_text import html_to_text, get_text_summary_info
    from openai_summarizer_bullets import process_documents_bullets
    
    # ===== ADD FILE PROCESSING IMPORTS =====
    from extractors.file_processor import process_file
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    from db_model import get_db_connection
    from utils.template_analyzer import analyze_template
    from utils.template_mapper import map_bullets_to_template
    from utils.openai_summarizer_with_template import generate_section_specific_summaries
except ImportError as e:
    SUCCESSFUL_IMPORTS = False
    IMPORT_ERROR_MSG = str(e)


def return_json(data, status_code=200):
    """Return JSON with proper headers for IIS"""
    status_messages = {200: "OK", 400: "Bad Request", 404: "Not Found", 500: "Internal Server Error"}
    
    try:
        log_debug(f"[RESPONSE] Returning status {status_code}")
    except:
        pass
    
    # Create JSON
    json_output = json.dumps(data, ensure_ascii=False, indent=2)
    
    try:
        # Headers as text
        sys.stdout.write(f"Status: {status_code} {status_messages.get(status_code, 'Unknown')}\r\n")
        sys.stdout.write("Content-Type: application/json; charset=utf-8\r\n")
        sys.stdout.write(f"Content-Length: {len(json_output.encode('utf-8'))}\r\n")
        sys.stdout.write("\r\n")
        sys.stdout.flush()
        
        # Body as text
        sys.stdout.write(json_output)
        sys.stdout.flush()
        
        log_debug(f"[RESPONSE] JSON sent successfully")
    except Exception as e:
        log_debug(f"[RESPONSE] Error sending response: {e}")
    
    sys.exit(0)

def read_post_data():
    """Read POST data"""
    log_debug("[READ_POST] Starting to read POST data")
    
    if os.environ.get('REQUEST_METHOD', '').upper() != 'POST':
        log_debug("[ERROR] Not POST method")
        return_json({"success": False, "error": "Only POST method supported"}, 400)

    content_length_str = os.environ.get('CONTENT_LENGTH')
    if not content_length_str:
        log_debug("[ERROR] No CONTENT_LENGTH")
        return_json({"success": False, "error": "No content length"}, 400)

    try:
        content_length = int(content_length_str)
        log_debug(f"[READ_POST] Content length: {content_length}")
        if content_length <= 0:
            log_debug(f"[ERROR] Invalid CONTENT_LENGTH: {content_length}")
            return_json({"success": False, "error": "Invalid content length"}, 400)
    except ValueError:
        log_debug(f"[ERROR] Invalid CONTENT_LENGTH format: {content_length_str}")
        return_json({"success": False, "error": "Invalid content length format"}, 400)
        
    # Read stdin as BINARY
    log_debug("[READ_POST] Reading from stdin...")
    try:
        post_data_raw = sys.stdin.buffer.read(content_length)
        post_data_str = post_data_raw.decode('utf-8')
        log_debug(f"[READ_POST] Read {len(post_data_str)} bytes")
        log_debug(f"[READ_POST] Received Data :  {post_data_str} ")
    except Exception as e:
        log_debug(f"[ERROR] Failed to read stdin: {e}")
        return_json({"success": False, "error": "Failed to read POST data"}, 400)
    
    if not post_data_str:
        log_debug("[ERROR] Empty POST data")
        return_json({"success": False, "error": "Empty POST data"}, 400)
        
    # Parse JSON
    try:
        data = json.loads(post_data_str)
        log_debug("[INFO] POST data parsed successfully. Received Data ", data)
        return data
    except json.JSONDecodeError as e:
        log_debug(f"[ERROR] JSON decode error: {str(e)}")
        return_json({"success": False, "error": f"Invalid JSON: {str(e)}"}, 400)

def is_html_content(content):
    """Check if content is HTML or a file path"""
    if not content:
        return False
    
    content_lower = content.strip().lower()
    html_indicators = ['<span', '<div', '<p>', '<table', '<html', '<body', '<!doctype']
    if any(indicator in content_lower for indicator in html_indicators):
        return True
    
    # ===== ADD FILE DETECTION =====
    file_extensions = ['.pdf', '.docx', '.doc', '.jpg', '.jpeg', '.png', '.gif']
    if any(content_lower.endswith(ext) for ext in file_extensions):
        return False
    
    if content_lower.startswith('<'):
        return True
    
    return False

def execute_sql_query(sql_query):
    """Execute SQL query"""
    if not pyodbc:
        raise Exception("pyodbc not available")

    start_time = time.time()
    log_debug(f"[SQL] Executing query...")
    
    try:
        conn = get_db_connection() 
        cursor = conn.cursor()
        cursor.execute(sql_query)
        
        columns = [column[0] for column in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            row_dict = {}
            for i, column in enumerate(columns):
                value = row[i]
                if isinstance(value, datetime):
                    row_dict[column] = value.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    row_dict[column] = value
            results.append(row_dict)
        
        cursor.close()
        conn.close()
        
        elapsed = time.time() - start_time
        log_debug(f"[SQL] Query completed in {elapsed:.2f}s, returned {len(results)} rows")
        
        return results
    except Exception as e:
        log_debug(f"[SQL] [ERROR] {str(e)}")
        raise Exception(f"Database error: {str(e)}")

def process_single_file(doc, base_path, ocr_language):
    log_debug(f"process single file function calling... base path {base_path}")
    """Process a single file document"""
    try:
        log_debug(f"[FILE_PROCESS] Processing file: {doc['name']}")
        result = process_file(
            filename=doc['content'],
            base_path=base_path,
            ocr_language=ocr_language,
            try_ocr_if_empty=True
        )
        
        if result['success']:
            text_info = get_text_summary_info(result['text'])
            log_debug(f"[FILE_PROCESS] Success: {doc['name']} - {text_info['word_count']} words")
            return {
                'success': True,
                'name': doc['name'],
                'text': result['text'],
                'created_date': doc['record'].get('CreatedDate', 'N/A'),
                'signed_date': doc['record'].get('SignedDate', 'N/A'),
                'source_type': 'file',
                'document_type': doc['type'],
                'file_type': result['file_type'],
                'extraction_method': result['extraction_method'],
                'text_info': text_info
            }
        else:
            log_debug(f"[FILE_PROCESS] Failed: {doc['name']}")
            return {'success': False}
    except Exception as e:
        log_debug(f"[FILE_PROCESS] Error processing {doc['name']}: {e}")
        return {'success': False}

def main():
    try:
        log_debug("="*70)
        log_debug("[START] AI Summary API Request")
        log_debug(f"[START] Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if not SUCCESSFUL_IMPORTS:
            log_debug(f"[ERROR] Import failed: {IMPORT_ERROR_MSG}")
            return_json({"success": False, "error": f"Missing dependencies: {IMPORT_ERROR_MSG}"}, 500)
        
        log_debug("[START] Imports successful")
        
        # Read POST data
        data = read_post_data()
        
        # Extract parameters
        user_id = data.get('user_id')
        cust_id = data.get('cust_id')
        client_id = data.get('client_id')
        sql_query = data.get('sql_query')
        doc_template_query = data.get('doc_template_query', None)
        openai_model = data.get('openai_model', 'gpt-4o-mini')
        max_tokens = data.get('max_tokens', 6000)
        
        # ===== ADD FILE PROCESSING PARAMETERS =====
        client_int_doc_ids = data.get('client_int_doc_ids', None)
        journal_doc_ids = data.get('journal_doc_ids', None)
        internal_doc_id = data.get('internal_doc_id', None)
        
        ip_address = os.environ.get('REMOTE_ADDR', '0.0.0.0')
        cust_code = data.get('cust_code')
        report_type= data.get('report_type' , 'SlutReport')
        
        log_debug("Report Type --->", report_type)
        # ===== ADD BASE PATH CONFIGURATION =====
        
        ocr_language = 'swe'
        
        if cust_code:
            base_path = f"D:/inetpub/Js/Customer/{cust_code}/Client Documents"

        else:   
            base_path = ""


        log_debug(f"[PARAMS] User: {user_id}, Customer: {cust_id}, Client: {client_id}")
        log_debug(f"[PARAMS] Model: {openai_model}, IP: {ip_address}")
        log_debug(f"[PARAMS] Base path: {base_path}, OCR language: {ocr_language}")

        if not sql_query:
            log_debug("[ERROR] Missing sql_query parameter")
            return_json({"success": False, "error": "Missing sql_query"}, 400)
        
        # Execute SQL
        log_debug("[STEP 1] Executing SQL query")
        db_results = execute_sql_query(sql_query)
        
        if not db_results:
            log_debug("[RESULT] No documents found")
            return_json({
                "success": True,
                "message": "No documents found",
                "document_counts": {"total": 0, "html_docs": 0, "file_docs": 0}
            })
        
        log_debug(f"[STEP 1] Found {len(db_results)} documents")
        
        # Process documents
        log_debug("[STEP 2] Processing documents")
        processed_documents = []
        html_docs = []
        file_docs = []  # ===== ADD FILE DOCS LIST =====
        
        for idx, record in enumerate(db_results, 1):
            doc_content = record.get('DocumentContent', '')
            doc_name = record.get('DocumentName', f'Document {idx}')
            doc_type = record.get('DocumentType', 'internal')
            
            if is_html_content(doc_content):
                html_docs.append({
                    'index': idx, 'name': doc_name, 'content': doc_content, 
                    'record': record, 'type': doc_type
                })
            else:
                # ===== ADD FILE DOCS PROCESSING =====
                file_docs.append({
                    'index': idx, 'name': doc_name, 'content': doc_content,
                    'record': record, 'type': doc_type
                })
        
        log_debug(f"[STEP 2] HTML docs: {len(html_docs)}, File docs: {len(file_docs)}")
        
        # Process HTML documents
        if html_docs:
            log_debug(f"[STEP 2A] Converting {len(html_docs)} HTML documents")
            for doc in html_docs:
                clean_text = html_to_text(doc['content'])
                text_info = get_text_summary_info(clean_text)
                processed_documents.append({
                    'name': doc['name'],
                    'text': clean_text,
                    'created_date': doc['record'].get('CreatedDate', 'N/A'),
                    'signed_date': doc['record'].get('SignedDate', 'N/A'),
                    'source_type': 'html',
                    'document_type': doc['type'],
                    'text_info': text_info
                })
                log_debug(f"[HTML_PROCESS] {doc['name']} - {text_info['word_count']} words")
        
        # ===== ADD FILE DOCUMENTS PROCESSING =====
        if file_docs:
            log_debug(f"[STEP 2B] Processing {len(file_docs)} file documents")
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_doc = {
                    executor.submit(process_single_file, doc, base_path, ocr_language): doc 
                    for doc in file_docs
                }
                
                for future in as_completed(future_to_doc):
                    result = future.result()
                    if result['success']:
                        processed_documents.append({
                            'name': result['name'],
                            'text': result['text'],
                            'created_date': result['created_date'],
                            'signed_date': result['signed_date'],
                            'source_type': result['source_type'],
                            'document_type': result['document_type'],
                            'file_type': result['file_type'],
                            'extraction_method': result['extraction_method'],
                            'text_info': result['text_info']
                        })
                        log_debug(f"[FILE_SUCCESS] {result['name']} - {result['text_info']['word_count']} words")
                    else:
                        log_debug(f"[FILE_FAILED] {future_to_doc[future]['name']}")
        
        log_debug(f"[STEP 2] Processed {len(processed_documents)} documents total")
        
        if not processed_documents:
            log_debug("[ERROR] No documents processed")
            return_json({"success": False, "error": "No documents processed"}, 500)
        
        # TEMPLATE MODE
        if doc_template_query:
            log_debug("[MODE] TEMPLATE MODE")
            
            template_results = execute_sql_query(doc_template_query)
            if not template_results:
                log_debug("[ERROR] Template not found")
                return_json({"success": False, "error": "Template not found"}, 404)
            
            template_html = template_results[0].get('chrDocumentText', '')
            if not template_html:
                log_debug("[ERROR] Template HTML empty")
                return_json({"success": False, "error": "Template HTML empty"}, 400)
            
            log_debug("[STEP 3] Analyzing template")
            # template_structure = analyze_template(template_html)
            # section_names = [s['name'] for s in template_structure['sections']]
            
            # NEW: Filter out metadata sections
            template_structure = analyze_template(template_html)
            metadata_keywords = ['månadsrapport', 'dagens datum', 'förnamn', 'efternamn', 'personnummer']
            section_names = [
                s['name'] for s in template_structure['sections'] 
                if not any(keyword in s['name'].lower() for keyword in metadata_keywords)
            ]
            log_debug(f"[STEP 4] Filtered to {len(section_names)} content sections (removed metadata)")

            
            log_debug(f"[STEP 4] Generating AI summaries for {len(section_names)} sections")
            ai_result = generate_section_specific_summaries(
                documents=processed_documents,
                section_names=section_names,
                model=openai_model,
                max_tokens=max_tokens,
                ip_address=ip_address,
                client_int_doc_ids=client_int_doc_ids,
                journal_doc_ids=journal_doc_ids,
                internal_doc_id=internal_doc_id,
                client_id=client_id,
                cust_id=cust_id,
                user_id=user_id,
                report_type=report_type
            )
            
            section_bullets = ai_result['section_bullets']
            
            log_debug("[STEP 5] Mapping bullets to template")
            filled_template_html = map_bullets_to_template(
                template_html=template_html,
                section_bullets_dict=section_bullets,
                template_structure=template_structure
            )
            
            response = {
                "success": True,
                "user_id": user_id,
                "cust_id": cust_id,
                "client_id": client_id,
                "template_mode": True,
                "filled_template_html": filled_template_html,
                "section_bullets": section_bullets,
                "template_info": {
                    "type": template_structure['template_type'],
                    "sections_detected": len(section_names),
                    "sections_mapped": len(section_bullets)
                },
                "document_counts": {
                    "total": len(db_results),
                    "html_docs": len(html_docs),
                    "file_docs": len(file_docs)  # ===== ADD FILE DOCS COUNT =====
                },
                "ai_usage": {
                    "tokens": ai_result.get('tokens', 0),
                    "processing_time": ai_result.get('time', 0),
                    "input_cost": ai_result.get('input_cost', 0),
                    "output_cost": ai_result.get('output_cost', 0),
                    "total_cost": ai_result.get('total_cost', 0)
                }
            }
            
            log_debug("[SUCCESS] Template mode completed")
            return_json(response)
            
        else:
            # BULLET MODE
            log_debug("[MODE] BULLET MODE")
            
            analysis_results = process_documents_bullets(
                processed_documents,
                chunk_size=5,
                ip_address=ip_address,
                model=openai_model,
                max_tokens=max_tokens,
                client_int_doc_ids=client_int_doc_ids,
                journal_doc_ids=journal_doc_ids,
                internal_doc_id=internal_doc_id,
                client_id=client_id,
                cust_id=cust_id,
                user_id=user_id
            )
            
            if analysis_results.get('status') == 'error':
                log_debug(f"[ERROR] AI processing failed: {analysis_results.get('error')}")
                return_json({"success": False, "error": analysis_results.get('error')}, 500)
            
            response = {
                "success": True,
                "user_id": user_id,
                "cust_id": cust_id,
                "client_id": client_id,
                "template_mode": False,
                "document_counts": {
                    "total": len(db_results),
                    "html_docs": len(html_docs),
                    "file_docs": len(file_docs)  # ===== ADD FILE DOCS COUNT =====
                },
                "summary": analysis_results.get('bullet_summaries', []),
                "ai_usage": {
                    "tokens": analysis_results.get('tokens', 0),
                    "processing_time": analysis_results.get('time', 0),
                    "input_cost": analysis_results.get('input_cost', 0),
                    "output_cost": analysis_results.get('output_cost', 0),
                    "total_cost": analysis_results.get('total_cost', 0)
                }
            }
            
            log_debug("[SUCCESS] Bullet mode completed")
            return_json(response)

    except Exception as e:
        log_debug(f"[FATAL ERROR] {str(e)}")
        import traceback
        log_debug(f"[TRACEBACK]\n{traceback.format_exc()}")
        return_json({"success": False, "error": "Internal server error"}, 500)


if __name__ == '__main__':
    main()