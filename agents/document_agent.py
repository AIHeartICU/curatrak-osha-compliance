# agents/document_agent.py
import os
import re
import asyncio
from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.agents import AzureAIAgent
from semantic_kernel.functions.kernel_function_decorator import kernel_function
from services.azure_search import AzureSearchService
from utils.vector_utils import generate_embedding
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DocumentAgentPlugin:
    """Plugin for document retrieval functionality."""
    
    def __init__(self, search_service):
        self.search_service = search_service
    
    @kernel_function(description="Searches for OSHA regulations relevant to a query")
    async def search_regulations(self, query: str) -> str:
        """Search for OSHA regulations relevant to a query."""
        # Generate embedding for the query
        embedding = await generate_embedding(query)
        
        if not embedding:
            # Fall back to traditional search if embedding fails
            documents = self.search_service.search_documents(query)
        else:
            # Use vector search
            documents = self.search_service.vector_search(embedding)
        
        if not documents:
            return "No relevant OSHA regulations found."
        
        # Format the documents for the response
        formatted_documents = "\n\n".join([
            f"Source: {doc['source']}\nID: {doc['id']}\nContent: {doc['content']}"
            for doc in documents
        ])
        
        return formatted_documents

class DocumentAgent:
    """Agent for retrieving relevant OSHA regulations."""
    
    def __init__(self):
        """Initialize the Document Agent."""
        self.search_service = AzureSearchService()
        self.agent = None
        self.agent_definition = None
        self.plugin = None  # Store the plugin separately
    
    async def initialize(self, client):
        """Initialize the Azure AI Agent."""
        self.agent_definition = await client.agents.create_agent(
            model=os.getenv("AZURE_AI_FOUNDRY_GPT4O_DEPLOYMENT", "gpt-4o"),
            name="DOCUMENT_AGENT",
            instructions="""You are a Document Agent specialized in OSHA regulations for nutraceutical manufacturing.
Your task is to retrieve relevant OSHA regulations based on the user's query.

Focus on:
1. Identifying specific OSHA standards related to the query
2. Providing accurate citations (e.g., 29 CFR 1910.132)
3. Summarizing the key requirements from the regulations

Format your response with clear, actionable steps using plain text only. Do not use markdown formatting (**, ###, etc.). 
When mentioning citations like '29 CFR 1910.132', write them as plain text without bolding or other formatting. 
Use plain numbers for lists (1., 2., etc.).
"""
        )
        
        # Create plugin instance and store it
        self.plugin = DocumentAgentPlugin(self.search_service)
        
        # Create a Semantic Kernel agent
        self.agent = AzureAIAgent(
            client=client,
            definition=self.agent_definition,
            plugins=[self.plugin]
        )
        
        return self.agent
    
    async def process(self, query, thread_id=None):
        """Process a query to retrieve relevant OSHA regulations."""
        if not self.agent:
            raise ValueError("Agent not initialized. Call initialize() first.")
        
        try:
            # First, search for regulations related to the query - using the plugin directly
            documents = await self.plugin.search_regulations(query)
            
            # Then, ask the agent to analyze the regulations
            prompt_messages = [f"Analyze these OSHA regulations for the query: {query}\n\nRegulations:\n{documents}"]
            
            # Get the response from the agent
            response = await self.agent.get_response(thread_id=thread_id, messages=prompt_messages)
            
            # Extract the string content from the response
            if hasattr(response, 'content'):
                result = response.content
                if not isinstance(result, str):
                    result = str(result)
            else:
                result = str(response)
            
            # Clean up any unwanted formatting in CFR citations
            # Remove any markdown or special formatting
            result = re.sub(r'\*\*(.*?)\*\*', r'\1', result)
            
            # Now handle CFR citations specifically
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
            print(f"Error processing query with Document Agent: {e}")
            return {"content": "Error retrieving OSHA regulations.", "citations": []}