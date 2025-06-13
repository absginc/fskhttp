import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, send_file, jsonify
import subprocess
import tempfile
import logging
import re
from functools import wraps
from threading import Lock
import psutil
import queue
from datetime import datetime

# Load configuration from environment variables
class Config:
    # Server configuration
    HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    PORT = int(os.getenv('FLASK_PORT', '8080'))
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Threading configuration
    MAX_WORKERS = int(os.getenv('MAX_WORKERS', str(min(32, (os.cpu_count() or 1) + 4))))
    MAX_CONCURRENT_REQUESTS = int(os.getenv('MAX_CONCURRENT_REQUESTS', '50'))
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
    
    # GGWave paths
    GGWAVE_TO_FILE = os.getenv('GGWAVE_TO_FILE', '/ggwave/build/bin/ggwave-to-file')
    GGWAVE_FROM_FILE = os.getenv('GGWAVE_FROM_FILE', '/ggwave/build/bin/ggwave-from-file')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # Health check
    HEALTH_CHECK_ENABLED = os.getenv('HEALTH_CHECK_ENABLED', 'True').lower() == 'true'
    
    # File cleanup
    TEMP_FILE_CLEANUP_INTERVAL = int(os.getenv('TEMP_FILE_CLEANUP_INTERVAL', '300'))  # 5 minutes

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s'
)
logger = logging.getLogger(__name__)

# Global thread pool executor
executor = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS, thread_name_prefix="FSKWorker")

# Request counter and metrics
class Metrics:
    def __init__(self):
        self.lock = Lock()
        self.total_requests = 0
        self.active_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.encode_requests = 0
        self.decode_requests = 0
        self.start_time = datetime.now()
        
    def increment_total(self):
        with self.lock:
            self.total_requests += 1
            self.active_requests += 1
    
    def decrement_active(self, success=True, request_type='unknown'):
        with self.lock:
            self.active_requests -= 1
            if success:
                self.successful_requests += 1
            else:
                self.failed_requests += 1
            
            if request_type == 'encode':
                self.encode_requests += 1
            elif request_type == 'decode':
                self.decode_requests += 1
    
    def get_stats(self):
        with self.lock:
            uptime = (datetime.now() - self.start_time).total_seconds()
            return {
                'total_requests': self.total_requests,
                'active_requests': self.active_requests,
                'successful_requests': self.successful_requests,
                'failed_requests': self.failed_requests,
                'encode_requests': self.encode_requests,
                'decode_requests': self.decode_requests,
                'uptime_seconds': uptime,
                'requests_per_second': self.total_requests / uptime if uptime > 0 else 0
            }

metrics = Metrics()

def rate_limit_decorator(max_concurrent=Config.MAX_CONCURRENT_REQUESTS):
    """Decorator to limit concurrent requests"""
    semaphore = threading.Semaphore(max_concurrent)
    
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not semaphore.acquire(blocking=False):
                logger.warning(f"Rate limit exceeded. Active requests: {metrics.active_requests}")
                return jsonify({
                    "error": "Service temporarily overloaded",
                    "retry_after_seconds": 5,
                    "active_requests": metrics.active_requests
                }), 503
            
            try:
                metrics.increment_total()
                return f(*args, **kwargs)
            finally:
                semaphore.release()
        return wrapper
    return decorator

def timeout_decorator(timeout_seconds=Config.REQUEST_TIMEOUT):
    """Decorator to add timeout to requests"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            future = executor.submit(f, *args, **kwargs)
            try:
                return future.result(timeout=timeout_seconds)
            except Exception as e:
                logger.error(f"Request timeout or error: {str(e)}")
                return jsonify({
                    "error": "Request timeout or processing error",
                    "details": str(e)
                }), 504
        return wrapper
    return decorator

def safe_temp_file_cleanup():
    """Background task to clean up orphaned temp files"""
    def cleanup_worker():
        while True:
            try:
                time.sleep(Config.TEMP_FILE_CLEANUP_INTERVAL)
                temp_dir = tempfile.gettempdir()
                current_time = time.time()
                
                for filename in os.listdir(temp_dir):
                    if filename.startswith('tmp') and filename.endswith('.wav'):
                        filepath = os.path.join(temp_dir, filename)
                        try:
                            # Remove files older than 10 minutes
                            if current_time - os.path.getctime(filepath) > 600:
                                os.unlink(filepath)
                                logger.debug(f"Cleaned up orphaned temp file: {filepath}")
                        except Exception as e:
                            logger.debug(f"Could not clean up {filepath}: {e}")
            except Exception as e:
                logger.error(f"Error in cleanup worker: {e}")
    
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True, name="TempCleanup")
    cleanup_thread.start()

def parse_ggwave_output(raw_output):
    """Parse ggwave output and extract structured information"""
    
    # Define regex patterns to extract information
    regex_map = {
        'channels': r"\[\+\] Number of channels: (\d+)",
        'sample_rate': r"\[\+\] Sample rate: (\d+)",
        'bps': r"\[\+\] Bits per sample: (\d+)",
        'total_samples': r"\[\+\] Total samples: (\d+)"
    }
    
    # Extract decoded message
    message_pattern = r"\[\+\] Decoded message with length \d+: '(.*)'"
    
    # Initialize result dictionary
    result = {
        'success': True,
        'audio_info': {},
        'decoded_text': '',
        'message_length': 0,
        'processing_thread': threading.current_thread().name
    }
    
    try:
        # Extract audio information
        for key, pattern in regex_map.items():
            match = re.search(pattern, raw_output)
            if match:
                result['audio_info'][key] = int(match.group(1))
        
        # Extract decoded message
        message_match = re.search(message_pattern, raw_output)
        if message_match:
            decoded_text = message_match.group(1)
            result['decoded_text'] = decoded_text
            result['message_length'] = len(decoded_text)
        else:
            # Fallback: try to find any text between single quotes
            fallback_pattern = r"'([^']*)'"
            fallback_matches = re.findall(fallback_pattern, raw_output)
            if fallback_matches:
                # Take the longest match as it's likely the decoded message
                decoded_text = max(fallback_matches, key=len)
                result['decoded_text'] = decoded_text
                result['message_length'] = len(decoded_text)
        
        # Check if decoding was successful
        if "[+] Done" not in raw_output:
            result['success'] = False
            
    except Exception as e:
        logger.error(f"Error parsing ggwave output: {str(e)}")
        result['success'] = False
        result['error'] = f"Failed to parse output: {str(e)}"
    
    return result

@app.route('/encode', methods=['POST'])
@rate_limit_decorator()
def encode():
    """Encode text to FSK audio - thread-safe version"""
    start_time = time.time()
    output_file = None
    
    try:
        # Get text from the request (JSON or form data)
        data = request.get_json() or request.form
        text = data.get('text')
        if not text:
            logger.error("No text provided in request")
            metrics.decrement_active(success=False, request_type='encode')
            return jsonify({"error": "No text provided"}), 400

        logger.info(f"Encoding request: {len(text)} characters on thread {threading.current_thread().name}")

        # Create a temporary file for the output WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
            output_file = temp_wav.name

        # Run ggwave-to-file with -f without space
        cmd = [Config.GGWAVE_TO_FILE, f"-f{output_file}"]
        logger.debug(f"Running command: {' '.join(cmd)} with input length: {len(text)} bytes")
        
        result = subprocess.run(
            cmd,
            input=(text + "\n").encode('utf-8'),
            capture_output=True,
            text=False,
            timeout=Config.REQUEST_TIMEOUT
        )

        # Check if the output file exists and has content
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            processing_time = time.time() - start_time
            logger.info(f"Encoding successful in {processing_time:.2f}s")
            metrics.decrement_active(success=True, request_type='encode')
            return send_file(output_file, mimetype='audio/wav', as_attachment=True, download_name='encoded.wav')

        # Fallback: Try capturing stdout if file output failed
        logger.debug("Falling back to stdout capture")
        cmd = [Config.GGWAVE_TO_FILE]
        result = subprocess.run(
            cmd,
            input=(text + "\n").encode('utf-8'),
            capture_output=True,
            text=False,
            timeout=Config.REQUEST_TIMEOUT
        )

        if result.stdout and result.stdout.startswith(b"RIFF"):
            with open(output_file, 'wb') as f:
                f.write(result.stdout)
            processing_time = time.time() - start_time
            logger.info(f"Encoding successful (fallback) in {processing_time:.2f}s")
            metrics.decrement_active(success=True, request_type='encode')
            return send_file(output_file, mimetype='audio/wav', as_attachment=True, download_name='encoded.wav')
        else:
            logger.error(f"No valid WAV data generated")
            metrics.decrement_active(success=False, request_type='encode')
            return jsonify({"error": "Failed to encode text to audio"}), 500

    except subprocess.TimeoutExpired:
        logger.error("Encoding process timed out")
        metrics.decrement_active(success=False, request_type='encode')
        return jsonify({"error": "Encoding process timed out"}), 504
    except Exception as e:
        logger.error(f"Unexpected error during encoding: {str(e)}")
        metrics.decrement_active(success=False, request_type='encode')
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
    finally:
        # Clean up the temporary file
        if output_file and os.path.exists(output_file):
            try:
                os.unlink(output_file)
                logger.debug(f"Cleaned up temporary file: {output_file}")
            except Exception as e:
                logger.warning(f"Could not clean up temp file {output_file}: {e}")

@app.route('/decode', methods=['POST'])
@rate_limit_decorator()
def decode():
    """Decode FSK audio to text - thread-safe version"""
    start_time = time.time()
    input_file = None
    
    try:
        # Check if a file is provided
        if 'file' not in request.files:
            logger.error("No file provided in request")
            metrics.decrement_active(success=False, request_type='decode')
            return jsonify({"error": "No file provided"}), 400

        file = request.files['file']
        if not file.filename.endswith('.wav'):
            logger.error("File must be a WAV file")
            metrics.decrement_active(success=False, request_type='decode')
            return jsonify({"error": "File must be a WAV file"}), 400

        logger.info(f"Decoding request: {file.filename} on thread {threading.current_thread().name}")

        # Save the uploaded file temporarily
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
            input_file = temp_wav.name
            file.save(input_file)

        # Run ggwave-from-file to decode WAV to text
        cmd = [Config.GGWAVE_FROM_FILE, input_file]
        logger.debug(f"Running command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            timeout=Config.REQUEST_TIMEOUT
        )
        
        raw_output = result.stdout.strip()
        
        if result.returncode == 0:
            # Parse the output into structured JSON
            parsed_result = parse_ggwave_output(raw_output)
            processing_time = time.time() - start_time
            parsed_result['processing_time_seconds'] = round(processing_time, 3)
            
            if parsed_result['success']:
                logger.info(f"Decoding successful in {processing_time:.2f}s: '{parsed_result['decoded_text']}'")
                metrics.decrement_active(success=True, request_type='decode')
                return jsonify(parsed_result)
            else:
                logger.error(f"Parsing failed: {parsed_result.get('error', 'Unknown parsing error')}")
                metrics.decrement_active(success=False, request_type='decode')
                return jsonify({
                    "error": "Failed to parse decode output",
                    "details": parsed_result.get('error', 'Unknown parsing error'),
                    "processing_time_seconds": round(processing_time, 3)
                }), 500
        else:
            logger.error(f"Failed to decode audio: {result.stderr}")
            metrics.decrement_active(success=False, request_type='decode')
            return jsonify({
                "error": "Failed to decode audio",
                "stderr": result.stderr,
                "stdout": raw_output
            }), 500
            
    except subprocess.TimeoutExpired:
        logger.error("Decoding process timed out")
        metrics.decrement_active(success=False, request_type='decode')
        return jsonify({"error": "Decoding process timed out"}), 504
    except Exception as e:
        logger.error(f"Unexpected error during decoding: {str(e)}")
        metrics.decrement_active(success=False, request_type='decode')
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
    finally:
        # Clean up the temporary file
        if input_file and os.path.exists(input_file):
            try:
                os.unlink(input_file)
                logger.debug(f"Cleaned up temporary file: {input_file}")
            except Exception as e:
                logger.warning(f"Could not clean up temp file {input_file}: {e}")

@app.route('/health', methods=['GET'])
def health():
    """Comprehensive health check endpoint"""
    try:
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Service metrics
        service_stats = metrics.get_stats()
        
        # Check if ggwave binaries are accessible
        ggwave_status = {
            'to_file': os.path.exists(Config.GGWAVE_TO_FILE) and os.access(Config.GGWAVE_TO_FILE, os.X_OK),
            'from_file': os.path.exists(Config.GGWAVE_FROM_FILE) and os.access(Config.GGWAVE_FROM_FILE, os.X_OK)
        }
        
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "fskhttp",
            "version": "2.0.0",
            "thread_pool": {
                "max_workers": Config.MAX_WORKERS,
                "active_threads": threading.active_count()
            },
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2)
            },
            "service_metrics": service_stats,
            "ggwave_binaries": ggwave_status,
            "configuration": {
                "max_concurrent_requests": Config.MAX_CONCURRENT_REQUESTS,
                "request_timeout": Config.REQUEST_TIMEOUT,
                "log_level": Config.LOG_LEVEL
            }
        }
        
        # Determine overall health status
        if (cpu_percent > 90 or 
            memory.percent > 90 or 
            disk.percent > 90 or 
            not all(ggwave_status.values()) or
            service_stats['active_requests'] >= Config.MAX_CONCURRENT_REQUESTS):
            health_data["status"] = "degraded"
            return jsonify(health_data), 503
        
        return jsonify(health_data), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 503

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Endpoint for Prometheus-style metrics"""
    stats = metrics.get_stats()
    
    # Simple text format for Prometheus scraping
    prometheus_metrics = f"""# HELP fskhttp_requests_total Total number of requests
# TYPE fskhttp_requests_total counter
fskhttp_requests_total {stats['total_requests']}

# HELP fskhttp_requests_active Current active requests
# TYPE fskhttp_requests_active gauge
fskhttp_requests_active {stats['active_requests']}

# HELP fskhttp_requests_successful_total Total successful requests
# TYPE fskhttp_requests_successful_total counter
fskhttp_requests_successful_total {stats['successful_requests']}

# HELP fskhttp_requests_failed_total Total failed requests
# TYPE fskhttp_requests_failed_total counter
fskhttp_requests_failed_total {stats['failed_requests']}

# HELP fskhttp_encode_requests_total Total encode requests
# TYPE fskhttp_encode_requests_total counter
fskhttp_encode_requests_total {stats['encode_requests']}

# HELP fskhttp_decode_requests_total Total decode requests
# TYPE fskhttp_decode_requests_total counter
fskhttp_decode_requests_total {stats['decode_requests']}

# HELP fskhttp_uptime_seconds Service uptime in seconds
# TYPE fskhttp_uptime_seconds gauge
fskhttp_uptime_seconds {stats['uptime_seconds']}

# HELP fskhttp_requests_per_second Requests per second
# TYPE fskhttp_requests_per_second gauge
fskhttp_requests_per_second {stats['requests_per_second']}
"""
    
    return prometheus_metrics, 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    logger.info(f"Starting FSK HTTP Service with {Config.MAX_WORKERS} workers")
    logger.info(f"Max concurrent requests: {Config.MAX_CONCURRENT_REQUESTS}")
    logger.info(f"Request timeout: {Config.REQUEST_TIMEOUT}s")
    
    # Start background cleanup task
    safe_temp_file_cleanup()
    
    # Run the Flask app
    app.run(
        host=Config.HOST, 
        port=Config.PORT, 
        debug=Config.DEBUG,
        threaded=True
    )
