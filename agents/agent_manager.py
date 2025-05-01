# agents/agent_manager.py
import os
import asyncio
import time
import re
from datetime import datetime
from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.agents import AzureAIAgent, AzureAIAgentThread, AzureAIAgentSettings
from agents.document_agent import DocumentAgent
from agents.analysis_agent import AnalysisAgent
from agents.compliance_agent import ComplianceAgent
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AgentManager:
    """Manager for the multi-agent system."""
    
    def __init__(self):
        """Initialize the agent manager."""
        self.document_agent = DocumentAgent()
        self.analysis_agent = AnalysisAgent()
        self.compliance_agent = ComplianceAgent()
        self.client = None
        self.thread = None
        self.initialized = False
        self.credential = None
    
    async def initialize(self):
        """Initialize the agent manager and all agents."""
        if self.initialized:
            return
        
        # Set required environment variables if not already set
        if not os.environ.get("AZURE_AI_AGENT_PROJECT_CONNECTION_STRING"):
            connection_string = os.getenv("AZURE_AI_AGENT_PROJECT_CONNECTION_STRING")
            model_deployment = os.getenv("AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME", "gpt-4o")
        
        # Create settings from environment variables
        ai_agent_settings = AzureAIAgentSettings()
        
        # Create the Azure AI Foundry client
        self.credential = DefaultAzureCredential(
            exclude_environment_credential=True,
            exclude_managed_identity_credential=True
        )
        
        # Use create_client without await - it returns a client directly
        self.client = AzureAIAgent.create_client(credential=self.credential)
        
        # Initialize the thread for conversation history
        self.thread = AzureAIAgentThread(client=self.client)
        
        # Initialize all agents with substantial delay between initializations
        print("Initializing Document Agent...")
        await self.document_agent.initialize(self.client)
        
        # Wait a substantial time before initializing the next agent to avoid rate limits
        print("Waiting 20 seconds before initializing the next agent...")
        await asyncio.sleep(20)
        
        print("Initializing Analysis Agent...")
        await self.analysis_agent.initialize(self.client)
        
        # Wait again
        print("Waiting 20 seconds before initializing the next agent...")
        await asyncio.sleep(20)
        
        print("Initializing Compliance Agent...")
        await self.compliance_agent.initialize(self.client)
        
        self.initialized = True

    async def process_query(self, query):
        """Process a user query through the multi-agent system."""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Step 1: Document Agent retrieves relevant regulations
            print("Getting relevant regulations from Document Agent...")
            
            # INSERT NEW CODE HERE - Replace the single document_response line with this:
            try:
                # Create a new thread if not provided
                if not self.thread:
                    try:
                        self.thread = AzureAIAgentThread(client=self.client)
                    except Exception as e:
                        print(f"Error creating thread: {e}")
                        # Fall back to direct agent calls without a thread
                        document_response = await self.document_agent.process(query, None)
                else:
                    document_response = await self.document_agent.process(query, self.thread.id)
            except Exception as e:
                print(f"Error with Document Agent: {e}")
                return f"Error retrieving OSHA regulations: {str(e)}"

            if not document_response or "No relevant OSHA regulations found" in document_response:
                return "I couldn't find any relevant OSHA regulations for your query. Please try a different question."
            
            # Display Document Agent's findings immediately
            print("\n" + "="*50)
            print("DOCUMENT AGENT FINDINGS:")
            print(document_response)
            print("="*50 + "\n")
            
            # Wait before the next agent call to avoid rate limits
            print("Waiting 90 seconds before Analysis Agent processing...")
            await asyncio.sleep(90)
            
            # Step 2: Analysis Agent interprets the regulations
            print("Getting interpretation from Analysis Agent...")
            analysis_response = await self.analysis_agent.process(query, document_response, self.thread.id)
            
            # Display Analysis Agent's findings immediately
            print("\n" + "="*50)
            print("ANALYSIS AGENT INTERPRETATION:")
            print(analysis_response)
            print("="*50 + "\n")
            
            # Wait before the final agent call
            print("Waiting 90 seconds before Compliance Agent processing...")
            await asyncio.sleep(90)
            
            # Step 3: Compliance Agent generates actionable guidance
            print("Getting compliance guidance...")
            
            # Try multiple times for the Compliance Agent with exponential backoff
            max_retries = 3
            retry_count = 0
            compliance_response = None
            
            while retry_count <= max_retries and compliance_response is None:
                try:
                    compliance_response = await self.compliance_agent.process(
                        query, document_response, analysis_response, self.thread.id
                    )
                    
                    # Display Compliance Agent's findings immediately
                    print("\n" + "="*50)
                    print("COMPLIANCE AGENT GUIDANCE:")
                    print(compliance_response)
                    print("="*50 + "\n")
                    
                except Exception as e:
                    error_message = str(e)
                    print(f"Error with Compliance Agent: {error_message}")
                    
                    if "Rate limit is exceeded" in error_message:
                        retry_count += 1
                        if retry_count > max_retries:
                            print(f"Exceeded maximum retries ({max_retries}) for Compliance Agent.")
                            compliance_response = f"Error processing query with Compliance Agent: {error_message}"
                            break
                        
                        # Extract wait time from error message
                        import re
                        wait_time_match = re.search(r"Try again in (\d+) seconds", error_message)
                        if wait_time_match:
                            wait_seconds = int(wait_time_match.group(1))
                            # Add buffer to the suggested wait time
                            wait_time = wait_seconds + 30
                        else:
                            # Exponential backoff with much longer initial wait
                            wait_time = 90 * (2 ** retry_count)  # 90, 180, 360 seconds
                        
                        print(f"Rate limit exceeded. Retry {retry_count}/{max_retries}. Waiting {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                    else:
                        print("Unexpected error with Compliance Agent. Aborting.")
                        compliance_response = f"Error generating compliance guidance."
                        break
            
            # Combine the responses for the final return value
            full_response = f"""DOCUMENT AGENT FINDINGS:
    {document_response}

    ANALYSIS AGENT INTERPRETATION:
    {analysis_response}

    COMPLIANCE AGENT GUIDANCE:
    {compliance_response if compliance_response else "Error generating compliance guidance."}

    DISCLAIMER: This OSHA compliance information is provided for general guidance only and is not a substitute for professional safety consultation or legal advice. Always consult with a qualified safety professional for specific compliance requirements.
    """
            
            return full_response
        except Exception as e:
            print(f"Error in processing query: {e}")
            return f"Error processing your query: {str(e)}"    

    async def generate_report(self, topic, query=None, report_data=None, email_to=None):
        """Generate a comprehensive compliance report and optionally email it."""
        # Check if report_data is a dictionary or a string
        if isinstance(report_data, dict):
            # Use provided report data
            pass
        else:
            # Extract information from last_response if available
            last_response = report_data  # The old parameter was last_response
            if last_response:
                document_response = last_response.split("DOCUMENT AGENT FINDINGS:")[1].split("ANALYSIS AGENT INTERPRETATION:")[0].strip() if last_response and "DOCUMENT AGENT FINDINGS:" in last_response else "No specific regulations retrieved."
                analysis_response = last_response.split("ANALYSIS AGENT INTERPRETATION:")[1].split("COMPLIANCE AGENT GUIDANCE:")[0].strip() if last_response and "ANALYSIS AGENT INTERPRETATION:" in last_response else ""
                compliance_response = last_response.split("COMPLIANCE AGENT GUIDANCE:")[1].split("DISCLAIMER:")[0].strip() if last_response and "COMPLIANCE AGENT GUIDANCE:" in last_response else "No specific compliance steps provided."
            else:
                document_response = "No specific regulations retrieved."
                analysis_response = ""
                compliance_response = "No specific compliance steps provided."
            
            # Create report data structure
            report_data = {
                "title": f"OSHA Compliance Report: {topic}",
                "timestamp": datetime.now().isoformat(),
                "content": {
                    "executive_summary": f"This report provides guidance on OSHA compliance for {topic} in nutraceutical manufacturing. It includes regulatory findings, interpretations, and recommended compliance steps.",
                    "regulatory_findings": document_response,
                    "compliance_steps": compliance_response,
                    "conclusion": "Implementing proper compliance measures is essential for workplace safety and regulatory compliance. Regular review and updates to your safety protocols are recommended."
                }
            }
        
        # Generate report (HTML and PDF)
        from utils.report_generator import ReportGenerator
        report_generator = ReportGenerator()
        report_result = report_generator.generate_report(report_data, generate_pdf=True)
        
        # Create email preview if requested
        email_preview = None
        if email_to:
            from utils.email_service import EmailService
            email_service = EmailService()
            email_subject = f"OSHA Compliance Report: {topic}"
            email_message = f"""
            <p>Please find attached the OSHA compliance report for {topic}.</p>
            <p>This report was generated in response to the query: "{query}"</p>
            <p>For questions or further clarification, please contact our safety team.</p>
            """
            email_result = email_service.send_report(email_to, email_subject, email_message, report_result.get('html_path'))
            email_preview = email_result.get('preview_path')
        
        result = {
            "success": True,
            "report": {
                "html_path": report_result.get('html_path'),
                "pdf_path": report_result.get('pdf_path'),
                "email_preview": email_preview,
                "emailed_to": email_to
            }
        }
            
        return result

    async def cleanup(self):
        """Clean up resources."""
        if not self.initialized:
            return
            
        try:
            print("Cleaning up resources...")
            # Clean up agents
            if hasattr(self.document_agent, 'agent_definition') and self.document_agent.agent_definition:
                try:
                    await self.client.agents.delete_agent(self.document_agent.agent_definition.id)
                    print("Document agent deleted.")
                except Exception as e:
                    print(f"Error cleaning up document agent: {e}")
            
            if hasattr(self.analysis_agent, 'agent_definition') and self.analysis_agent.agent_definition:
                try:
                    await self.client.agents.delete_agent(self.analysis_agent.agent_definition.id)
                    print("Analysis agent deleted.")
                except Exception as e:
                    print(f"Error cleaning up analysis agent: {e}")
                
            if hasattr(self.compliance_agent, 'agent_definition') and self.compliance_agent.agent_definition:
                try:
                    await self.client.agents.delete_agent(self.compliance_agent.agent_definition.id)
                    print("Compliance agent deleted.")
                except Exception as e:
                    print(f"Error cleaning up compliance agent: {e}")
            
            # Clean up thread
            if self.thread:
                try:
                    await self.thread.delete()
                    print("Thread deleted.")
                except Exception as e:
                    print(f"Error cleaning up thread: {e}")
            
            # No need to try closing the client anymore, as we're just setting it to None
            self.client = None
            self.initialized = False
            print("Cleanup completed.")
        except Exception as e:
            print(f"Error during cleanup: {e}")