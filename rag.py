#!/usr/bin/env python3
"""
CVE RAG System — Vector-only search engine (ChromaDB + all-MiniLM-L6-v2).

Build index:
    python rag.py --build-vectors      # embed CVE descriptions into ChromaDB
    python rag.py --ingest-osv npm PyPI Go
    python rag.py --search "react xss"
    python rag.py --lookup CVE-2021-44228
    python rag.py --stats
"""

import json
import os
import re
import glob
import sqlite3
import logging
import argparse
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CVE_DIR    = os.path.join(BASE_DIR, "cves")
DB_PATH    = os.path.join(BASE_DIR, "cve_rag.db")
CHROMA_DIR = os.path.join(BASE_DIR, "cve_chroma")

# ── Alias resolver ────────────────────────────────────────────────────────────
ALIAS_MAP: Dict[str, List[str]] = {
    "react":       ["react", "react-dom", "react-scripts", "reactjs"],
    "node":        ["node.js", "nodejs", "node"],
    "express":     ["express", "expressjs"],
    "next":        ["next.js", "nextjs", "vercel"],
    "vue":         ["vue", "vuejs", "vue.js"],
    "angular":     ["angular", "angularjs"],
    "jquery":      ["jquery"],
    "electron":    ["electron", "electronjs"],
    "django":      ["django"],
    "flask":       ["flask", "pallets"],
    "fastapi":     ["fastapi", "starlette"],
    "spring":      ["spring", "spring_framework", "spring_boot"],
    "wordpress":   ["wordpress", "wp"],
    "apache":      ["apache", "httpd", "apache_http_server"],
    "nginx":       ["nginx"],
    "mysql":       ["mysql", "mariadb"],
    "postgres":    ["postgresql", "postgres"],
    "php":         ["php"],
    "log4j":       ["log4j", "log4shell", "apache_log4j"],
    "openssl":     ["openssl"],
    "openssh":     ["openssh"],
    "docker":      ["docker", "moby", "containerd"],
    "kubernetes":  ["kubernetes", "k8s"],
    "jenkins":     ["jenkins"],
    "gitlab":      ["gitlab"],
    "redis":       ["redis"],
    "mongodb":     ["mongodb", "mongo"],
    "elasticsearch": ["elasticsearch", "elastic"],
    "grafana":     ["grafana"],
    "struts":      ["struts", "apache_struts"],
    "log4shell":   ["log4j", "log4shell", "CVE-2021-44228"],
    "shellshock":  ["bash", "shellshock", "CVE-2014-6271"],
    "heartbleed":  ["openssl", "heartbleed", "CVE-2014-0160"],
    "eternalblue": ["smb", "ms17-010", "CVE-2017-0144"],
    "sqli":        ["sql injection", "sqli"],
    "rce":         ["remote code execution", "rce", "arbitrary command"],
    "xss":         ["cross-site scripting", "xss"],
    "lfi":         ["local file inclusion", "lfi", "path traversal"],
    "ssrf":        ["server-side request forgery", "ssrf"],
}


def resolve_aliases(query: str) -> str:
    """Expand query terms using alias map for richer vector search."""
    terms = query.lower().split()
    expanded = list(terms)
    for term in terms:
        if term in ALIAS_MAP:
            expanded.extend(ALIAS_MAP[term])
    return " ".join(dict.fromkeys(expanded))


# ══════════════════════════════════════════════════════════════════════════════
# INGESTION — SQLite metadata store (no FTS5, just structured data)
# ══════════════════════════════════════════════════════════════════════════════

def _init_db(conn: sqlite3.Connection):
    conn.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        PRAGMA cache_size=20000;

        CREATE TABLE IF NOT EXISTS cves (
            cve_id         TEXT PRIMARY KEY,
            year           TEXT,
            state          TEXT,
            description    TEXT,
            vendors        TEXT,
            products       TEXT,
            versions       TEXT,
            cvss_score     REAL,
            cvss_vector    TEXT,
            severity       TEXT,
            cwes           TEXT,
            refs           TEXT,
            date_published TEXT,
            source         TEXT DEFAULT 'nvd'
        );

        CREATE TABLE IF NOT EXISTS rag_meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_severity ON cves(severity);
        CREATE INDEX IF NOT EXISTS idx_year     ON cves(year);
        CREATE INDEX IF NOT EXISTS idx_cvss     ON cves(cvss_score);
        CREATE INDEX IF NOT EXISTS idx_source   ON cves(source);
    """)
    conn.commit()


def _extract_nvd_fields(data: dict) -> Optional[dict]:
    try:
        meta   = data.get("cveMetadata", {})
        cve_id = meta.get("cveId", "")
        if not cve_id:
            return None

        year  = cve_id.split("-")[1] if "-" in cve_id else ""
        state = meta.get("state", "")
        cna   = data.get("containers", {}).get("cna", {})

        descs = cna.get("descriptions", [])
        description = next(
            (d.get("value", "") for d in descs if d.get("lang") == "en"),
            " ".join(d.get("value", "") for d in descs)
        )

        vendors, products, versions_list = [], [], []
        for a in cna.get("affected", []):
            v = a.get("vendor", "")
            p = a.get("product", "")
            if v: vendors.append(v.lower())
            if p: products.append(p.lower())
            for ver in a.get("versions", []):
                vs = ver.get("version", "")
                if vs: versions_list.append(vs)

        cvss_score, cvss_vector, severity = None, "", ""
        for m in cna.get("metrics", []):
            cvss = (m.get("cvssV3_1") or m.get("cvssV3_0") or m.get("cvssV2_0"))
            if cvss:
                cvss_score  = cvss.get("baseScore")
                cvss_vector = cvss.get("vectorString", "")
                severity    = cvss.get("baseSeverity", "")
                break

        cwes = [
            d.get("cweId", "")
            for pt in cna.get("problemTypes", [])
            for d in pt.get("descriptions", [])
            if d.get("cweId")
        ]
        refs = [r.get("url", "") for r in cna.get("references", []) if r.get("url")][:5]

        return {
            "cve_id": cve_id, "year": year, "state": state,
            "description": description[:2000],
            "vendors": json.dumps(vendors), "products": json.dumps(products),
            "versions": json.dumps(versions_list),
            "cvss_score": cvss_score, "cvss_vector": cvss_vector,
            "severity": severity.upper() if severity else "",
            "cwes": json.dumps(cwes), "refs": json.dumps(refs),
            "date_published": meta.get("datePublished", ""),
            "source": "nvd",
        }
    except Exception as e:
        logger.debug(f"NVD parse error: {e}")
        return None


def build_vector_index(cve_dir: str = CVE_DIR, db_path: str = DB_PATH,
                       chroma_dir: str = CHROMA_DIR, batch_size: int = 512, limit: int = 0):
    """
    Walk CVE JSON files → store metadata in SQLite → embed descriptions into ChromaDB.
    Run once. ~20-40 min on CPU for 337k CVEs.
    """
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise ImportError("pip install chromadb sentence-transformers")

    # Step 1: ingest metadata into SQLite
    print(f"[VEC] Ingesting CVE metadata from: {cve_dir}")
    conn = sqlite3.connect(db_path)
    _init_db(conn)

    files = glob.glob(os.path.join(cve_dir, "**", "CVE-*.json"), recursive=True)
    total_files = len(files)
    print(f"[VEC] Found {total_files:,} CVE files...")

    batch_data = []
    processed = skipped = 0
    start = datetime.now()

    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            fields = _extract_nvd_fields(data)
            if not fields:
                skipped += 1
                continue
            batch_data.append((
                fields["cve_id"], fields["year"], fields["state"],
                fields["description"], fields["vendors"], fields["products"],
                fields["versions"], fields["cvss_score"], fields["cvss_vector"],
                fields["severity"], fields["cwes"], fields["refs"],
                fields["date_published"], fields["source"]
            ))
            processed += 1
            if len(batch_data) >= 5000:
                conn.executemany(
                    "INSERT OR REPLACE INTO cves VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    batch_data
                )
                conn.commit()
                batch_data.clear()
                print(f"  metadata: {processed:,}/{total_files:,}")
        except Exception as e:
            skipped += 1
            logger.debug(f"Error {filepath}: {e}")

    if batch_data:
        conn.executemany(
            "INSERT OR REPLACE INTO cves VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch_data
        )
        conn.commit()

    conn.execute("INSERT OR REPLACE INTO rag_meta VALUES ('vec_built_at', ?)",
                 (datetime.now().isoformat(),))
    conn.commit()

    # Step 2: embed into ChromaDB
    print(f"\n[VEC] Loading all-MiniLM-L6-v2...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    client = chromadb.PersistentClient(path=chroma_dir)
    col = client.get_or_create_collection("cves", metadata={"hnsw:space": "cosine"})

    conn.row_factory = sqlite3.Row
    q = "SELECT cve_id, description, severity, cvss_score FROM cves WHERE description != ''"
    if limit:
        q += f" LIMIT {limit}"
    rows = conn.execute(q).fetchall()
    conn.close()

    existing = set(col.get(include=[])["ids"])
    rows = [r for r in rows if r["cve_id"] not in existing]
    total = len(rows)
    print(f"[VEC] Embedding {total:,} CVEs (skipping {len(existing):,} already done)...")

    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        ids   = [r["cve_id"] for r in batch]
        texts = [f"{r['cve_id']} {r['description']}" for r in batch]
        metas = [{"severity": r["severity"] or "", "cvss_score": float(r["cvss_score"] or 0)}
                 for r in batch]
        embeddings = model.encode(texts, show_progress_bar=False).tolist()
        col.add(ids=ids, embeddings=embeddings, metadatas=metas, documents=texts)
        if i % (batch_size * 20) == 0:
            print(f"  vectors: {min(i + batch_size, total):,}/{total:,}")

    elapsed = (datetime.now() - start).seconds
    print(f"[VEC] Done — {processed:,} CVEs, {col.count():,} vectors in {elapsed}s")


# ══════════════════════════════════════════════════════════════════════════════
# INGESTION — OSV.dev secondary feed
# ══════════════════════════════════════════════════════════════════════════════

OSV_API = "https://api.osv.dev/v1"


def _parse_osv(vuln: dict) -> Optional[dict]:
    try:
        osv_id  = vuln.get("id", "")
        aliases = vuln.get("aliases", [])
        cve_id  = next((a for a in aliases if a.startswith("CVE-")), osv_id)

        summary     = vuln.get("summary", "")
        details     = vuln.get("details", "")
        description = f"{summary} {details}".strip()[:2000]

        vendors, products, versions_list = [], [], []
        for aff in vuln.get("affected", []):
            pkg  = aff.get("package", {})
            eco  = pkg.get("ecosystem", "").lower()
            name = pkg.get("name", "").lower()
            if eco:  vendors.append(eco)
            if name: products.append(name)
            for rng in aff.get("ranges", []):
                for ev in rng.get("events", []):
                    v = ev.get("introduced") or ev.get("fixed") or ev.get("last_affected")
                    if v and v != "0": versions_list.append(v)

        cvss_score, cvss_vector, severity = None, "", ""
        for sev in vuln.get("severity", []):
            if sev.get("type") in ("CVSS_V3", "CVSS_V2"):
                try:
                    cvss_score = float(sev.get("score", ""))
                except Exception:
                    pass
                cvss_vector = sev.get("score", "")
        if cvss_score:
            if cvss_score >= 9.0:   severity = "CRITICAL"
            elif cvss_score >= 7.0: severity = "HIGH"
            elif cvss_score >= 4.0: severity = "MEDIUM"
            else:                   severity = "LOW"

        cwes      = vuln.get("database_specific", {}).get("cwe_ids", [])
        refs      = [r.get("url", "") for r in vuln.get("references", []) if r.get("url")][:5]
        published = vuln.get("published", "")
        year      = published[:4] if published else ""

        return {
            "cve_id": cve_id, "year": year, "state": "PUBLISHED",
            "description": description,
            "vendors": json.dumps(vendors), "products": json.dumps(products),
            "versions": json.dumps(versions_list),
            "cvss_score": cvss_score, "cvss_vector": cvss_vector,
            "severity": severity, "cwes": json.dumps(cwes),
            "refs": json.dumps(refs), "date_published": published,
            "source": "osv",
        }
    except Exception as e:
        logger.debug(f"OSV parse error: {e}")
        return None


def ingest_osv(ecosystems: List[str] = None, db_path: str = DB_PATH):
    """Fetch OSV.dev CVEs and upsert into SQLite (metadata only — re-run --build-vectors after)."""
    import requests as _req
    if ecosystems is None:
        ecosystems = ["npm", "PyPI", "Go"]

    conn = sqlite3.connect(db_path)
    _init_db(conn)

    for eco in ecosystems:
        print(f"[OSV] Fetching {eco}...")
        inserted   = 0
        page_token = ""
        page       = 0

        while True:
            payload = {"ecosystem": eco, "page_size": 500}
            if page_token:
                payload["page_token"] = page_token
            try:
                resp = _req.post(f"{OSV_API}/query", json=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"  [OSV] Error: {e}")
                break

            vulns = data.get("vulns", [])
            if not vulns:
                break

            batch = []
            for v in vulns:
                row = _parse_osv(v)
                if row:
                    batch.append((
                        row["cve_id"], row["year"], row["state"],
                        row["description"], row["vendors"], row["products"],
                        row["versions"], row["cvss_score"], row["cvss_vector"],
                        row["severity"], row["cwes"], row["refs"],
                        row["date_published"], row["source"]
                    ))

            if batch:
                conn.executemany(
                    "INSERT OR IGNORE INTO cves VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch
                )
                conn.commit()
                inserted += len(batch)

            page += 1
            print(f"  page {page} — {inserted} inserted")
            page_token = data.get("next_page_token", "")
            if not page_token:
                break
            time.sleep(0.2)

        print(f"[OSV] {eco} done — {inserted} records")

    conn.close()
    print("[OSV] Done. Run --build-vectors to embed new records.")


# ══════════════════════════════════════════════════════════════════════════════
# QUERY ENGINE — Vector-only
# ══════════════════════════════════════════════════════════════════════════════

class RAGEngine:
    """
    CVE retrieval engine — pure vector search (ChromaDB + all-MiniLM-L6-v2).
    Model loads lazily on first search call (no startup delay).

    Usage:
        engine  = RAGEngine()
        results = engine.search("apache rce")
        cve     = engine.get("CVE-2021-44228")
        stats   = engine.stats()
    """

    def __init__(self, db_path: str = DB_PATH, chroma_dir: str = CHROMA_DIR):
        self.db_path    = db_path
        self.chroma_dir = chroma_dir
        self._conn: Optional[sqlite3.Connection] = None
        self._col       = None
        self._model     = None
        self._init()

    def _init(self):
        """Open SQLite + ChromaDB connections. Does NOT load the embedding model."""
        if not os.path.exists(self.db_path):
            logger.warning(f"CVE DB not found at {self.db_path}. Run: python rag.py --build-vectors")
            return
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        try:
            import chromadb
            if os.path.exists(self.chroma_dir):
                client    = chromadb.PersistentClient(path=self.chroma_dir)
                self._col = client.get_collection("cves")
                logger.info(f"RAG: vector store ready — {self._col.count():,} CVEs (model loads on first search)")
            else:
                logger.warning("RAG: ChromaDB not found. Run: python rag.py --build-vectors")
        except Exception as e:
            logger.warning(f"RAG: ChromaDB unavailable — {e}")

    def _ensure_model(self):
        """Load SentenceTransformer lazily on first search."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("RAG: loading embedding model...")
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("RAG: model ready")
            except Exception as e:
                raise RuntimeError(f"Failed to load embedding model: {e}")

    @property
    def ready(self) -> bool:
        return self._conn is not None and self._col is not None

    @property
    def mode(self) -> str:
        return "vector (ChromaDB + all-MiniLM-L6-v2 + alias resolver)"

    # ── Public API ────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 20) -> List[Dict]:
        """Semantic vector search with alias expansion."""
        if not self.ready:
            return []
        self._ensure_model()
        expanded = resolve_aliases(query)
        try:
            emb  = self._model.encode([expanded]).tolist()
            res  = self._col.query(query_embeddings=emb, n_results=min(top_k, self._col.count()),
                                   include=["metadatas", "distances"])
            ids   = res["ids"][0]
            dists = res["distances"][0]
            out   = []
            for cve_id, dist in zip(ids, dists):
                row = self._conn.execute("SELECT * FROM cves WHERE cve_id=?", (cve_id,)).fetchone()
                if row:
                    d = dict(row)
                    d["_score"] = round(1 - dist, 4)
                    out.append(self._deserialize(d))
            # boost by CVSS score
            out.sort(key=lambda x: (x["_score"] + (float(x.get("cvss_score") or 0) / 10) * 0.1), reverse=True)
            return out
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []

    def get(self, cve_id: str) -> Optional[Dict]:
        """Exact CVE ID lookup."""
        if not self._conn:
            return None
        row = self._conn.execute(
            "SELECT * FROM cves WHERE cve_id=?", (cve_id.upper().strip(),)
        ).fetchone()
        return self._deserialize(dict(row)) if row else None

    def search_product(self, product: str, version: str = "", top_k: int = 10) -> List[Dict]:
        return self.search(f"{product} {version}".strip(), top_k=top_k)

    def by_severity(self, severity: str, year: str = "", limit: int = 20) -> List[Dict]:
        if not self._conn:
            return []
        sev = severity.upper()
        if year:
            rows = self._conn.execute(
                "SELECT * FROM cves WHERE severity=? AND year=? ORDER BY cvss_score DESC LIMIT ?",
                (sev, year, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM cves WHERE severity=? ORDER BY cvss_score DESC LIMIT ?",
                (sev, limit)
            ).fetchall()
        return [self._deserialize(dict(r)) for r in rows]

    def batch_search(self, service_list: List[str], limit_per: int = 5) -> Dict[str, List[Dict]]:
        return {
            svc: self.search(svc, top_k=limit_per)
            for svc in service_list
        }

    def stats(self) -> Dict:
        if not self._conn:
            return {"error": "DB not initialized"}
        total    = self._conn.execute("SELECT COUNT(*) FROM cves").fetchone()[0]
        by_sev   = dict(self._conn.execute(
            "SELECT severity, COUNT(*) FROM cves WHERE severity!='' GROUP BY severity ORDER BY COUNT(*) DESC"
        ).fetchall())
        by_year  = dict(self._conn.execute(
            "SELECT year, COUNT(*) FROM cves GROUP BY year ORDER BY year DESC LIMIT 10"
        ).fetchall())
        by_src   = dict(self._conn.execute(
            "SELECT source, COUNT(*) FROM cves GROUP BY source"
        ).fetchall())
        meta     = dict(self._conn.execute("SELECT key, value FROM rag_meta").fetchall())
        vec_count = self._col.count() if self._col else 0
        return {
            "total_cves":   total,
            "vector_count": vec_count,
            "search_mode":  self.mode,
            "by_severity":  by_sev,
            "recent_years": by_year,
            "by_source":    by_src,
            "vec_built_at": meta.get("vec_built_at", "not built"),
            "db_size_mb":   round(os.path.getsize(self.db_path) / 1024 / 1024, 1),
        }

    def format_results(self, cves: List[Dict]) -> str:
        if not cves:
            return "No matching CVEs found."
        lines = []
        for c in cves:
            score = f"CVSS {c['cvss_score']}" if c.get("cvss_score") else "No CVSS"
            sev   = c.get("severity", "UNKNOWN")
            cwes  = ", ".join(c.get("cwes", [])) or "N/A"
            prods = ", ".join(c.get("products", [])) or "N/A"
            refs  = c.get("references", [])
            ref   = refs[0] if refs else "N/A"
            lines.append(
                f"[{c['cve_id']}] {sev} | {score}\n"
                f"  Products : {prods}\n"
                f"  CWE      : {cwes}\n"
                f"  Summary  : {c.get('description','')[:200]}\n"
                f"  Reference: {ref}\n"
            )
        return "\n".join(lines)

    def _deserialize(self, doc: Dict) -> Dict:
        for field in ("vendors", "products", "versions", "cwes", "refs"):
            try:
                doc[field] = json.loads(doc.get(field) or "[]")
            except Exception:
                doc[field] = []
        doc["references"] = doc.pop("refs", [])
        return doc

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="CVE Vector Search Engine")
    parser.add_argument("--build-vectors", action="store_true",
                        help="Ingest CVE JSON files and embed into ChromaDB")
    parser.add_argument("--ingest-osv",    nargs="+", metavar="ECO",
                        help="Fetch OSV.dev CVEs (e.g. npm PyPI Go)")
    parser.add_argument("--search",  type=str, help="Semantic search query")
    parser.add_argument("--lookup",  type=str, help="Exact CVE ID lookup")
    parser.add_argument("--stats",   action="store_true", help="Show DB statistics")
    parser.add_argument("--limit",   type=int, default=0,
                        help="Limit CVEs to embed (0=all, use 10000 for quick test)")
    parser.add_argument("--top-k",   type=int, default=10)
    args = parser.parse_args()

    if args.build_vectors:
        build_vector_index(limit=args.limit)
    elif args.ingest_osv:
        ingest_osv(ecosystems=args.ingest_osv)
    elif args.stats:
        engine = RAGEngine()
        print(json.dumps(engine.stats(), indent=2))
    elif args.search:
        engine  = RAGEngine()
        results = engine.search(args.search, top_k=args.top_k)
        print(f"Mode: {engine.mode}\n")
        print(engine.format_results(results))
    elif args.lookup:
        engine = RAGEngine()
        result = engine.get(args.lookup)
        print(json.dumps(result, indent=2) if result else "Not found")
    else:
        parser.print_help()
