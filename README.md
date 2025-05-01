# Curatrak: Multi-Agent OSHA Compliance System

A sophisticated multi-agent AI system that helps nutraceutical manufacturers navigate complex OSHA regulations, interpret requirements, and implement compliance measures.

## Problem Statement

Nutraceutical manufacturers face complex OSHA regulatory challenges:
- Technical regulations are extensive and difficult to navigate
- Specialized knowledge is required for interpretation
- Non-compliance risks include safety hazards and financial penalties

## Solution

Curatrak addresses these challenges through a sophisticated multi-agent AI system:

1. **Document Agent**: Retrieves relevant OSHA regulations using vector search technology
2. **Analysis Agent**: Interprets regulations specifically for nutraceutical context
3. **Compliance Agent**: Provides actionable implementation guidance

## Features

- Multi-agent orchestration using Azure AI Agent Service and Semantic Kernel
- Vector search for efficient regulatory information retrieval
- Production-ready rate limit handling with exponential backoff
- Rich HTML and PDF report generation with interactive citations

## Architecture

<img width="649" alt="image" src="https://github.com/user-attachments/assets/3a515fc3-d9aa-42a3-b280-3acf121a91dd" />


### Components
Built with Azure AI Foundry and Semantic Kernel 1.29.0, Curatrak features:

**Document Agent Pipeline**:
- User query processing with intent recognition
- Vector embedding generation for semantic matching
- Azure Cognitive Search integration with fine-tuned relevance
- Regulation retrieval and contextual summarization

**Analysis Agent Pipeline**:
- Regulatory language interpretation with domain-specific understanding
- Nutraceutical context adaptation for industry relevance
- Citation extraction and linking for complete traceability
- Confidence scoring for responsible AI implementation

**Compliance Agent Pipeline**:
- Implementation guidance generation with priority levels
- Resource recommendation based on company size and capabilities
- Step-by-step instruction creation with clear timelines
- Risk assessment integration

**Orchestration Layer**:
- Thread management for maintaining conversation context
- Production-ready rate limiting with exponential backoff
- Agent coordination and parallel processing capabilities
- Error handling and recovery mechanisms

## Technologies & Implementation

<img width="404" alt="image" src="https://github.com/user-attachments/assets/1afcabc1-ba11-4602-8b14-893a1290ded5" />


- **Azure AI Foundry with Semantic Kernel 1.29.0**: Orchestrates a three-agent architecture with specialized roles for document retrieval, analysis, and compliance guidance. Implements advanced conversational threading to maintain context across agent interactions.

- **Azure Cognitive Search with Vector Search**: Powers semantic retrieval of regulations using HNSW vector search algorithm (m=4, ef=500), enabling 1536-dimensional embeddings to find contextually relevant requirements beyond keyword matching.

- **Advanced Rate Limiting**: Implements exponential backoff with dynamic retry timing based on error message parsing. System automatically extracts wait times from API responses (e.g., "Try again in X seconds") and adds buffer periods for production reliability.

- **Asynchronous Processing Pipeline**: Built with Python's asyncio for efficient concurrent processing. Thread management ensures coherent multi-stage processing with graceful degradation when rate limits are encountered.

- **Document Processing & Storage**: Implements chunking with configurable overlap (1000/100) to optimize vector retrieval, with sanitized document keys for reliable storage in Azure Cognitive Search.

- **Interactive HTML/PDF Reporting**: Generates compliance reports with interactive CFR regulation citations that hyperlink to official OSHA documentation for verification.

## Setup and Installation

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the environment:
   - Windows: `venv\Scripts\activate`
   - Mac/Linux: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and add your credentials
6. Upload OSHA regulation PDFs to the `data/regulations` directory
7. Run the indexing scripts:python scripts/create_search_index.py python scripts/document_indexer.py

## Usage

1. Start the application: `python main.py`
2. Access the web interface at http://localhost:5000
3. Enter your query about OSHA compliance in nutraceutical manufacturing
4. Review the responses from each agent
5. Generate compliance reports as needed
