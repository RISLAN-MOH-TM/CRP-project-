#!/usr/bin/env python3
"""
CVE RAG System - Fast keyword-based retrieval using SQLite FTS5.
Indexes 320k+ CVE JSON files for instant cross-referencing during pentest report generation.

Usage:
    # First time: build the index (run once, takes a few minutes)
    python cve_rag.py --build

    # Then use via MCP tools or directly:
    from cve_rag import CVESearchEngine
    engine = CVESearchEngine()
    results = engine.search_by_product("apache", "2.4.49")
"""

import json
import os
import re
import sqlite3
import glob
import logging
import argparse
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CVE_DIR = os.path.join(BASE_DIR, "cves")
DB_PATH = os.path.join(BASE_DIR, "cve_index.db")


def _extract_cve_fields(data: dict) -> Optional[dict]:
    """Extract flat searchable fields from a CVE JSON record."""
    try:
        meta = data.get("cveMetadata", {})
        cve_id = meta.get("cveId", "")
        state = meta.get("state", "")
        year = cve_id.split("-")[1] if cve_id else ""

        cna = data.get("containers", {}).get("cna", {})

        # Description
        descriptions = cna.get("descriptions", [])
        description = " ".join(d.get("value", "") for d in descriptions if d.get("lang") == "en")

        # Affected products
        affected = cna.get("affected", [])
        vendors, products, versions_list = [], [], []
        for a in affected:
            v = a.get("vendor", "")
            p = a.get("product", "")
            if v:
                vendors.append(v.lower())
            if p:
                products.append(p.lower())
            for ver in a.get("versions", []):
                vs = ver.get("version", "")
                if vs:
                    versions_list.append(vs)

        # CVSS
        cvss_score = None
        cvss_vector = ""
        severity = ""
        for m in cna.get("metrics", []):
            cvss = m.get("cvssV3_1") or m.get("cvssV3_0") or m.get("cvssV2_0")
            if cvss:
                cvss_score = cvss.get("baseScore")
                cvss_vector = cvss.get("vectorString", "")
                severity = cvss.get("baseSeverity", "")
                break

        # CWE
        cwes = []
        for pt in cna.get("problemTypes", []):
            for d in pt.get("descriptions", []):
                cwe = d.get("cweId", "")
                if cwe:
                    cwes.append(cwe)

        # References
        refs = [r.get("url", "") for r in cna.get("references", []) if r.get("url")]

        # Build search text blob for FTS
        search_text = " ".join(filter(None, [
            cve_id, description,
            " ".join(vendors), " ".join(products),
            " ".join(versions_list), " ".join(cwes)
        ]))

        return {
            "cve_id": cve_id,
            "year": year,
            "state": state,
            "description": description[:2000],
            "vendors": json.dumps(vendors),
            "products": json.dumps(products),
            "versions": json.dumps(versions_list),
            "cvss_score": cvss_score,
            "cvss_vector": cvss_vector,
            "severity": severity.upper() if severity else "",
            "cwes": json.dumps(cwes),
            "refs": json.dumps(refs[:5]),
            "search_text": search_text,
            "date_published": meta.get("datePublished", ""),
        }
    except Exception as e:
        logger.debug(f"Error extracting CVE fields: {e}")
        return None


def build_index(cve_dir: str = CVE_DIR, db_path: str = DB_PATH, batch_size: int = 5000):
    """
    Walk all CVE JSON files and build a SQLite FTS5 index.
    Run once — takes ~3-8 minutes for 320k files.
    """
    print(f"Building CVE index from: {cve_dir}")
    print(f"Database: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")

    # Main data table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cves (
            cve_id      TEXT PRIMARY KEY,
            year        TEXT,
            state       TEXT,
            description TEXT,
            vendors     TEXT,
            products    TEXT,
            versions    TEXT,
            cvss_score  REAL,
            cvss_vector TEXT,
            severity    TEXT,
            cwes        TEXT,
            refs        TEXT,
            date_published TEXT
        )
    """)

    # FTS5 virtual table for fast keyword search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS cves_fts USING fts5(
            cve_id,
            search_text,
            content='cves',
            content_rowid='rowid'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS index_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()

    # Find all CVE JSON files
    pattern = os.path.join(cve_dir, "**", "CVE-*.json")
    files = glob.glob(pattern, recursive=True)
    total = len(files)
    print(f"Found {total:,} CVE files. Indexing...")

    batch_data = []
    batch_fts = []
    processed = 0
    skipped = 0
    start = datetime.now()

    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)

            fields = _extract_cve_fields(data)
            if not fields:
                skipped += 1
                continue

            batch_data.append((
                fields["cve_id"], fields["year"], fields["state"],
                fields["description"], fields["vendors"], fields["products"],
                fields["versions"], fields["cvss_score"], fields["cvss_vector"],
                fields["severity"], fields["cwes"], fields["refs"],
                fields["date_published"]
            ))
            batch_fts.append((fields["cve_id"], fields["search_text"]))
            processed += 1

            if len(batch_data) >= batch_size:
                conn.executemany("""
                    INSERT OR REPLACE INTO cves VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, batch_data)
                conn.executemany("""
                    INSERT OR REPLACE INTO cves_fts(cve_id, search_text) VALUES (?,?)
                """, batch_fts)
                conn.commit()
                batch_data.clear()
                batch_fts.clear()
                elapsed = (datetime.now() - start).seconds
                print(f"  Indexed {processed:,}/{total:,} ({processed/total*100:.1f}%) — {elapsed}s elapsed")

        except Exception as e:
            skipped += 1
            logger.debug(f"Error processing {filepath}: {e}")

    # Final batch
    if batch_data:
        conn.executemany("""
            INSERT OR REPLACE INTO cves VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, batch_data)
        conn.executemany("""
            INSERT OR REPLACE INTO cves_fts(cve_id, search_text) VALUES (?,?)
        """, batch_fts)
        conn.commit()

    # Save metadata
    conn.execute("INSERT OR REPLACE INTO index_meta VALUES ('total', ?)", (str(processed),))
    conn.execute("INSERT OR REPLACE INTO index_meta VALUES ('built_at', ?)", (datetime.now().isoformat(),))
    conn.commit()

    # Create indexes for fast lookups
    conn.execute("CREATE INDEX IF NOT EXISTS idx_severity ON cves(severity)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_year ON cves(year)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cvss ON cves(cvss_score)")
    conn.commit()
    conn.close()

    elapsed = (datetime.now() - start).seconds
    print(f"\nDone! Indexed {processed:,} CVEs, skipped {skipped} in {elapsed}s")
    print(f"Database: {db_path}")


class CVESearchEngine:
    """
    Fast CVE retrieval engine backed by SQLite FTS5.
    Designed to be called from MCP tools during pentest report generation.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            if not os.path.exists(self.db_path):
                raise FileNotFoundError(
                    f"CVE index not found at {self.db_path}. "
                    "Run: python cve_rag.py --build"
                )
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA query_only=ON")
        return self._conn

    def _row_to_dict(self, row) -> dict:
        d = dict(row)
        for field in ("vendors", "products", "versions", "cwes", "refs"):
            try:
                d[field] = json.loads(d.get(field) or "[]")
            except Exception:
                d[field] = []
        # expose as 'references' for backward compat
        d["references"] = d.pop("refs", [])
        return d

    def is_ready(self) -> bool:
        """Check if the index exists and is populated."""
        return os.path.exists(self.db_path)

    def get_stats(self) -> dict:
        """Return index statistics."""
        try:
            conn = self._get_conn()
            total = conn.execute("SELECT COUNT(*) FROM cves").fetchone()[0]
            by_severity = dict(conn.execute(
                "SELECT severity, COUNT(*) FROM cves WHERE severity != '' GROUP BY severity ORDER BY COUNT(*) DESC"
            ).fetchall())
            by_year = dict(conn.execute(
                "SELECT year, COUNT(*) FROM cves GROUP BY year ORDER BY year DESC LIMIT 10"
            ).fetchall())
            meta = dict(conn.execute("SELECT key, value FROM index_meta").fetchall())
            return {
                "total_cves": total,
                "by_severity": by_severity,
                "recent_years": by_year,
                "built_at": meta.get("built_at", "unknown"),
                "db_size_mb": round(os.path.getsize(self.db_path) / 1024 / 1024, 1)
            }
        except Exception as e:
            return {"error": str(e)}

    def get_by_id(self, cve_id: str) -> Optional[dict]:
        """
        Fetch a single CVE by exact ID (e.g. 'CVE-2021-44228').
        Fastest lookup — direct primary key.
        """
        try:
            cve_id = cve_id.upper().strip()
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM cves WHERE cve_id = ?", (cve_id,)).fetchone()
            return self._row_to_dict(row) if row else None
        except Exception as e:
            logger.error(f"get_by_id error: {e}")
            return None

    def search_by_product(self, product: str, version: str = "", limit: int = 10) -> List[dict]:
        """
        Search CVEs by product name and optional version string.
        Used to cross-reference nmap/nikto discovered services.

        Examples:
            search_by_product("apache", "2.4.49")
            search_by_product("openssh", "7.4")
            search_by_product("wordpress", "5.8")
        """
        try:
            conn = self._get_conn()
            # Build FTS query — product is required, version optional
            query_parts = [product]
            if version:
                # Try exact version first, then major.minor
                query_parts.append(version)

            fts_query = " ".join(query_parts)

            rows = conn.execute("""
                SELECT c.* FROM cves c
                JOIN cves_fts f ON c.cve_id = f.cve_id
                WHERE cves_fts MATCH ?
                ORDER BY c.cvss_score DESC NULLS LAST
                LIMIT ?
            """, (fts_query, limit)).fetchall()

            return [self._row_to_dict(r) for r in rows]
        except Exception as e:
            logger.error(f"search_by_product error: {e}")
            return []

    def search_by_keyword(self, query: str, limit: int = 10) -> List[dict]:
        """
        Free-text search across all CVE descriptions, products, vendors.
        Used for semantic-style queries like 'sql injection mysql' or 'rce apache'.
        """
        try:
            conn = self._get_conn()
            rows = conn.execute("""
                SELECT c.* FROM cves c
                JOIN cves_fts f ON c.cve_id = f.cve_id
                WHERE cves_fts MATCH ?
                ORDER BY c.cvss_score DESC NULLS LAST
                LIMIT ?
            """, (query, limit)).fetchall()
            return [self._row_to_dict(r) for r in rows]
        except Exception as e:
            logger.error(f"search_by_keyword error: {e}")
            return []

    def get_by_severity(self, severity: str, year: str = "", limit: int = 20) -> List[dict]:
        """
        Get CVEs filtered by severity (CRITICAL/HIGH/MEDIUM/LOW) and optional year.
        """
        try:
            conn = self._get_conn()
            severity = severity.upper()
            if year:
                rows = conn.execute("""
                    SELECT * FROM cves WHERE severity = ? AND year = ?
                    ORDER BY cvss_score DESC LIMIT ?
                """, (severity, year, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM cves WHERE severity = ?
                    ORDER BY cvss_score DESC LIMIT ?
                """, (severity, limit)).fetchall()
            return [self._row_to_dict(r) for r in rows]
        except Exception as e:
            logger.error(f"get_by_severity error: {e}")
            return []

    def search_multiple_products(self, products: List[str], limit_per: int = 5) -> Dict[str, List[dict]]:
        """
        Batch search for multiple products at once.
        Used after nmap scan to enrich all discovered services in one call.

        Example:
            search_multiple_products(["apache 2.4.49", "openssh 7.4", "mysql 5.7"])
        """
        results = {}
        for product_str in products:
            parts = product_str.strip().split(None, 1)
            product = parts[0]
            version = parts[1] if len(parts) > 1 else ""
            results[product_str] = self.search_by_product(product, version, limit=limit_per)
        return results

    def format_for_report(self, cves: List[dict]) -> str:
        """
        Format a list of CVE dicts into a clean report-ready string block.
        """
        if not cves:
            return "No matching CVEs found in database."

        lines = []
        for c in cves:
            score = f"CVSS {c['cvss_score']}" if c.get("cvss_score") else "No CVSS"
            severity = c.get("severity", "UNKNOWN")
            cwe_str = ", ".join(c.get("cwes", [])) or "N/A"
            products_str = ", ".join(c.get("products", [])) or "N/A"
            refs = c.get("references", [])
            ref_str = refs[0] if refs else "N/A"

            lines.append(
                f"[{c['cve_id']}] {severity} | {score}\n"
                f"  Products : {products_str}\n"
                f"  CWE      : {cwe_str}\n"
                f"  Summary  : {c.get('description', '')[:200]}\n"
                f"  Reference: {ref_str}\n"
            )
        return "\n".join(lines)

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="CVE RAG System")
    parser.add_argument("--build", action="store_true", help="Build the SQLite index from CVE JSON files")
    parser.add_argument("--search", type=str, help="Quick search test (e.g. 'apache 2.4.49')")
    parser.add_argument("--id", type=str, help="Lookup a specific CVE ID")
    parser.add_argument("--stats", action="store_true", help="Show index statistics")
    args = parser.parse_args()

    if args.build:
        build_index()
    elif args.stats:
        engine = CVESearchEngine()
        stats = engine.get_stats()
        print(json.dumps(stats, indent=2))
    elif args.search:
        engine = CVESearchEngine()
        parts = args.search.split(None, 1)
        results = engine.search_by_product(parts[0], parts[1] if len(parts) > 1 else "")
        print(engine.format_for_report(results))
    elif args.id:
        engine = CVESearchEngine()
        result = engine.get_by_id(args.id)
        print(json.dumps(result, indent=2) if result else "Not found")
    else:
        parser.print_help()
