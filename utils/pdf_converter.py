# utils/pdf_converter.py
import os
import uuid
import shutil

class PDFConverter:
    """Utility for creating PDF preview (without external dependencies)."""
    
    @staticmethod
    def html_to_pdf(html_path):
        """Creates a PDF preview HTML page that simulates a PDF download.
        
        This is a fallback when WeasyPrint dependencies aren't available.
        
        Args:
            html_path: Path to the source HTML file
            
        Returns:
            Path to the generated PDF preview HTML file
            
        Raises:
            FileNotFoundError: If the source HTML file doesn't exist
        """
        if not os.path.exists(html_path):
            raise FileNotFoundError(f"HTML file not found: {html_path}")
        
        # Read the original HTML content
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Create a "PDF view" version
        pdf_preview_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>PDF Preview</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto; }}
                .pdf-toolbar {{ background: #f1f1f1; padding: 10px; margin-bottom: 20px; border-radius: 5px; display: flex; justify-content: space-between; }}
                .pdf-page {{ border: 1px solid #ddd; padding: 40px; box-shadow: 0 0 10px rgba(0,0,0,0.1); background: white; }}
                .download-btn {{ background: #007bff; color: white; padding: 8px 15px; border-radius: 4px; text-decoration: none; }}
                .disclaimer {{ background: #f8f9fa; padding: 10px; margin-top: 20px; font-size: 0.8em; color: #666; }}
            </style>
        </head>
        <body>
            <div class="pdf-toolbar">
                <h2>PDF Preview</h2>
                <a href="{os.path.basename(html_path)}" class="download-btn" download>Download Original HTML</a>
            </div>
            
            <div class="disclaimer">
                <p><strong>Note:</strong> This is a simulated PDF preview for demonstration purposes. 
                In a production environment, an actual PDF would be generated.</p>
            </div>
            
            <div class="pdf-page">
                {content}
            </div>
        </body>
        </html>
        """
        
        # Create PDF preview path
        pdf_preview_path = html_path.replace('.html', '_pdf_preview.html')
        
        # Write the PDF preview
        with open(pdf_preview_path, 'w', encoding='utf-8') as f:
            f.write(pdf_preview_content)
        
        return pdf_preview_path