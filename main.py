# main.py
import os
import asyncio
import threading
import json
import uuid
import time
import traceback
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv

# Import the AgentManager
from agents.agent_manager import AgentManager

# Load environment variables
load_dotenv()

# Use environment variables instead of hardcoded values
# Default to "gpt-4o" if not specified in environment variables
model_deployment = os.getenv("AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME", "gpt-4o")

# Add this helper function at the top of your file after the imports

def extract_content_safely(obj):
    """
    Safely extract string content from various response types,
    including ChatMessageContent objects and fix malformed JSON structures.
    """
    if obj is None:
        return None
    
    # Check if it's a ChatMessageContent object
    if hasattr(obj, 'content') and callable(getattr(obj, 'content', None)):
        # Some ChatMessageContent objects have a content() method
        try:
            return obj.content()
        except:
            pass
    
    # Check if it has a content attribute
    if hasattr(obj, 'content') and not callable(getattr(obj, 'content', None)):
        content = str(obj.content)
        # Try to fix malformed JSON-like structures
        if content.startswith('{') and ('content' in content or 'citations' in content):
            try:
                # Attempt to convert single quotes to double quotes for proper JSON
                import json
                import re
                
                # Simple regex-based extraction if JSON parsing fails
                content_match = re.search(r"['\"]?content['\"]?\s*:\s*['\"]?(.*?)['\"]?\s*(?:,['\"]?citations|$)", content, re.DOTALL)
                if content_match:
                    extracted_content = content_match.group(1).strip()
                    # Clean up any trailing quotes or commas
                    extracted_content = re.sub(r"[,'\"]?\s*$", "", extracted_content)
                    return extracted_content
            except Exception as e:
                print(f"Error processing content: {e}")
                # Return the original content if fixing fails
                return content
        return content
    
    # Check if it has a text attribute
    if hasattr(obj, 'text'):
        return str(obj.text)
    
    # If it's a string, return it directly
    if isinstance(obj, str):
        return obj
    
    # Last resort - try to convert to string
    try:
        return str(obj)
    except:
        return "Content could not be extracted"

def extract_citations(text):
    """Extract CFR citations from text."""
    if not text:
        return []
        
    import re
    
    citations = []
    # Regex to find CFR citations
    citation_regex = r'29 CFR \d+\.\d+'
    
    # Find all matches
    matches = re.findall(citation_regex, text)
    for match in matches:
        cfr = match.replace('29 CFR ', '')
        citations.append({
            "text": match,
            "type": "CFR",
            "url": f"https://www.osha.gov/laws-regs/regulations/standardnumber/1910/{cfr}"
        })
    
    return citations

def clean_markdown_for_report(text):
    """Clean markdown and HTML from text for reports."""
    import re
    
    # Remove markdown headers (###)
    text = re.sub(r'#{1,6}\s+', '', text)
    
    # Remove markdown bold (**text**)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    
    # Remove markdown italic (*text*)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    
    # Remove HTML tags
    text = re.sub(r'</?[a-z][^>]*>', '', text)
    
    # Remove markdown list prefixes
    text = re.sub(r'^[\s-]*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s-]*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # Remove any trailing citation JSON objects
    text = re.sub(r',\s*"citations":\s*\[.*?\]\s*}*\s*$', '', text)
    
    # Remove markdown sections (like "### Section")
    text = re.sub(r'###\s+(.*?)$', r'\1', text, flags=re.MULTILINE)
    
    return text

def extract_document_response(text):
    """Extract and clean the document response section from the full response text."""
    if not text:
        return "No specific regulations retrieved."
        
    if "DOCUMENT AGENT FINDINGS:" in text and "ANALYSIS AGENT INTERPRETATION:" in text:
        doc_text = text.split("DOCUMENT AGENT FINDINGS:")[1].split("ANALYSIS AGENT INTERPRETATION:")[0].strip()
        return clean_markdown_for_report(doc_text)
    return "No specific regulations retrieved."

def extract_compliance_response(text):
    """Extract and clean the compliance response section from the full response text."""
    if not text:
        return "No specific compliance steps provided."
        
    if "COMPLIANCE AGENT GUIDANCE:" in text and "DISCLAIMER:" in text:
        comp_text = text.split("COMPLIANCE AGENT GUIDANCE:")[1].split("DISCLAIMER:")[0].strip()
        return clean_markdown_for_report(comp_text)
    return "No specific compliance steps provided."

# Initialize Flask app
app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

# Global variables to track state
agent_manager = AgentManager()
initialization_lock = threading.Lock()
is_initialized = False
initialization_thread = None
last_response = None
last_query = None

# Dictionary to store job status and results
global_responses = {}
jobs_lock = threading.Lock()

# Create directories for reports if they don't exist
os.makedirs('data/reports', exist_ok=True)

# Create a single event loop for the entire application
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def background_initialize():
    """Initialize the agent manager in a background thread."""
    global is_initialized
    
    print("Starting background initialization of agents...")
    
    try:
        # Run initialization using the global event loop
        loop.run_until_complete(agent_manager.initialize())
        
        with initialization_lock:
            is_initialized = True
        
        print("Agent system initialized and ready!")
    except Exception as e:
        print(f"Error during initialization: {e}")
        traceback.print_exc()

def ensure_initialized():
    """Make sure agents are initialized before processing requests."""
    global initialization_thread, is_initialized
    
    # Start initialization if not already started
    with initialization_lock:
        if initialization_thread is None:
            initialization_thread = threading.Thread(target=background_initialize)
            initialization_thread.daemon = True
            initialization_thread.start()
    
    # For API requests, wait for initialization to complete if needed
    if not is_initialized:
        print("Waiting for agent initialization to complete before processing request...")
        initialization_thread.join()

# Define the compliance phase processing function
def process_compliance_phase(job_id):
    """Process the compliance phase for a given job_id."""
    try:
        with jobs_lock:
            if job_id not in global_responses:
                print(f"Job {job_id} not found for compliance phase processing")
                return
            
            job_data = global_responses[job_id]
            user_message = last_query  # Use the global last query
            document_response_text = job_data.get('document_response', '')
            analysis_response_text = job_data.get('analysis_response', '')
        
        print(f"Starting compliance phase for job {job_id}")
        
        # Create document and analysis response objects if needed
        # This is a simple placeholder - adjust based on your actual agent structure
        document_response = document_response_text
        analysis_response = analysis_response_text
        
        # Process with Compliance Agent
        compliance_response = loop.run_until_complete(agent_manager.compliance_agent.process(
            user_message, document_response, analysis_response, 
            agent_manager.thread.id if agent_manager.thread else None
        ))
        compliance_response_text = extract_content_safely(compliance_response)

        # Create full response with all three agent outputs
        full_response = f"""DOCUMENT AGENT FINDINGS:
{document_response_text}

ANALYSIS AGENT INTERPRETATION:
{analysis_response_text}

COMPLIANCE AGENT GUIDANCE:
{compliance_response_text}

DISCLAIMER: This OSHA compliance information is provided for general guidance only and is not a substitute for professional safety consultation or legal advice. Always consult with a qualified safety professional for specific compliance requirements.
"""

        # Update with complete results
        with jobs_lock:
            global_responses[job_id] = {
                'status': 'complete',
                'document_response': document_response_text,
                'analysis_response': analysis_response_text,
                'compliance_response': compliance_response_text,
                'response': full_response,
                'created_at': job_data.get('created_at', time.time()),
                'completed_at': time.time(),
                'updated_at': time.time()
            }
            
            # Update last response for report generation
            global last_response
            last_response = full_response
            
        print(f"Compliance phase completed for job {job_id}")
        
    except Exception as e:
        print(f"Error in compliance phase: {e}")
        traceback.print_exc()
        
        # Store the error
        with jobs_lock:
            if job_id in global_responses:
                global_responses[job_id]['status'] = 'error'
                global_responses[job_id]['error'] = str(e)
                global_responses[job_id]['updated_at'] = time.time()

# Define the analysis phase processing function
def process_analysis_phase(job_id):
    """Process the analysis phase for a given job_id."""
    try:
        with jobs_lock:
            if job_id not in global_responses:
                print(f"Job {job_id} not found for analysis phase processing")
                return
            
            job_data = global_responses[job_id]
            user_message = last_query  # Use the global last query
            document_response_text = job_data.get('document_response', '')
        
        print(f"Starting analysis phase for job {job_id}")
        
        # Create document response object if needed
        # This is a simple placeholder - adjust based on your actual agent structure
        document_response = document_response_text
        
        # Process with Analysis Agent
        analysis_response = loop.run_until_complete(agent_manager.analysis_agent.process(
            user_message, document_response, agent_manager.thread.id if agent_manager.thread else None
        ))
        analysis_response_text = extract_content_safely(analysis_response)

        # Update with partial results
        with jobs_lock:
            global_responses[job_id] = {
                'status': 'partial',
                'phase': 'analysis',
                'document_response': document_response_text,
                'analysis_response': analysis_response_text,
                'created_at': job_data.get('created_at', time.time()),
                'updated_at': time.time()
            }
            
        print(f"Analysis phase completed for job {job_id}")
        
        # Wait a moment to allow frontend to update before changing phase
        time.sleep(5)
        
        # Update the phase to compliance before starting compliance agent
        with jobs_lock:
            if job_id in global_responses:
                global_responses[job_id].update({
                    'status': 'partial',
                    'phase': 'compliance',  # Explicitly mark as entering compliance phase
                    'document_response': document_response_text,
                    'analysis_response': analysis_response_text,
                    'updated_at': time.time()
                })
        
        # Continue with compliance phase
        process_compliance_phase(job_id)
        
    except Exception as e:
        print(f"Error in analysis phase: {e}")
        traceback.print_exc()
        
        # Store the error
        with jobs_lock:
            if job_id in global_responses:
                global_responses[job_id]['status'] = 'error'
                global_responses[job_id]['error'] = str(e)
                global_responses[job_id]['updated_at'] = time.time()

@app.route('/')
def home():
    """Home page route - doesn't wait for initialization."""
    return render_template('index.html')

@app.route('/reports/<path:filename>')
def serve_report(filename):
    """Serve report files."""
    return send_from_directory('data/reports', filename)

@app.route('/api/initialization-status')
def initialization_status():
    """Check if the agents are initialized."""
    return jsonify({
        'initialized': is_initialized
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """Process a chat message using a background task."""
    global last_query
    
    # Make sure agents are initialized before processing
    ensure_initialized()
    
    try:
        user_message = request.json.get('message', '')
        last_query = user_message
        
        # Create a unique job ID for this request
        job_id = str(uuid.uuid4())
        print(f"Created job ID: {job_id}")

        # Initialize job status
        with jobs_lock:
            global_responses[job_id] = {
                'status': 'processing',
                'created_at': time.time()
            }

        # Start processing in a background thread
        print("Starting background processing thread")
        processing_thread = threading.Thread(target=background_process, args=(job_id, user_message))
        processing_thread.daemon = True
        processing_thread.start()
        
        # Return immediately with the job ID
        print(f"Returning job ID: {job_id}")
        return jsonify({
            'success': True,
            'job_id': job_id,
            'status': 'processing'
        })
        
    except Exception as e:
        print(f"Error in chat route: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500        

def background_process(job_id, user_message):
    """Process a chat job in the background."""
    try:
        print(f"Starting background processing for job {job_id}")
        print(f"Processing query: {user_message}")
        
        # Process with Document Agent first
        try:
            document_response = loop.run_until_complete(agent_manager.document_agent.process(user_message, agent_manager.thread.id if agent_manager.thread else None))
            document_response_text = extract_content_safely(document_response)
            
            # Clean and standardize document response format 
            # (helps prevent malformed JSON issues)
            document_response_text = document_response_text.replace("'", "\"").replace("{content", "{\"content\"")
            
            # Attempt to extract citations and create a cleaner format
            citations = extract_citations(document_response_text)
            
            # Update with partial results from Document Agent
            with jobs_lock:
                global_responses[job_id] = {
                    'status': 'partial',
                    'phase': 'document',
                    'response': document_response_text,
                    'document_response': document_response_text,
                    'citations': citations,
                    'created_at': time.time(),
                    'updated_at': time.time()
                }

            print(f"Document Agent completed for job {job_id}")
            
            # IMPORTANT: Force a longer pause to ensure frontend displays document output first
            print("Pausing to allow frontend to display document results...")
            time.sleep(15)  # 15 second forced delay for frontend display
            
            # Wait before Analysis Agent processing to avoid rate limits
            print("Waiting before Analysis Agent processing...")
            time.sleep(90)  # Match the wait time in agent_manager.py
            
            # Process with Analysis Agent next
            analysis_response = loop.run_until_complete(agent_manager.analysis_agent.process(
                user_message, document_response, agent_manager.thread.id if agent_manager.thread else None
            ))
            analysis_response_text = extract_content_safely(analysis_response)
            analysis_citations = extract_citations(analysis_response_text)

            # Update with partial results from Analysis Agent                                 
            with jobs_lock:
                global_responses[job_id] = {
                    'status': 'partial',
                    'phase': 'analysis',
                    'document_response': document_response_text,
                    'document_citations': citations,
                    'analysis_response': analysis_response_text,
                    'analysis_citations': analysis_citations,
                    'created_at': time.time(),
                    'updated_at': time.time()
                }

            print(f"Analysis Agent completed for job {job_id}")
            
            # IMPORTANT: Add a longer pause to allow frontend to process the analysis phase
            print("Pausing to allow frontend to display analysis results...")
            time.sleep(15)  # 15 second forced delay for frontend display
            
            # Another smaller pause before changing phase
            time.sleep(8)  # Slightly longer pause to ensure frontend has time to process
            
            # Update phase to compliance before waiting for rate limits
            with jobs_lock:
                global_responses[job_id].update({
                    'status': 'partial',
                    'phase': 'compliance',  # Explicitly mark as entering compliance phase
                    'updated_at': time.time()
                })

            print("Waiting before Compliance Agent processing...")
            time.sleep(90)  # Wait time for rate limits

            print("Starting Compliance Agent processing...")
            
            # Finally process with Compliance Agent
            compliance_response = loop.run_until_complete(agent_manager.compliance_agent.process(
                user_message, document_response, analysis_response, 
                agent_manager.thread.id if agent_manager.thread else None
            ))
            compliance_response_text = extract_content_safely(compliance_response)
            compliance_citations = extract_citations(compliance_response_text)

            # Create full response with all three agent outputs using the text versions
            full_response = f"""DOCUMENT AGENT FINDINGS:
{document_response_text}

ANALYSIS AGENT INTERPRETATION:
{analysis_response_text}

COMPLIANCE AGENT GUIDANCE:
{compliance_response_text}

DISCLAIMER: This OSHA compliance information is provided for general guidance only and is not a substitute for professional safety consultation or legal advice. Always consult with a qualified safety professional for specific compliance requirements.
"""

            # Update with complete results from all agents                                              
            with jobs_lock:
                global_responses[job_id] = {
                    'status': 'complete',
                    'document_response': document_response_text,
                    'document_citations': citations,
                    'analysis_response': analysis_response_text,
                    'analysis_citations': analysis_citations,
                    'compliance_response': compliance_response_text,
                    'compliance_citations': compliance_citations,
                    'response': full_response,
                    'created_at': time.time(),
                    'completed_at': time.time(),
                    'updated_at': time.time()
                }                        

                # Update last response for report generation
                global last_response
                last_response = full_response
                
            print(f"Processing completed for job {job_id}")
            print(f"Response length: {len(full_response)}")
            
        except Exception as e:
            print(f"Error processing with agents: {e}")
            traceback.print_exc()
            
            # Store the error
            with jobs_lock:
                global_responses[job_id] = {
                    'status': 'error',
                    'error': str(e),
                    'completed_at': time.time(),
                    'updated_at': time.time()
                }
            
    except Exception as e:
        print(f"Error in background processing: {e}")
        traceback.print_exc()
        
        # Store the error
        with jobs_lock:
            global_responses[job_id] = {
                'status': 'error',
                'error': str(e),
                'completed_at': time.time(),
                'updated_at': time.time()
            }

@app.route('/api/chat/status/<job_id>', methods=['GET'])
def chat_status(job_id):
    """Check the status of a chat processing job."""
    print(f"Checking status for job: {job_id}")
    
    with jobs_lock:
        if job_id in global_responses:
            print(f"Found job {job_id}, status: {global_responses[job_id].get('status', 'unknown')}")
            
            # Clean up old completed jobs (optional)
            current_time = time.time()
            to_remove = []
            for jid, data in global_responses.items():
                if jid != job_id and 'completed_at' in data and current_time - data['completed_at'] > 3600:
                    to_remove.append(jid)
            
            for jid in to_remove:
                del global_responses[jid]
                
            # Return the requested job status
            return jsonify(global_responses[job_id])
        else:
            print(f"Job {job_id} not found")
            return jsonify({
                'status': 'not_found'
            }), 404

# Add this function to main.py
def get_relative_path(file_path):
    """Convert a full file path to a relative path for web access."""
    if not file_path:
        return None
    
    # Split the path and get just the filename
    import os
    filename = os.path.basename(file_path)
    return filename

@app.route('/api/generate-report', methods=['POST'])
def generate_report():
    """Generate a compliance report and optionally email it."""
    global last_response, last_query
    
    # Make sure agents are initialized before processing
    ensure_initialized()
    
    try:
        # Extract basic parameters from request
        topic = request.json.get('topic', '')
        query = request.json.get('query', '') or last_query
        email_to = request.json.get('email_to', None)
        
        # Use ONLY the global last_response variable since it's not sent from frontend
        response_text = last_response
        
        # Safety check - ensure response_text is not None
        if not response_text:
            return jsonify({
                'success': False,
                'error': "No response data available for report generation"
            }), 400
        
        # Extract citations from the response text
        citations = extract_citations(response_text)
        
        # Extract and clean document and compliance responses
        document_response = clean_markdown_for_report(extract_document_response(response_text))
        compliance_response = clean_markdown_for_report(extract_compliance_response(response_text))
        
        # Create report data with citations
        report_data = {
            "title": f"OSHA Compliance Report: {topic}",
            "timestamp": datetime.now().isoformat(),
            "content": {
                "executive_summary": f"This report provides guidance on OSHA compliance for {topic} in nutraceutical manufacturing. It includes regulatory findings, interpretations, and recommended compliance steps.",
                "regulatory_findings": document_response,
                "compliance_steps": compliance_response,
                "conclusion": "Implementing proper compliance measures is essential for workplace safety and regulatory compliance. Regular review and updates to your safety protocols are recommended."
            },
            "citations": citations
        }
        
        # Generate the report using the same event loop
        report_result = loop.run_until_complete(
            agent_manager.generate_report(topic, query, report_data, email_to)
        )
        
        # Convert full paths to relative paths
        if 'report' in report_result and report_result['report']:
            if 'html_path' in report_result['report']:
                report_result['report']['html_path'] = get_relative_path(report_result['report']['html_path'])
            if 'pdf_path' in report_result['report']:
                report_result['report']['pdf_path'] = get_relative_path(report_result['report']['pdf_path'])
        
        return jsonify({
            'success': True,
            'report': report_result.get('report', {})
        })
    
    except Exception as e:
        print(f"Error in generate_report endpoint: {e}")
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Add a simple health check endpoint
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'ok',
        'initialized': is_initialized,
        'active_jobs': len(global_responses)
    })

@app.route('/api/chat/recover', methods=['POST'])
def recover_chat_job():
    data = request.json
    job_id = data.get('job_id')
    force_phase = data.get('force_phase')
    
    if not job_id:
        return jsonify({"success": False, "error": "No job ID provided"})
    
    # Check if job exists
    with jobs_lock:
        if job_id not in global_responses:
            return jsonify({"success": False, "error": "Job not found"})
        
        job = global_responses[job_id]
    
    # If forcing a phase, update the job status
    if force_phase:
        if force_phase == 'compliance':
            # Skip to compliance phase if analysis is hanging
            with jobs_lock:
                if job["status"] == "partial" and job.get("phase") == "document":
                    job["phase"] = "analysis"  # Mark analysis as done
                    
            # Start compliance phase in background
            threading.Thread(target=process_compliance_phase, args=(job_id,)).start()
            return jsonify({"success": True, "message": "Forced compliance phase"})
    
    # Reset job timeouts or reconnect to background process
    with jobs_lock:
        if job["status"] == "error":
            job["status"] = "partial"
            job["error"] = None
            
    # Restart processing based on last known phase
    phase = job.get("phase", "document")
    if phase == "document":
        threading.Thread(target=process_analysis_phase, args=(job_id,)).start()
    elif phase == "analysis":
        threading.Thread(target=process_compliance_phase, args=(job_id,)).start()
            
    return jsonify({"success": True, "message": "Recovery initiated"})

# Add a debug endpoint
@app.route('/debug')
def debug_info():
    active_jobs = []
    with jobs_lock:
        for job_id, data in global_responses.items():
            status = data.get('status', 'unknown')
            created = data.get('created_at', 0)
            completed = data.get('completed_at', 0)
            
            job_info = {
                'job_id': job_id[:8] + '...',  # Truncated ID for readability
                'status': status,
                'age': time.time() - created if created else 0,
                'duration': completed - created if completed and created else 0
            }
            active_jobs.append(job_info)
    
    return jsonify({
        'initialized': is_initialized,
        'has_last_response': last_response is not None,
        'last_response_length': len(last_response) if last_response else 0,
        'has_last_query': last_query is not None,
        'active_jobs': active_jobs
    })

def clean_expired_jobs():
    while True:
        time.sleep(3600)  # Run once per hour
        current_time = time.time()
        with jobs_lock:
            to_remove = []
            for job_id, data in global_responses.items():
                if 'completed_at' in data and current_time - data['completed_at'] > 3600:
                    to_remove.append(job_id)
            
            for job_id in to_remove:
                del global_responses[job_id]  # Fixed: Changed from jid to job_id
        
        print(f"Cleaned up {len(to_remove)} expired jobs")

if __name__ == '__main__':
    # Start initialization in a background thread
    initialization_thread = threading.Thread(target=background_initialize)
    initialization_thread.daemon = True
    initialization_thread.start()
    
    # Start the job cleanup thread
    cleanup_thread = threading.Thread(target=clean_expired_jobs)
    cleanup_thread.daemon = True
    cleanup_thread.start()
    
    # Start the Flask server immediately
    print("Starting web server...")
    app.run(debug=False, port=5000, threaded=True)
