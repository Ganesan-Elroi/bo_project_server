import os
from datetime import datetime
import sys
import json
import tempfile

# Fix for Windows IIS - Set UTF-8 encoding for stdout
if sys.platform == 'win32':
	import codecs
	# Only wrap if buffer attribute exists (not already wrapped)
	if hasattr(sys.stdout, 'buffer'):
		sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')


LOG_FILE = os.path.join(tempfile.gettempdir(), 'ai_summary_debug.log')

def log_debug(message, also_print=False):
	"""
	Write debug messages to log file in TEMP folder
	
	Args:
		message (str): Message to log
		also_print (bool): If True, also print to console (useful for debugging)
	"""
	try:
		with open(LOG_FILE, 'a', encoding='utf-8') as f:
			timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
			log_line = f"[{timestamp}] {message}\n"
			f.write(log_line)
			
			# Also print if requested (useful during development)
			if also_print:
				print(f"DEBUG: {message}", file=sys.stderr)
				sys.stderr.flush()
	except Exception as e:
		# If logging fails, at least try to print the error
		try:
			print(f"LOGGING ERROR: {str(e)}", file=sys.stderr)
		except:
			pass  # Silently fail if even that doesn't work


def get_log_file_path():
	"""Return the current log file path"""
	return LOG_FILE


def clear_log():
	"""Clear the log file (useful for starting fresh)"""
	try:
		with open(LOG_FILE, 'w', encoding='utf-8') as f:
			f.write(f"Log cleared at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
			f.write("="*70 + "\n")
		return True
	except:
		return False