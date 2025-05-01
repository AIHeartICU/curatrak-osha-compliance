# utils/email_service.py
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class EmailService:
    """Service for email-related functionality."""
    
    def __init__(self):
        """Initialize the Email Service with environment configuration."""
        self.from_email = os.getenv("FROM_EMAIL", "compliance@curatrak.com")
    
    def preview_email(self, to_email, subject, message, report_file_path=None):
        """Create a preview of what the email would look like.
        
        Args:
            to_email: Email address of the recipient
            subject: Email subject line
            message: HTML message body
            report_file_path: Optional path to a report file to be attached
            
        Returns:
            Path to the generated HTML email preview file
        """
        # Get report filename if provided
        attachment_name = os.path.basename(report_file_path) if report_file_path else "No attachment"
        
        # Create HTML preview of the email
        email_preview = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .email-preview {{ border: 1px solid #ccc; border-radius: 5px; padding: 20px; margin-bottom: 20px; }}
                .email-header {{ background-color: #f5f5f5; padding: 10px; border-bottom: 1px solid #eee; }}
                .email-body {{ padding: 20px 0; }}
                .email-attachment {{ background-color: #f9f9f9; padding: 10px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <h1>Email Preview</h1>
            <div class="email-preview">
                <div class="email-header">
                    <p><strong>From:</strong> {self.from_email}</p>
                    <p><strong>To:</strong> {to_email}</p>
                    <p><strong>Subject:</strong> {subject}</p>
                    <p><strong>Date:</strong> {datetime.now().strftime('%B %d, %Y %I:%M %p')}</p>
                </div>
                <div class="email-body">
                    {message}
                </div>
                <div class="email-attachment">
                    <p><strong>Attachment:</strong> {attachment_name}</p>
                </div>
            </div>
            <p><em>Note: This is a preview of the email. In a production environment, this email would be sent via SMTP.</em></p>
        </body>
        </html>
        """
        
        # Save the preview to a file
        preview_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'data', 
            'reports', 
            f'email_preview_{uuid.uuid4().hex[:8]}.html'
        )
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(preview_path), exist_ok=True)
        
        with open(preview_path, 'w', encoding='utf-8') as f:
            f.write(email_preview)
        
        return preview_path
    
    def send_report(self, to_email, subject, message, report_file_path=None):
        """Mock sending an email with the report attached.
        
        Args:
            to_email: Email address of the recipient
            subject: Email subject line
            message: HTML message body
            report_file_path: Optional path to a report file to be attached
            
        Returns:
            Dictionary with email sending status and preview information
        """
        # In mock mode, we just create a preview of what would be sent
        preview_path = self.preview_email(to_email, subject, message, report_file_path)
        
        return {
            'success': True,
            'preview_path': preview_path,
            'to_email': to_email,
            'note': 'Email preview generated (no actual email sent)'
        }