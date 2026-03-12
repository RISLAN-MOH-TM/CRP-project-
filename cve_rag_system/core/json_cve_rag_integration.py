#!/usr/bin/env python3
"""
JSON CVE RAG Integration for Penetration Testing System
Handles CVE JSON files from NVD/CVEList format
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# RAG dependencies
try:
    # Updated imports for langchain 0.1.0+
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import Chroma
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document
except ImportError as e:
    print(f"⚠️  RAG dependencies not installed or import error: {e}")
    print("Run: pip install langchain langchain-community chromadb sentence-transformers")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CVEJSONRAGIntegration:
    """
    RAG system for CVE JSON files (NVD/CVEList format)
    Efficiently processes and indexes CVE data for semantic search
    """
    
    def __init__(
        self,
        cve_directory: str = "C:\\Users\\User\\User\\Desktop\\mcp\\cves",
        vector_db_path: str = "./chroma_cve_db",
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        Initialize CVE JSON RAG system
        
        Args:
            cve_directory: Directory containing CVE JSON files
            vector_db_path: Path to store vector database
            chunk_size: Size of text chunks for embedding
            chunk_overlap: Overlap between chunks
        """
        self.cve_dir = Path(cve_directory)
        self.vector_db_path = vector_db_path
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize embeddings (free, local model)
        logger.info("Loading embedding model...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2"  # Fast, efficient, 384 dimensions
        )
        
        # Text splitter for chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", ", ", " ", ""]
        )
        
        self.vectorstore = None
        
    def parse_cve_json(self, json_path: str) -> Optional[Document]:
        """
        Parse a single CVE JSON file (CVE 5.0 format)
        
        Args:
            json_path: Path to CVE JSON file
            
        Returns:
            Document object or None if parsing fails
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                cve_data = json.load(f)
            
            # Extract CVE ID
            cve_id = cve_data.get('cveMetadata', {}).get('cveId', 'Unknown')
            
            # Extract state
            state = cve_data.get('cveMetadata', {}).get('state', 'Unknown')
            
            # Skip rejected/reserved CVEs if desired
            if state in ['REJECTED', 'RESERVED']:
                return None
            
            # Extract containers
            containers = cve_data.get('containers', {})
            cna = containers.get('cna', {})
            
            # Extract descriptions
            descriptions = cna.get('descriptions', [])
            description_text = ""
            for desc in descriptions:
                if desc.get('lang') == 'en':
                    description_text = desc.get('value', '')
                    break
            
            # Extract affected products
            affected = cna.get('affected', [])
            affected_products = []
            for item in affected:
                vendor = item.get('vendor', 'Unknown')
                product = item.get('product', 'Unknown')
                versions = item.get('versions', [])
                affected_products.append(f"{vendor} {product}")
            
            # Extract metrics (CVSS scores)
            metrics = cna.get('metrics', [])
            cvss_score = "Unknown"
            severity = "Unknown"
            for metric in metrics:
                if 'cvssV3_1' in metric:
                    cvss_score = metric['cvssV3_1'].get('baseScore', 'Unknown')
                    severity = metric['cvssV3_1'].get('baseSeverity', 'Unknown')
                    break
                elif 'cvssV3_0' in metric:
                    cvss_score = metric['cvssV3_0'].get('baseScore', 'Unknown')
                    severity = metric['cvssV3_0'].get('baseSeverity', 'Unknown')
                    break
            
            # Extract problem types (CWE)
            problem_types = cna.get('problemTypes', [])
            cwe_ids = []
            for pt in problem_types:
                for desc in pt.get('descriptions', []):
                    cwe_id = desc.get('cweId', '')
                    if cwe_id:
                        cwe_ids.append(cwe_id)
            
            # Extract references
            references = cna.get('references', [])
            reference_urls = [ref.get('url', '') for ref in references[:5]]  # Limit to 5
            
            # Extract dates
            date_published = cve_data.get('cveMetadata', {}).get('datePublished', '')
            date_updated = cve_data.get('cveMetadata', {}).get('dateUpdated', '')
            
            # Extract year from CVE ID (e.g., CVE-2023-12345 -> 2023)
            year = cve_id.split('-')[1] if '-' in cve_id else 'Unknown'
            
            # Create text representation
            text_parts = [
                f"CVE ID: {cve_id}",
                f"Severity: {severity} (CVSS {cvss_score})",
                f"Description: {description_text}",
                f"Affected Products: {', '.join(affected_products[:5])}",  # Limit to 5
                f"CWE: {', '.join(cwe_ids)}",
                f"Published: {date_published}",
                f"State: {state}"
            ]
            
            text = " | ".join([p for p in text_parts if p])
            
            # Create metadata
            metadata = {
                "source": os.path.basename(json_path),
                "cve_id": cve_id,
                "year": year,
                "severity": severity,
                "cvss_score": str(cvss_score),
                "state": state,
                "date_published": date_published,
                "cwe_ids": ','.join(cwe_ids),
                "affected_count": len(affected_products)
            }
            
            # Create document
            doc = Document(
                page_content=text,
                metadata=metadata
            )
            
            return doc
        
        except Exception as e:
            logger.error(f"Error parsing {json_path}: {e}")
            return None
    
    def load_all_cve_files(
        self,
        max_files: Optional[int] = None,
        year_filter: Optional[str] = None
    ) -> List[Document]:
        """
        Load all CVE JSON files from the directory
        
        Args:
            max_files: Maximum number of files to process (None = all)
            year_filter: Only process CVEs from specific year (e.g., "2023")
            
        Returns:
            List of all documents
        """
        all_documents = []
        
        # Find all JSON files recursively
        if year_filter:
            # Look in specific year directory
            year_dir = self.cve_dir / year_filter
            if year_dir.exists():
                json_files = list(year_dir.rglob("*.json"))
            else:
                logger.warning(f"Year directory not found: {year_dir}")
                json_files = []
        else:
            json_files = list(self.cve_dir.rglob("*.json"))
        
        logger.info(f"Found {len(json_files)} JSON files")
        
        # Limit files if specified
        if max_files:
            json_files = json_files[:max_files]
            logger.info(f"Processing first {max_files} files")
        
        # Process files
        processed = 0
        skipped = 0
        
        for i, json_file in enumerate(json_files, 1):
            if i % 1000 == 0:
                logger.info(f"Processed {i}/{len(json_files)} files ({processed} CVEs, {skipped} skipped)")
            
            doc = self.parse_cve_json(str(json_file))
            if doc:
                all_documents.append(doc)
                processed += 1
            else:
                skipped += 1
        
        logger.info(f"Total: {processed} CVEs loaded, {skipped} skipped")
        return all_documents
    
    def create_vector_database(
        self,
        documents: List[Document],
        batch_size: int = 5000
    ):
        """
        Create vector database from documents in batches
        
        Args:
            documents: List of documents to index
            batch_size: Number of documents to process at once
        """
        logger.info(f"Creating vector database with {len(documents)} documents")
        
        # Process in batches to avoid memory issues
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} documents)")
            
            if i == 0:
                # Create new vectorstore with first batch
                self.vectorstore = Chroma.from_documents(
                    documents=batch,
                    embedding=self.embeddings,
                    persist_directory=self.vector_db_path
                )
            else:
                # Add to existing vectorstore
                self.vectorstore.add_documents(batch)
            
            # Persist after each batch
            self.vectorstore.persist()
        
        logger.info("Vector database created successfully")
    
    def load_existing_database(self):
        """Load existing vector database"""
        logger.info(f"Loading existing vector database from {self.vector_db_path}")
        self.vectorstore = Chroma(
            persist_directory=self.vector_db_path,
            embedding_function=self.embeddings
        )
        logger.info("Vector database loaded")
    
    def search(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict] = None
    ) -> List[Document]:
        """
        Search for relevant CVEs
        
        Args:
            query: Search query
            k: Number of results to return
            filter_dict: Metadata filters (e.g., {"year": "2023", "severity": "CRITICAL"})
            
        Returns:
            List of relevant documents
        """
        if not self.vectorstore:
            self.load_existing_database()
        
        if filter_dict:
            results = self.vectorstore.similarity_search(
                query,
                k=k,
                filter=filter_dict
            )
        else:
            results = self.vectorstore.similarity_search(query, k=k)
        
        return results
    
    def search_by_cve_id(self, cve_id: str) -> List[Document]:
        """
        Search for a specific CVE by ID
        
        Args:
            cve_id: CVE ID (e.g., "CVE-2023-12345")
            
        Returns:
            List of matching documents
        """
        return self.search(cve_id, k=1, filter_dict={"cve_id": cve_id})
    
    def search_by_severity(self, query: str, severity: str, k: int = 5) -> List[Document]:
        """
        Search CVEs by severity level
        
        Args:
            query: Search query
            severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
            k: Number of results
            
        Returns:
            Filtered results
        """
        return self.search(query, k=k, filter_dict={"severity": severity.upper()})
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the indexed CVE data"""
        if not self.vectorstore:
            self.load_existing_database()
        
        # Get collection stats
        collection = self.vectorstore._collection
        count = collection.count()
        
        return {
            "total_cves": count,
            "vector_db_path": self.vector_db_path,
            "embedding_model": "all-MiniLM-L6-v2",
            "embedding_dimensions": 384,
            "source_directory": str(self.cve_dir)
        }


def setup_cve_rag(
    cve_directory: str = "C:\\Users\\User\\User\\Downloads\\cvelistV5-main\\cvelistV5-main\\cves",
    force_rebuild: bool = False,
    max_files: Optional[int] = None,
    year_filter: Optional[str] = None
) -> CVEJSONRAGIntegration:
    """
    Setup CVE JSON RAG system
    
    Args:
        cve_directory: Directory containing CVE JSON files
        force_rebuild: Force rebuild of vector database
        max_files: Maximum files to process (None = all)
        year_filter: Only process specific year
        
    Returns:
        Configured CVEJSONRAGIntegration instance
    """
    rag = CVEJSONRAGIntegration(cve_directory=cve_directory)
    
    # Check if database exists
    db_exists = os.path.exists(rag.vector_db_path)
    
    if force_rebuild or not db_exists:
        logger.info("Building vector database from CVE JSON files...")
        
        # Load all CVE files
        documents = rag.load_all_cve_files(
            max_files=max_files,
            year_filter=year_filter
        )
        
        if not documents:
            logger.error("No CVE documents loaded!")
            return rag
        
        # Create vector database
        rag.create_vector_database(documents, batch_size=5000)
        
        logger.info("✅ Vector database built successfully")
    else:
        logger.info("Loading existing vector database...")
        rag.load_existing_database()
        logger.info("✅ Vector database loaded")
    
    # Show statistics
    stats = rag.get_statistics()
    logger.info(f"📊 Database statistics: {json.dumps(stats, indent=2)}")
    
    return rag


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CVE JSON RAG Integration")
    parser.add_argument("--cve-dir", 
                       default="C:\\Users\\User\\User\\Desktop\\mcp\\cves",
                       help="CVE JSON directory")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild database")
    parser.add_argument("--test-query", type=str, help="Test query")
    parser.add_argument("--max-files", type=int, help="Max files to process")
    parser.add_argument("--year", type=str, help="Only process specific year")
    
    args = parser.parse_args()
    
    # Setup RAG
    rag = setup_cve_rag(
        cve_directory=args.cve_dir,
        force_rebuild=args.rebuild,
        max_files=args.max_files,
        year_filter=args.year
    )
    
    # Test query
    if args.test_query:
        logger.info(f"\n🔍 Testing query: {args.test_query}")
        results = rag.search(args.test_query, k=5)
        
        for i, doc in enumerate(results, 1):
            print(f"\n{i}. CVE: {doc.metadata.get('cve_id')}")
            print(f"   Severity: {doc.metadata.get('severity')} (CVSS {doc.metadata.get('cvss_score')})")
            print(f"   Content: {doc.page_content[:200]}...")
