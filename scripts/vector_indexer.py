import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
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

# Load environment variables
load_dotenv()

def create_search_index(delete_existing=True):
    """Create a vector search index for OSHA regulations.
    
    Args:
        delete_existing: Whether to delete the index if it already exists
        
    Returns:
        The created search index or None if creation fails
    """
    # Search service details
    service_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "osha-compliance-index")
    key = os.getenv("AZURE_SEARCH_KEY")
   
    print(f"Service endpoint: {service_endpoint}")
    print(f"Index name: {index_name}")
    print(f"API key available: {'Yes' if key else 'No'}")
   
    try:
        # Create an index client
        print("Creating index client...")
        index_client = SearchIndexClient(
            endpoint=service_endpoint,
            credential=AzureKeyCredential(key)
        )
       
        # Check if index exists and delete if requested
        if delete_existing:
            try:
                print(f"Checking if index '{index_name}' exists...")
                existing_index = index_client.get_index(index_name)
                if existing_index:
                    print(f"Index '{index_name}' exists. Deleting...")
                    index_client.delete_index(index_name)
                    print(f"Index '{index_name}' deleted.")
            except Exception as e:
                if "ResourceNotFound" in str(e):
                    print(f"Index '{index_name}' doesn't exist. Creating new index.")
                else:
                    print(f"Error checking/deleting index: {e}")
                    raise
       
        # Define vector search capabilities
        print("Defining vector search configuration...")
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
        print("Defining index fields...")
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
        print("Creating index...")
        index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)
        result = index_client.create_or_update_index(index)
        print(f"Index {result.name} created or updated successfully!")
        return result
       
    except Exception as e:
        print(f"Error creating index: {e}")
        return None

if __name__ == "__main__":
    print("Starting vector index creation...")
    create_search_index(delete_existing=True)
    print("Script completed.")