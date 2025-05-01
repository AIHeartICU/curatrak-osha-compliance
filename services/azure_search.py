# services/azure_search.py
import json
import requests
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    HnswParameters,
    SearchField,
    VectorSearchProfile
)
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

class AzureSearchService:
    """Service for interacting with Azure Cognitive Search."""
    
    def __init__(self):
        """Initialize Azure Search service."""
        self.endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.key = os.getenv("AZURE_SEARCH_KEY")
        self.index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "osha-compliance-index")
        
        # Initialize search client
        self.search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=self.index_name,
            credential=AzureKeyCredential(self.key)
        )
    
    def create_search_index(self, delete_existing=False):
        """Create the search index with vector search capabilities.
        
        Args:
            delete_existing: Whether to delete the index if it already exists
            
        Returns:
            The created or updated search index
        """
        # Initialize index client
        index_client = SearchIndexClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.key)
        )
        
        # Check if index exists and delete if requested
        if delete_existing:
            try:
                index_client.get_index(self.index_name)
                index_client.delete_index(self.index_name)
                print(f"Index '{self.index_name}' deleted.")
            except Exception as e:
                if "ResourceNotFound" not in str(e):
                    raise
        
        # Define vector search capabilities
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="hnsw-config",
                    parameters=HnswParameters(
                        m=4,
                        ef_construction=400,
                        ef_search=500,
                        metric="cosine"
                    )
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="vector-profile",
                    algorithm_configuration_name="hnsw-config"
                )
            ]
        )
        
        # Define fields for the index
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="content", type=SearchFieldDataType.String, searchable=True),
            SimpleField(name="source", type=SearchFieldDataType.String, filterable=True, searchable=True),
            SimpleField(name="category", type=SearchFieldDataType.String, filterable=True, searchable=True),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                vector_search_dimensions=1536,  # OpenAI ada-002 embeddings have 1536 dimensions
                vector_search_profile_name="vector-profile"
            )
        ]
        
        # Create the index
        index = SearchIndex(name=self.index_name, fields=fields, vector_search=vector_search)
        result = index_client.create_or_update_index(index)
        print(f"Index {result.name} created successfully!")
        
        return result
    
    def upload_document(self, document):
        """Upload a document to the search index.
        
        Args:
            document: Document dictionary to upload
            
        Returns:
            Boolean indicating success or failure
        """
        try:
            result = self.search_client.upload_documents(documents=[document])
            return result[0].succeeded
        except Exception as e:
            print(f"Error uploading document: {e}")
            return False
    
    def search_documents(self, search_text, top=5):
        """Search documents using keyword search.
        
        Args:
            search_text: Text to search for
            top: Maximum number of results to return
            
        Returns:
            List of document dictionaries
        """
        try:
            results = self.search_client.search(
                search_text=search_text,
                select=["content", "source", "id"],
                top=top
            )
            
            documents = []
            for result in results:
                documents.append({
                    "source": result["source"],
                    "content": result["content"],
                    "id": result["id"]
                })
            
            return documents
        except Exception as e:
            print(f"Error searching documents: {e}")
            return []
    
    def vector_search(self, vector, top=5):
        """Search documents using vector search.
        
        Args:
            vector: The embedding vector to search with
            top: Maximum number of results to return
            
        Returns:
            List of document dictionaries
        """
        try:
            # Use the REST API for vector search
            headers = {
                "Content-Type": "application/json",
                "api-key": self.key
            }
            
            search_url = f"{self.endpoint}/indexes/{self.index_name}/docs/search?api-version=2023-11-01"
            search_payload = {
                "vectorQueries": [
                    {
                        "kind": "vector",
                        "vector": vector,
                        "fields": "content_vector",
                        "k": top,
                        "exhaustive": True
                    }
                ],
                "select": "content,source,id",
                "top": top
            }
            
            response = requests.post(
                search_url,
                headers=headers,
                json=search_payload
            )
            
            if response.status_code != 200:
                print(f"Vector search error: {response.status_code}")
                print(response.text)
                return []
            
            results = response.json().get('value', [])
            
            documents = []
            for result in results:
                documents.append({
                    "source": result.get("source", "Unknown"),
                    "content": result.get("content", ""),
                    "id": result.get("id", "")
                })
            
            return documents
        except Exception as e:
            print(f"Error in vector search: {e}")
            return []