#!/usr/bin/env python3
"""
Enhanced MCP Server with CVE JSON RAG Integration
Combines penetration testing tools with CVE database analysis
"""

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, Optional

from mcp_server import (
    KaliToolsClient, setup_mcp_server, 
    DEFAULT_KALI_SERVER, DEFAULT_REQUEST_TIMEOUT, API_KEY
)

# Import CVE RAG
try:
    from json_cve_rag_integration import CVEJSONRAGIntegration, setup_cve_rag
    CVE_RAG_AVAILABLE = True
except ImportError:
    CVE_RAG_AVAILABLE = False
    logging.warning("CVE RAG not available. Install dependencies: pip install langchain chromadb sentence-transformers")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# Global CVE RAG instance
cve_rag: Optional[CVEJSONRAGIntegration] = None


def setup_enhanced_mcp_server(kali_client: KaliToolsClient, cve_rag_instance: Optional[CVEJSONRAGIntegration] = None):
    """
    Setup MCP server with CVE RAG integration
    
    Args:
        kali_client: Kali tools client
        cve_rag_instance: CVE RAG instance (optional)
        
    Returns:
        Enhanced FastMCP instance
    """
    # Get base MCP server with all tools
    mcp = setup_mcp_server(kali_client)
    
    # Add CVE RAG tools if available
    if cve_rag_instance and CVE_RAG_AVAILABLE:
        logger.info("Adding CVE RAG tools to MCP server")
        
        @mcp.tool(name="search_cve_database")
        def search_cve_database(query: str, limit: int = 5, severity: Optional[str] = None) -> str:
            """
            Search through CVE database using semantic search.
            
            Args:
                query: Search query (e.g., "SQL injection", "remote code execution", "Apache")
                limit: Number of results to return (default: 5)
                severity: Optional severity filter (CRITICAL, HIGH, MEDIUM, LOW)
                
            Returns:
                Formatted search results from CVE database
                
            Examples:
                - search_cve_database("SQL injection vulnerabilities")
                - search_cve_database("Apache Struts", limit=10)
                - search_cve_database("remote code execution", severity="CRITICAL")
            """
            try:
                # Apply severity filter if provided
                if severity:
                    results = cve_rag_instance.search_by_severity(
                        query,
                        severity,
                        k=limit
                    )
                else:
                    results = cve_rag_instance.search(query, k=limit)
                
                if not results:
                    return f"No CVEs found for query: {query}"
                
                report = f"\n{'='*80}\n🔍 CVE DATABASE SEARCH RESULTS\n{'='*80}\n\n"
                report += f"Query: {query}\n"
                if severity:
                    report += f"Severity Filter: {severity}\n"
                report += f"Results: {len(results)}\n\n"
                
                for i, doc in enumerate(results, 1):
                    cve_id = doc.metadata.get('cve_id', 'Unknown')
                    severity_level = doc.metadata.get('severity', 'Unknown')
                    cvss_score = doc.metadata.get('cvss_score', 'Unknown')
                    year = doc.metadata.get('year', 'Unknown')
                    
                    report += f"{i}. {cve_id} ({year})\n"
                    report += f"   Severity: {severity_level} (CVSS {cvss_score})\n"
                    report += f"   {doc.page_content[:300]}\n"
                    report += f"{'─'*80}\n\n"
                
                return report
            
            except Exception as e:
                return f"❌ Error searching CVE database: {str(e)}"
        
        @mcp.tool(name="get_cve_details")
        def get_cve_details(cve_id: str) -> str:
            """
            Get detailed information about a specific CVE.
            
            Args:
                cve_id: CVE ID (e.g., "CVE-2023-12345")
                
            Returns:
                Detailed CVE information
                
            Examples:
                - get_cve_details("CVE-2023-12345")
                - get_cve_details("CVE-2021-44228")  # Log4Shell
            """
            try:
                results = cve_rag_instance.search_by_cve_id(cve_id)
                
                if not results:
                    return f"CVE not found: {cve_id}"
                
                doc = results[0]
                
                report = f"\n{'='*80}\n📋 CVE DETAILS: {cve_id}\n{'='*80}\n\n"
                report += f"Severity: {doc.metadata.get('severity', 'Unknown')} "
                report += f"(CVSS {doc.metadata.get('cvss_score', 'Unknown')})\n"
                report += f"Year: {doc.metadata.get('year', 'Unknown')}\n"
                report += f"Published: {doc.metadata.get('date_published', 'Unknown')}\n"
                report += f"State: {doc.metadata.get('state', 'Unknown')}\n"
                
                cwe_ids = doc.metadata.get('cwe_ids', '')
                if cwe_ids:
                    report += f"CWE: {cwe_ids}\n"
                
                report += f"\n{doc.page_content}\n"
                report += f"\n{'='*80}\n"
                
                return report
            
            except Exception as e:
                return f"❌ Error getting CVE details: {str(e)}"
        
        @mcp.tool(name="search_cves_by_year")
        def search_cves_by_year(query: str, year: str, limit: int = 10) -> str:
            """
            Search CVEs from a specific year.
            
            Args:
                query: Search query
                year: Year (e.g., "2023", "2024")
                limit: Number of results
                
            Returns:
                CVEs from specified year
                
            Examples:
                - search_cves_by_year("SQL injection", "2023")
                - search_cves_by_year("remote code execution", "2024", limit=20)
            """
            try:
                results = cve_rag_instance.search(
                    query,
                    k=limit,
                    filter_dict={"year": year}
                )
                
                if not results:
                    return f"No CVEs found for '{query}' in year {year}"
                
                report = f"\n{'='*80}\n📅 CVE SEARCH - YEAR {year}\n{'='*80}\n\n"
                report += f"Query: {query}\n"
                report += f"Results: {len(results)}\n\n"
                
                for i, doc in enumerate(results, 1):
                    cve_id = doc.metadata.get('cve_id', 'Unknown')
                    severity = doc.metadata.get('severity', 'Unknown')
                    cvss = doc.metadata.get('cvss_score', 'Unknown')
                    
                    report += f"{i}. {cve_id}\n"
                    report += f"   Severity: {severity} (CVSS {cvss})\n"
                    report += f"   {doc.page_content[:250]}\n"
                    report += f"{'─'*80}\n\n"
                
                return report
            
            except Exception as e:
                return f"❌ Error searching CVEs: {str(e)}"
        
        @mcp.tool(name="get_cve_statistics")
        def get_cve_statistics() -> str:
            """
            Get statistics about the indexed CVE database.
            
            Returns:
                Statistics including total CVEs, database info
            """
            try:
                stats = cve_rag_instance.get_statistics()
                
                report = f"\n{'='*80}\n📊 CVE DATABASE STATISTICS\n{'='*80}\n\n"
                report += f"Total CVEs: {stats['total_cves']:,}\n"
                report += f"Vector Database: {stats['vector_db_path']}\n"
                report += f"Source Directory: {stats['source_directory']}\n"
                report += f"Embedding Model: {stats['embedding_model']}\n"
                report += f"Embedding Dimensions: {stats['embedding_dimensions']}\n"
                report += f"\n{'='*80}\n"
                
                return report
            
            except Exception as e:
                return f"❌ Error getting statistics: {str(e)}"
        
        @mcp.tool(name="enhanced_vulnerability_report_with_cve")
        def enhanced_vulnerability_report_with_cve(target: str, include_cve_context: bool = True) -> str:
            """
            Generate enhanced vulnerability report combining scan results with CVE database.
            
            Args:
                target: Target that was scanned
                include_cve_context: Include CVE database context
                
            Returns:
                Comprehensive report with scan results and CVE context
                
            Examples:
                - enhanced_vulnerability_report_with_cve("192.168.1.100")
                - enhanced_vulnerability_report_with_cve("example.com", include_cve_context=True)
            """
            try:
                from mcp_server import load_all_results
                
                # Load scan results for target
                results = load_all_results()
                target_results = [r for r in results if target.lower() in r.get('target', '').lower()]
                
                if not target_results:
                    return f"No scan results found for target: {target}"
                
                report = f"\n{'='*80}\n🎯 ENHANCED VULNERABILITY REPORT WITH CVE CONTEXT\n{'='*80}\n\n"
                report += f"Target: {target}\n"
                report += f"Scan Results: {len(target_results)}\n"
                report += f"CVE Context: {'Enabled' if include_cve_context else 'Disabled'}\n\n"
                
                # Analyze scan results
                report += "📊 SCAN FINDINGS\n"
                report += f"{'─'*80}\n"
                
                for i, result in enumerate(target_results, 1):
                    status = "✅" if result.get('success') else "❌"
                    report += f"{i}. {status} {result['tool'].upper()}\n"
                    report += f"   Time: {result.get('datetime', 'Unknown')}\n"
                    
                    if result.get('success'):
                        stdout = result.get('stdout', '')[:200]
                        report += f"   Output: {stdout}...\n"
                    else:
                        report += f"   Error: {result.get('error', 'Unknown')}\n"
                    
                    report += f"{'─'*80}\n"
                
                # Add CVE context
                if include_cve_context:
                    report += f"\n📚 CVE DATABASE CONTEXT\n"
                    report += f"{'─'*80}\n"
                    
                    # Search for relevant CVEs based on findings
                    search_queries = [
                        "common vulnerabilities",
                        "network service vulnerabilities",
                        "web application vulnerabilities"
                    ]
                    
                    for query in search_queries:
                        cve_results = cve_rag_instance.search(query, k=3)
                        
                        if cve_results:
                            report += f"\n🔍 {query.upper()}\n"
                            for doc in cve_results:
                                cve_id = doc.metadata.get('cve_id', 'Unknown')
                                severity = doc.metadata.get('severity', 'Unknown')
                                cvss = doc.metadata.get('cvss_score', 'Unknown')
                                report += f"   • {cve_id} ({severity}, CVSS {cvss})\n"
                                report += f"     {doc.page_content[:150]}...\n"
                    
                    report += f"\n{'─'*80}\n"
                
                report += f"\n💡 This report combines real-time scan results with {cve_rag_instance.get_statistics()['total_cves']:,} CVEs\n"
                report += f"{'='*80}\n"
                
                return report
            
            except Exception as e:
                return f"❌ Error generating enhanced report: {str(e)}"
        
        logger.info("✅ CVE RAG tools added successfully")
    else:
        if not CVE_RAG_AVAILABLE:
            logger.warning("⚠️  CVE RAG tools not available - install dependencies")
        else:
            logger.warning("⚠️  CVE RAG instance not provided")
    
    return mcp


def main():
    """Main entry point for enhanced MCP server"""
    parser = argparse.ArgumentParser(description="Enhanced MCP Kali client with CVE RAG")
    parser.add_argument("--server", type=str, default=DEFAULT_KALI_SERVER,
                       help=f"Kali API server URL (default: {DEFAULT_KALI_SERVER})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_REQUEST_TIMEOUT,
                       help=f"Request timeout in seconds (default: {DEFAULT_REQUEST_TIMEOUT})")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    # CVE RAG options
    parser.add_argument("--cve-dir", type=str,
                       default="C:\\Users\\User\\User\\Desktop\\mcp\\cves",
                       help="Directory containing CVE JSON files")
    parser.add_argument("--enable-cve-rag", action="store_true",
                       help="Enable CVE RAG integration")
    parser.add_argument("--rebuild-cve-db", action="store_true",
                       help="Force rebuild of CVE vector database")
    parser.add_argument("--max-cves", type=int,
                       help="Maximum CVEs to process (for testing)")
    parser.add_argument("--year", type=str,
                       help="Only process CVEs from specific year")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Initialize Kali Tools client
    kali_client = KaliToolsClient(args.server, args.timeout, API_KEY)
    
    # Check server health
    health = kali_client.check_health()
    if "error" in health:
        logger.warning(f"Unable to connect to Kali API server: {health['error']}")
        logger.warning("MCP server will start, but tool execution may fail")
    else:
        logger.info(f"✅ Connected to Kali API server at {args.server}")
        logger.info(f"Server status: {health['status']}")
    
    # Initialize CVE RAG if enabled
    global cve_rag
    if args.enable_cve_rag and CVE_RAG_AVAILABLE:
        logger.info("🚀 Initializing CVE RAG system...")
        
        try:
            cve_rag = setup_cve_rag(
                cve_directory=args.cve_dir,
                force_rebuild=args.rebuild_cve_db,
                max_files=args.max_cves,
                year_filter=args.year
            )
            logger.info("✅ CVE RAG system initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize CVE RAG: {e}")
            cve_rag = None
    elif args.enable_cve_rag and not CVE_RAG_AVAILABLE:
        logger.error("❌ CVE RAG requested but dependencies not installed")
        logger.error("Run: pip install langchain chromadb sentence-transformers")
    
    # Setup and run MCP server
    mcp = setup_enhanced_mcp_server(kali_client, cve_rag)
    logger.info("🚀 Starting Enhanced MCP Kali server with CVE RAG")
    mcp.run()


if __name__ == "__main__":
    main()
