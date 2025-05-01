# scripts/document_indexer.py
import os
import glob
import time
import io
import re
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI
import requests
import json
import PyPDF2

# Load environment variables
load_dotenv()

# Set up clients
search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
search_key = os.getenv("AZURE_SEARCH_KEY")
index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "osha-compliance-index")
search_client = SearchClient(
    endpoint=search_endpoint,
    index_name=index_name,
    credential=AzureKeyCredential(search_key)
)

# Set up OpenAI client using environment variables
openai_client = AzureOpenAI(
    api_key=os.getenv("AZURE_AI_FOUNDRY_API_KEY"),
    api_version=os.getenv("AZURE_AI_FOUNDRY_API_VERSION", "2023-05-15"),
    azure_endpoint=os.getenv("AZURE_AI_FOUNDRY_ENDPOINT")
)

# Use environment variable for embedding model
embedding_model = os.getenv("AZURE_AI_FOUNDRY_EMBEDDING_MODEL", "my-embedding-model")

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    print(f"Extracting text from {pdf_path}...")
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            num_pages = len(reader.pages)
            print(f"  PDF has {num_pages} pages")
           
            for page_num in range(num_pages):
                page = reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
                   
        return text
    except Exception as e:
        print(f"  Error extracting text from PDF: {e}")
        return ""

def chunk_document(text, chunk_size=1000, overlap=100):
    """Split document into overlapping chunks."""
    if not text:
        return []
   
    chunks = []
    start = 0
    text_length = len(text)
   
    while start < text_length:
        end = start + chunk_size
        # Adjust end to not cut words if possible
        if end < text_length:
            # Look for a space or newline to break at
            while end < text_length - 1 and not text[end].isspace():
                end += 1
       
        # Get chunk
        chunk = text[start:min(end, text_length)]
        chunks.append(chunk)
       
        # Move start position considering overlap
        start = end - overlap
   
    return chunks

def generate_embedding(text):
    """Generate embedding for text using Azure OpenAI."""
    try:
        print(f"Using embedding model: {embedding_model}")
        response = openai_client.embeddings.create(
            input=text,
            model=embedding_model
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

def sanitize_key(text):
    """Replace invalid characters in document keys with underscores."""
    return re.sub(r'[^a-zA-Z0-9_\-=]', '_', text)

def index_documents():
    """Index OSHA documents with vector embeddings."""
    # Directory with OSHA PDF documents
    docs_directory = os.path.join(os.getcwd(), "data", "regulations")
   
    # Get all PDF files
    pdf_files = glob.glob(os.path.join(docs_directory, "*.pdf"))
   
    if not pdf_files:
        print(f"No PDF files found in {docs_directory}")
        print(f"Current directory: {os.getcwd()}")
        print(f"Directory exists: {os.path.exists(docs_directory)}")
        return
       
    print(f"Found {len(pdf_files)} PDF files to process")
   
    # Process each file
    doc_count = 0
    for file_path in pdf_files:
        file_name = os.path.basename(file_path)
        print(f"Processing {file_name}...")
       
        # Extract text from PDF
        content = extract_text_from_pdf(file_path)
       
        if not content.strip():
            print(f"  No text extracted from {file_name}, skipping...")
            continue
           
        print(f"  Extracted {len(content)} characters of text")
       
        # Split into chunks
        chunks = chunk_document(content)
        print(f"  Split into {len(chunks)} chunks")
       
        # Process and index each chunk
        chunk_success = 0
        for i, chunk in enumerate(chunks):
            chunk_id = f"{sanitize_key(file_name)}-chunk-{i}"
           
            # Generate embedding
            print(f"  Generating embedding for chunk {i+1}/{len(chunks)}...")
            embedding = generate_embedding(chunk)
            if not embedding:
                print(f"  Skipping {chunk_id} - could not generate embedding")
                continue
           
            # Create document
            document = {
                "id": chunk_id,
                "content": chunk,
                "source": file_name,
                "category": "OSHA Regulation",
                "content_vector": embedding
            }
           
            # Upload to search index
            try:
                result = search_client.upload_documents(documents=[document])
                success = result[0].succeeded
                print(f"  Indexed {chunk_id}: {success}")
                if success:
                    chunk_success += 1
                    doc_count += 1
                # Small delay to avoid throttling
                time.sleep(0.5)
            except Exception as e:
                print(f"  Error indexing {chunk_id}: {e}")
       
        print(f"  Successfully indexed {chunk_success}/{len(chunks)} chunks from {file_name}")
   
    print(f"Indexing complete. Processed {doc_count} document chunks.")

if __name__ == "__main__":
    index_documents()