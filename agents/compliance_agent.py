# agents/compliance_agent.py
import os
import re
import asyncio
from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.agents import AzureAIAgent
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ComplianceAgent:
    """Agent for generating actionable OSHA compliance guidance."""
    
    def __init__(self):
        """Initialize the Compliance Agent."""
        self.agent = None
        self.agent_definition = None
    
    async def initialize(self, client):
        """Initialize the Azure AI Agent.
        
        Args:
            client: The Azure AI agent client instance
            
        Returns:
            The initialized agent
        """
        self.agent_definition = await client.agents.create_agent(
            model=os.getenv("AZURE_AI_FOUNDRY_GPT4O_DEPLOYMENT"),
            name="COMPLIANCE_AGENT",
            instructions="""You are a Compliance Agent specialized in OSHA compliance for nutraceutical manufacturing.
Your task is to provide actionable guidance for implementing OSHA compliance measures.

Focus on:
1. Providing step-by-step implementation guidance
2. Suggesting specific equipment, procedures, or training
3. Offering practical compliance strategies for nutraceutical manufacturers

Format your response with clear, actionable steps using plain text only. Do not use markdown formatting (**, ###, etc.). 
When mentioning citations like '29 CFR 1910.132', write them as plain text without bolding or other formatting. 
Use plain numbers for lists (1., 2., etc.).
"""
        )
        
        # Create a Semantic Kernel agent
        self.agent = AzureAIAgent(
            client=client,
            definition=self.agent_definition
        )
        
        return self.agent
    
    async def process(self, query, document_response, analysis_response, thread_id=None):
        """Process a query to generate compliance guidance.
        
        Args:
            query: The user's query about OSHA compliance
            document_response: Response from the Document Agent (may be string or dict)
            analysis_response: Response from the Analysis Agent (may be string or dict)
            thread_id: Optional thread ID for conversation history
            
        Returns:
            Dict with content and citations data
        """
        if not self.agent:
            raise ValueError("Agent not initialized. Call initialize() first.")
        
        try:
            # Extract content if responses are dictionaries
            if isinstance(document_response, dict) and "content" in document_response:
                doc_content = document_response["content"]
            else:
                doc_content = str(document_response)
                
            if isinstance(analysis_response, dict) and "content" in analysis_response:
                analysis_content = analysis_response["content"]
            else:
                analysis_content = str(analysis_response)
                
            # Create the prompt message
            prompt_messages = [
                f"Query: {query}\n\nOSHA Regulations:\n{doc_content}\n\nRegulation Analysis:\n{analysis_content}"
            ]
            
            # Get response from the agent
            response = await self.agent.get_response(thread_id=thread_id, messages=prompt_messages)
            
            # Extract the string content from the response
            if hasattr(response, 'content'):
                result = response.content
                if not isinstance(result, str):
                    result = str(result)
            else:
                result = str(response)
            
            # Clean up ANY markdown formatting - not just for citations
            # Remove all ** markdown
            result = re.sub(r'\*\*(.*?)\*\*', r'\1', result)
            
            # Handle CFR citations specifically
            result = re.sub(r'29 CFR (\d+\.\d+)', r'29 CFR \1', result)
            
            # Extract CFR citations for URL creation
            cfr_citations = re.findall(r'29 CFR (\d+\.\d+)', result)
            citations_data = []
            
            if cfr_citations:
                for citation in cfr_citations:
                    # Create citation data object
                    citations_data.append({
                        "text": f"29 CFR {citation}",
                        "type": "CFR",
                        "url": f"https://www.osha.gov/laws-regs/regulations/standardnumber/1910/{citation}"
                    })
                    
            # Return both the text and any found citations
            return {"content": result, "citations": citations_data}
            
        except Exception as e:
            print(f"Error processing query with Compliance Agent: {e}")
            return {"content": f"Error generating compliance guidance: {str(e)}", "citations": []}