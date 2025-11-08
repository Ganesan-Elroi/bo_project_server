"""
Modified ai_app_api.py - WITH TEMPLATE MAPPING INTEGRATION
This shows EXACTLY where to add the new code
"""

from flask import Flask, request, jsonify
import pyodbc
import os
from datetime import datetime

import sys
import json


# EXISTING IMPORTS
from convert_html_to_text import html_to_text, get_text_summary_info
from openai_summarizer_bullets import process_documents_bullets
from extractors.file_processor import process_file
from db_model import get_db_connection

# ===== NEW IMPORTS - ADD THESE 3 LINES =====
from utils.template_analyzer import analyze_template
from utils.template_mapper import map_bullets_to_template
from utils.openai_summarizer_with_template import generate_section_specific_summaries
# ============================================

# app = Flask(__name__)

# Handle IIS application path
APPLICATION_ROOT = os.environ.get('APPL_PHYSICAL_PATH', '/')
# if APPLICATION_ROOT != '/':
#     app.config['APPLICATION_ROOT'] = '/flaskai'


def return_json(data, status_code=200):
    """Helper function to return JSON response for CGI"""
    try:
        log_debug(f"return_json called with status {status_code}")
        
        status_messages = {
            200: "OK",
            400: "Bad Request",
            404: "Not Found", 
            500: "Internal Server Error"
        }
        
        # Send HTTP headers with CORS
        print(f"Status: {status_code} {status_messages.get(status_code, 'Unknown')}")
        print("Content-Type: application/json; charset=utf-8")
        print("Access-Control-Allow-Origin: *")  # Add CORS
        print("Access-Control-Allow-Methods: GET, POST, OPTIONS")
        print("Access-Control-Allow-Headers: Content-Type")
        print()
        sys.stdout.flush()
        
        # Send JSON body
        json_output = json.dumps(data, ensure_ascii=False)
        log_debug(f"Sending JSON body: {len(json_output)} characters")
        print(json_output)
        sys.stdout.flush()
        
        log_debug("return_json completed successfully")
        
    except Exception as e:
        log_debug(f"return_json error: {str(e)}")
        print("Status: 500 Internal Server Error")
        print("Content-Type: text/plain")
        print()
        print("Error generating response")
        sys.stdout.flush()

def is_html_content(content):
    """Detect if content is HTML or a file path"""
    if not content:
        return False
    
    content_lower = content.strip().lower()
    html_indicators = ['<span', '<div', '<p>', '<table', '<html', '<body', '<!doctype']
    if any(indicator in content_lower for indicator in html_indicators):
        return True
    
    file_extensions = ['.pdf', '.docx', '.doc', '.jpg', '.jpeg', '.png', '.gif']
    if any(content_lower.endswith(ext) for ext in file_extensions):
        return False
    
    if content_lower.startswith('<'):
        return True
    
    return False


def execute_sql_query(sql_query):
    """Execute SQL query and return results"""
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
        
        return results
        
    except Exception as e:
        raise Exception(f"Database error: {str(e)}")


def document_summary():
    # print("Content-type: text/html\n\n")
    # return "test"
    method = os.environ.get("REQUEST_METHOD", "GET")
    if method not in  ["POST"]:
        return_json({
            "success": False,
            "error": "Invalid method"
        }, 400)

    content_length = int(os.environ.get("CONTENT_LENGTH", 0))
    print(content_length)
        
    body = sys.stdin.read(content_length)        

    try:
        print("API Calling ...cls")
        data = json.loads(body)
        print("================")
        print("Received JSON Payload : ", data)
        print("================")
        
        if not data:
            return_json({
                "success": False,
                "error": "No JSON data provided"
            }, 400)
        
        user_id = data.get('user_id')
        cust_id = data.get('cust_id')
        client_id = data.get('client_id')
        sql_query = data.get('sql_query')
        summary_language = 'svenska'
        doc_template_query = data.get('doc_template_query', None)
        
        # ===== NEW PARAMETER - ADD THIS LINE =====
        openai_model = data.get('openai_model', 'gpt-4o-mini')
        max_tokens = data.get('max_tokens', 4000)
        client_int_doc_ids = data.get('client_int_doc_ids', None)
        journal_doc_ids    = data.get('journal_doc_ids', None)
        internal_doc_id    = data.get('internal_doc_id', None)
        # ==========================================
        
        # Validation (existing)
        if not user_id:
            return_json({"success": False, "error": "user_id is required"}, 400)
        if not cust_id:
            return_json({"success": False, "error": "cust_id is required"}, 400)
        if not client_id:
            return_json({"success": False, "error": "client_id is required"}, 400)
        if not sql_query:
            return_json({"success": False, "error": "sql_query is required"}, 400)
        
        print(f"\n{'='*70}")
        print(f"📥 Received request from .NET")
        print(f"   User ID: {user_id}")
        print(f"   Cust ID: {cust_id}")
        print(f"   Client ID: {client_id}")
        
        # ===== NEW - ADD THIS LINE =====
        print(f"   Template Mode: {'YES' if doc_template_query else 'NO'}")
        # ================================
        
        print(f"{'='*70}")
        
        ip_address = os.environ.get('REMOTE_ADDR', '0.0.0.0')
        
        # Execute SQL query (existing)
        print(f"\n🔍 Executing SQL query...")
        db_results = execute_sql_query(sql_query)
        
        if not db_results or len(db_results) == 0:
            return_json({
                "success": True,
                "user_id": user_id,
                "cust_id": cust_id,
                "client_id": client_id,
                "document_counts": {"total": 0, "html_docs": 0, "file_docs": 0},
                "summary": [],
                "message": "No documents found"
            })
        
        print(f"✅ Found {len(db_results)} documents")
        
        # Process documents (existing code - NO CHANGES HERE)
        print(f"\n📄 Processing documents...")
        processed_documents = []
        base_path = ''
        ocr_language = 'swe'
        
        html_docs = []
        file_docs = []
        
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
                file_docs.append({
                    'index': idx, 'name': doc_name, 'content': doc_content,
                    'record': record, 'type': doc_type
                })
        
        print(f"   HTML docs: {len(html_docs)}")
        print(f"   File docs: {len(file_docs)}")
        
        # Process HTML documents (existing)
        if html_docs:
            print(f"\n📄 Processing {len(html_docs)} HTML documents...")
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
                print(f"   ✓ {doc['name']} - {text_info['word_count']} words")
        
        # Process file documents (existing)
        if file_docs:
            print(f"\n📁 Processing {len(file_docs)} file documents...")
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def process_single_file(doc):
                try:
                    result = process_file(
                        filename=doc['content'],
                        base_path=base_path,
                        ocr_language=ocr_language,
                        try_ocr_if_empty=True
                    )
                    
                    if result['success']:
                        text_info = get_text_summary_info(result['text'])
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
                        print(f"   ❌ {doc['name']} - FAILED")
                        return {'success': False}
                except Exception as e:
                    print(f"   ❌ {doc['name']} - ERROR: {e}")
                    return {'success': False}
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_doc = {executor.submit(process_single_file, doc): doc for doc in file_docs}
                
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
                        print(f"   ✓ {result['name']} - {result['text_info']['word_count']} words")
        
        print(f"\n✅ Successfully processed {len(processed_documents)} documents")
        
        if not processed_documents:
            return_json({
                "success": False,
                "error": "No documents could be processed successfully"
            }, 500)
        
        logging_info = {
            'user_id': user_id,
            'cid': cust_id,
            'client_id': client_id
        }
        
        # ========== NEW CODE BLOCK - ADD THIS ENTIRE SECTION ==========
        # Check if template mode is enabled
        if doc_template_query:
            print(f"\n📋 TEMPLATE MODE ENABLED")
            print(f"{'='*70}")
            
            # Step 1: Fetch template from database
            print(f"🔍 Fetching template from database...")
            template_results = execute_sql_query(doc_template_query)
            
            if not template_results or len(template_results) == 0:
                return_json({
                    "success": False,
                    "error": "Template not found in database"
                }, 404)
            
            template_html = template_results[0].get('chrDocumentText', '')
            
            if not template_html:
                return_json({
                    "success": False,
                    "error": "Template HTML is empty"
                }, 400)
            
            print(f"   ✓ Template loaded ({len(template_html)} bytes)")
            
            # Step 2: Analyze template structure
            print(f"\n🔍 Analyzing template structure...")
            template_structure = analyze_template(template_html)
            
            print(f"   ✓ Template type: {template_structure['template_type']}")
            print(f"   ✓ Detected sections: {template_structure['total_sections']}")
            
            for i, section in enumerate(template_structure['sections'][:5], 1):
                print(f"      {i}. {section['name']}")
            if len(template_structure['sections']) > 5:
                print(f"      ... and {len(template_structure['sections']) - 5} more")
            
            # Step 3: Generate section-specific summaries with OpenAI
            print(f"\n🤖 Generating AI summaries for template sections...")
            
            section_names = [s['name'] for s in template_structure['sections']]
            # Get client IP address for logging
            ip_address = os.environ.get('REMOTE_ADDR', '0.0.0.0')
            
            ai_result = generate_section_specific_summaries(
                documents=processed_documents,
                section_names=section_names,
                model=openai_model,
                max_tokens=max_tokens,
                ip_address=ip_address,
                
                client_int_doc_ids=client_int_doc_ids,
                journal_doc_ids=journal_doc_ids,
                internal_doc_id=internal_doc_id,
                client_id=client_id, cust_id=cust_id, user_id=user_id
                
            )
            
            section_bullets = ai_result['section_bullets']
            
            # Step 4: Map bullets to template
            print(f"\n🗺️  Mapping bullets to template...")
            
            filled_template_html = map_bullets_to_template(
                template_html=template_html,
                section_bullets_dict=section_bullets,
                template_structure=template_structure
            )
            
            # Step 5: Build response
            response = {
                "success": True,
                "user_id": user_id,
                "cust_id": cust_id,
                "client_id": client_id,
                "template_mode": True,
                "filled_template_html": filled_template_html,
                "template_info": {
                    "type": template_structure['template_type'],
                    "sections_detected": len(section_names),
                    "sections_mapped": len(section_bullets)
                },
                "document_counts": {
                    "total": len(db_results),
                    "html_docs": len(html_docs),
                    "file_docs": len(file_docs)
                },
                "ai_usage": {
                    "tokens": ai_result['tokens'],
                    "processing_time": ai_result['time']
                }
            }
            
            print(f"\n{'='*70}")
            print(f"✅ TEMPLATE MODE - Request completed successfully")
            print(f"   Sections: {len(section_names)}")
            print(f"   Documents: {len(processed_documents)}")
            print(f"   Tokens: {ai_result['tokens']}")
            print(f"{'='*70}\n")
            
            return_json(response)
        # ========== END OF NEW CODE BLOCK ==========
        
        # ========== EXISTING CODE - NO CHANGES (runs if no template) ==========
        else:
            # Generate bullet summaries (existing flow)
            print(f"\n🤖 Generating AI summaries...")
            
            analysis_results = process_documents_bullets(
                processed_documents,
                chunk_size=5,
                ip_address=ip_address, 
                               
                model=openai_model,
                max_tokens=max_tokens,
                
                client_int_doc_ids=client_int_doc_ids,
                journal_doc_ids=journal_doc_ids,
                internal_doc_id=internal_doc_id,
                
                client_id=client_id, cust_id=cust_id, user_id=user_id
            )
            
            if analysis_results.get('status') == 'error':
                return_json({
                    "success": False,
                    "error": analysis_results.get('error', 'Analysis failed')
                }, 500)
            
            # Build response (existing)
            response = {
                "success": True,
                "user_id": user_id,
                "cust_id": cust_id,
                "client_id": client_id,
                "template_mode": False,
                "document_counts": {
                    "total": len(db_results),
                    "html_docs": len(html_docs),
                    "file_docs": len(file_docs)
                },
                "summary": analysis_results.get('bullet_summaries', [])
            }
            
            print(f"\n{'='*70}")
            print(f"✅ Request completed successfully")
            print(f"   Documents: {len(db_results)}")
            print(f"   Summaries: {len(response['summary'])}")
            print(f"{'='*70}\n")
            
            return_json(response)
        # ========== END OF EXISTING CODE ==========
    
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return_json({
            "success": False,
            "error": str(e)
        }, 500)


if __name__ == '__main__':
    # app.run(debug=True, host='0.0.0.0', port=5009)
    # app.run()
    document_summary()