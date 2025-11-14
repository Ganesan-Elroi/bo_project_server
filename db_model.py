# db_model.py
import pyodbc
import os
import pyodbc
from datetime import datetime
		



def get_db_connection():
    """Create and return a database connection using hardcoded credentials."""
    # For Live
    # driver = "ODBC Driver 17 for SQL Server"
    # server = "SRV298\\MSSQLSERVER2022"
    # database = "Js"
    # username = "sa"
    # password = "Qualitysql2024"
    
    
    # For Local connection
    driver = "ODBC Driver 17 for SQL Server"
    server = "localhost\\MSSQLSERVER01"
    database = "Js"
    username = "js_api_user"
    password = "SecurePassword123!"


    
    conn = pyodbc.connect(
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
    )
    return conn

def model_pricing(model_name: str):
	try:
		conn = get_db_connection()
		cursor = conn.cursor()

		cursor.execute("""
			SELECT inputCostPerM, outputCostPerM 
			FROM tblAiModels 
			WHERE chrModelName = ?
		""", (model_name,))

		row = cursor.fetchone()
		if row:
			input_cost_per_m, output_cost_per_m = row
		else:
			raise ValueError(f"[ERROR] Model '{model_name}' not found in tblAiModels")

		cursor.close()
		conn.close()

		return {
			"inputCostPerM": float(input_cost_per_m or 0),
			"outputCostPerM": float(output_cost_per_m or 0)
		}

	except Exception as e: 
		return {"inputCostPerM": 0.0, "outputCostPerM": 0.0}
	

def log_to_database(log_data):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
        INSERT INTO tblAiLogs (
            intCid,
            intUserId,
            intClientId,
            intDocCount,
            intPromptToken,
            intOutputToken,
            intTotalToken,
            chrModelName,
            intAPICalls,
            InputCost,
            OutputCost,
            TotalCost,
            IPAddress,
            ProcessingTime,
            dtCreatedDate,
            chrClientIntDocIds,
            chrJournalDocIds,
            intInternalDocId,
            chrReportType
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        values = (
            log_data.get('cid', 0),
            log_data.get('user_id', 0),
            log_data.get('client_id', 0),
            log_data.get('document_count', 0),
            log_data.get('prompt_tokens', 0),
            log_data.get('completion_tokens', 0),
            log_data.get('total_tokens', 0),
            log_data.get('model', ''),
            log_data.get('api_calls', 0),
            log_data.get('input_cost', 0.0),
            log_data.get('output_cost', 0.0),
            log_data.get('total_cost', 0.0),
            log_data.get('ip_address', ''),
            log_data.get('processing_time', 0.0),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            log_data.get('chrClientIntDocIds', ''),
            log_data.get('chrJournalDocIds', ''),
            log_data.get('intInternalDocId', None),   # FIXED
            log_data.get('chrReportType', '')
        )

        cursor.execute(sql, values)
        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
