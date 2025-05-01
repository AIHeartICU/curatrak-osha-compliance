# utils/report_generator.py
import jinja2
import os
import uuid
import markdown
import re
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import PDFConverter
try:
    from utils.pdf_converter import PDFConverter
except ImportError:
    print("Warning: PDFConverter could not be imported")
    PDFConverter = None

class ReportGenerator:
    """Service for generating HTML and PDF compliance reports."""
    
    def __init__(self):
        """Initialize the Report Generator with template environment."""
        # Set up Jinja2 template environment
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'templates')
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
    
    def clean_markdown_content(self, text):
        """Clean markdown content for display in reports.
        
        Args:
            text: Markdown text to clean
            
        Returns:
            Cleaned text with markdown formatting removed
        """
        if not text:
            return ""
            
        # Remove markdown headers (###)
        text = re.sub(r'#{1,6}\s+', '', text)
        
        # Remove markdown bold (**text**)
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        
        # Remove markdown italic (*text*)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        
        # Remove HTML paragraph tags
        text = re.sub(r'</?p>', '', text)
        
        # Remove markdown list prefixes
        text = re.sub(r'^[\s-]*[-*+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[\s-]*\d+\.\s+', '', text, flags=re.MULTILINE)
        
        # Remove any trailing citation JSON objects
        text = re.sub(r',\s*"citations":\s*\[.*?\]\s*}*\s*$', '', text)
        
        return text
        
    def format_json_content(self, content):
        """Properly format JSON content for display in reports.
        
        Args:
            content: Content to format (may be dict, JSON string, or plain text)
            
        Returns:
            Formatted content suitable for HTML display
        """
        if not content:
            return ""
            
        # If content is already a dictionary
        if isinstance(content, dict) and 'content' in content:
            content_text = content['content']
            
            # Format citations if present
            if 'citations' in content:
                # Process citations...
                pass
                
            return content_text.replace("\\n", "<br>").replace("\n", "<br>")
            
        # If content is a string but looks like a JSON object
        if isinstance(content, str):
            # Check if it's JSON-like 
            if content.strip().startswith('{') and ('content' in content or 'content":' in content):
                try:
                    # Try to parse it as JSON
                    data = json.loads(content)
                    
                    # If successful and it has content field, use that
                    if isinstance(data, dict) and 'content' in data:
                        return self.format_json_content(data)  # Recursive call with parsed dict
                except json.JSONDecodeError:
                    # If strict JSON parsing fails, try with single quote replacement
                    try:
                        # Convert single quotes to double quotes for proper JSON parsing
                        content_json = content.replace("'", '"')
                        data = json.loads(content_json)
                        
                        if isinstance(data, dict) and 'content' in data:
                            return self.format_json_content(data)  # Recursive call with parsed dict
                    except Exception:
                        # If all JSON parsing fails, continue with text formatting
                        pass
        
        # Clean the content and format citations
        cleaned_content = self.clean_markdown_content(content)
        return self.format_citations(cleaned_content).replace("\\n", "<br>").replace("\n", "<br>")

    def format_citations(self, text):
        """Format CFR citations as clickable links in the HTML.
        
        Args:
            text: Text with CFR citations to format
            
        Returns:
            Text with citations replaced by HTML links
        """
        if not text:
            return text
            
        # First clean markdown and HTML
        text = self.clean_markdown_content(text)
            
        # Regex to find CFR citations
        citation_regex = r'(29 CFR \d+\.\d+)'
        
        def citation_replacer(match):
            citation = match.group(1)
            cfr = citation.replace('29 CFR ', '')
            url = f"https://www.osha.gov/laws-regs/regulations/standardnumber/1910/{cfr}"
            return f'<a href="{url}" class="citation" title="View regulation on OSHA website" target="_blank">{citation}</a>'
        
        # Replace citations with styled links
        return re.sub(citation_regex, citation_replacer, text)
    
    def generate_html_report(self, report_data):
        """Generate an HTML report from the report data.
        
        Args:
            report_data: Dictionary containing report content
            
        Returns:
            Path to the generated HTML report
        """
        template = self.env.get_template('report_template.html')
        
        # Convert markdown content to HTML if needed
        if report_data.get('content'):
            for key, value in report_data['content'].items():
                # Clean the content first
                cleaned_value = self.clean_markdown_content(value)
                
                # Process executive summary and conclusion 
                if key in ['executive_summary', 'conclusion']:
                    report_data['content'][key] = cleaned_value
                
                # Process regulatory findings with special JSON handling
                elif key == 'regulatory_findings':
                    formatted_value = self.format_json_content(value)
                    report_data['content'][key] = formatted_value
                
                # For compliance steps, also use JSON handling
                elif key == 'compliance_steps':
                    formatted_value = self.format_json_content(value)
                    report_data['content'][key] = formatted_value
                
                # For other keys, use standard markdown handling
                elif isinstance(value, str):
                    report_data['content'][key] = cleaned_value

        # Add formatted date
        report_data['formatted_date'] = datetime.fromisoformat(report_data['timestamp']).strftime('%B %d, %Y %I:%M %p')
        
        # Add CSS for citations to the template context
        citation_css = """
        .citation {
            font-weight: bold;
            color: #1B67B2;
            background-color: rgba(27, 103, 178, 0.1);
            padding: 2px 4px;
            border-radius: 3px;
            text-decoration: underline;
        }
        .citation:hover {
            background-color: rgba(27, 103, 178, 0.2);
        }
        """
        report_data['citation_css'] = citation_css
        
        # Generate HTML
        html_content = template.render(**report_data)
        
        # Create a unique filename
        filename = f"osha_report_{uuid.uuid4().hex[:8]}.html"
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'reports', filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return file_path
    
    def generate_report(self, report_data, generate_pdf=True):
        """Generate report in HTML and optionally PDF format.
        
        Args:
            report_data: Dictionary containing report content
            generate_pdf: Whether to generate a PDF version
            
        Returns:
            Dictionary with paths to the generated reports
        """
        # Generate HTML report
        html_path = self.generate_html_report(report_data)
        
        result = {
            'html_path': html_path
        }
        
        # Generate PDF if requested and PDFConverter is available
        if generate_pdf and PDFConverter is not None:
            try:
                pdf_path = PDFConverter.html_to_pdf(html_path)
                result['pdf_path'] = pdf_path
            except Exception as e:
                print(f"Warning: PDF generation failed: {e}")
                result['pdf_error'] = str(e)
        
        return result