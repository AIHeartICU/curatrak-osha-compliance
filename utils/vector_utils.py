# utils/vector_utils.py
import os
import re
import asyncio
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure OpenAI
client = AzureOpenAI(
    api_key=os.getenv("AZURE_AI_FOUNDRY_API_KEY"),
    api_version=os.getenv("AZURE_AI_FOUNDRY_API_VERSION", "2023-05-15"),
    azure_endpoint=os.getenv("AZURE_AI_FOUNDRY_ENDPOINT")
)

async def generate_embedding(text):
    """Generate an embedding for the given text.
    
    Args:
        text: Text to generate embedding for
        
    Returns:
        Vector embedding or None if generation fails
    """
    try:
        embedding_model = os.getenv("AZURE_AI_FOUNDRY_EMBEDDING_MODEL", "my-embedding-model")
        print(f"Generating embedding using model: {embedding_model}")
        
        response = client.embeddings.create(
            input=text,
            model=embedding_model
        )
        
        # Extract the embedding vector
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

def sanitize_key(text):
    """Replace invalid characters in document keys with underscores.
    
    Args:
        text: Text to sanitize
        
    Returns:
        Sanitized text valid for use as a key
    """
    return re.sub(r'[^a-zA-Z0-9_\-=]', '_', text)