#!/usr/bin/env python3
"""
CVE RAG System — Unified vector + keyword hybrid search engine.

Auto-initializes when imported. No separate build step needed if you
pass auto_build=True (default). Just import and search.

Architecture:
  ┌─────────────────────────────────────────────────────┐
  │  Ingestion (offline, runs once + nightly sync)      │
  │  CVE JSON files → SQLite FTS5                       │
  │  CVE descriptions → all-MiniLM-L6-v2 → ChromaDB    │
  │  OSV.dev API → npm/pip/Go CVEs → SQLite FTS5        │
  └─────────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────────┐
  │  Query (online, every MCP call)                     │
  │  User query → alias expand → FTS5 top-50            │
  │                            → vector ANN top-50      │
  │                            → RRF merge + CVSS boost │
  │                            → top-N results          │
  └─────────────────────────────────────────────────────┘

Standalone build:
    python rag.py --build-fts          # index CVE JSON files into SQLite
    python rag.py --build-vectors      # embed descriptions into ChromaDB
    python rag.py --ingest-osv npm PyPI Go   # pull OSV ecosystem CVEs
    python rag.py --search "react file upload"
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
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
CVE_DIR   = os.path.join(BASE_DIR, "cves")
DB_PATH   = os.path.join(BASE_DIR, "cve_rag.db")
CHROMA_DIR = os.path.join(BASE_DIR, "cve_chroma")

# ── Alias resolver ────────────────────────────────────────────────────────────
# Maps short user terms → CPE/product name variants stored in the DB.
# Solves: user types "react" → DB stores "react-server-dom-webpack"
ALIAS_MAP: Dict[str, List[str]] = {
    "react":       ["react", "react-dom", "react-scripts", "react-server-dom-webpack", "reactjs"],
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
    "pip":         ["pip", "pypi", "python-pip"],
    "npm":         ["npm", "node_package_manager"],
    "docker":      ["docker", "moby", "containerd"],
    "kubernetes":  ["kubernetes", "k8s"],
    "jenkins":     ["jenkins"],
    "gitlab":      ["gitlab"],
    "github":      ["github", "github_actions"],
    "redis":       ["redis"],
    "mongodb":     ["mongodb", "mongo"],
    "elasticsearch": ["elasticsearch", "elastic"],
    "grafana":     ["grafana"],
    "struts":      ["struts", "apache_struts"],
    "log4shell":   ["log4j", "log4shell", "CVE-2021-44228"],
    "shellshock":  ["bash", "shellshock", "CVE-2014-6271"],
    "heartbleed":  ["openssl", "heartbleed", "CVE-2014-0160"],
    "eternalblue": ["smb", "ms17-010", "CVE-2017-0144"],
}


def resolve_aliases(query: str) -> List[str]:
    """Expand query terms using alias map. Returns deduplicated list."""
    terms = query.lower().split()
    expanded = list(terms)
    for term in terms:
        if term in ALIAS_MAP:
            expanded.extend(ALIAS_MAP[term])
    return list(dict.fromkeys(expanded))


# ══════════════════════════════════════════════════════════════════════════════
# INGESTION — SQLite FTS5
# ══════════════════════════════════════════════════════════════════════════════

def _init_db(conn: sqlite3.Connection):
    """Create tables if they don't exist."""
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

        CREATE VIRTUAL TABLE IF NOT EXISTS cves_fts USING fts5(
            cve_id,
            search_text,
            content='cves',
            content_rowid='rowid'
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
    """Parse a CVE JSON file (NVD CVE 5.0 format) into a flat dict."""
    try:
        meta  = data.get("cveMetadata", {})
        cve_id = meta.get("cveId", "")
        if not cve_id:
            return None

        year  = cve_id.split("-")[1] if "-" in cve_id else ""
        state = meta.get("state", "")
        cna   = data.get("containers", {}).get("cna", {})

        # Description (English preferred)
        descs = cna.get("descriptions", [])
        description = next(
            (d.get("value", "") for d in descs if d.get("lang") == "en"),
            " ".join(d.get("value", "") for d in descs)
        )

        # Affected products
        vendors, products, versions_list = [], [], []
        for a in cna.get("affected", []):
            v = a.get("vendor", "")
            p = a.get("product", "")
            if v: vendors.append(v.lower())
            if p: products.append(p.lower())
            for ver in a.get("versions", []):
                vs = ver.get("version", "")
                if vs: versions_list.append(vs)

        # CVSS (prefer v3.1 > v3.0 > v2)
        cvss_score, cvss_vector, severity = None, "", ""
        for m in cna.get("metrics", []):
            cvss = (m.get("cvssV3_1") or m.get("cvssV3_0") or m.get("cvssV2_0"))
            if cvss:
                cvss_score  = cvss.get("baseScore")
                cvss_vector = cvss.get("vectorString", "")
                severity    = cvss.get("baseSeverity", "")
                break

        # CWE
        cwes = [
            d.get("cweId", "")
            for pt in cna.get("problemTypes", [])
            for d in pt.get("descriptions", [])
            if d.get("cweId")
        ]

        # References
        refs = [r.get("url", "") for r in cna.get("references", []) if r.get("url")][:5]

        search_text = " ".join(filter(None, [
            cve_id, description,
            " ".join(vendors), " ".join(products),
            " ".join(versions_list), " ".join(cwes)
        ]))

        return {
            "cve_id": cve_id, "year": year, "state": state,
            "description": description[:2000],
            "vendors": json.dumps(vendors), "products": json.dumps(products),
            "versions": json.dumps(versions_list),
            "cvss_score": cvss_score, "cvss_vector": cvss_vector,
            "severity": severity.upper() if severity else "",
            "cwes": json.dumps(cwes), "refs": json.dumps(refs),
            "date_published": meta.get("datePublished", ""),
            "search_text": search_text, "source": "nvd",
        }
    except Exception as e:
        logger.debug(f"NVD parse error: {e}")
        return None


def build_fts_index(cve_dir: str = CVE_DIR, db_path: str = DB_PATH, batch_size: int = 5000):
    """
    Walk all CVE JSON files and build SQLite FTS5 index.
    Run once — ~3-8 min for 337k files.
    """
    print(f"[FTS] Building index from: {cve_dir}")
    conn = sqlite3.connect(db_path)
    _init_db(conn)

    files = glob.glob(os.path.join(cve_dir, "**", "CVE-*.json"), recursive=True)
    total = len(files)
    print(f"[FTS] Found {total:,} CVE files...")

    batch_data, batch_fts = [], []
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
            batch_fts.append((fields["cve_id"], fields["search_text"]))
            processed += 1

            if len(batch_data) >= batch_size:
                conn.executemany(
                    "INSERT OR REPLACE INTO cves VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    batch_data
                )
                conn.executemany(
                    "INSERT OR REPLACE INTO cves_fts(cve_id, search_text) VALUES (?,?)",
                    batch_fts
                )
                conn.commit()
                batch_data.clear(); batch_fts.clear()
                elapsed = (datetime.now() - start).seconds
                pct = processed / total * 100
                print(f"  {processed:,}/{total:,} ({pct:.1f}%) — {elapsed}s")
        except Exception as e:
            skipped += 1
            logger.debug(f"Error: {filepath}: {e}")

    if batch_data:
        conn.executemany(
            "INSERT OR REPLACE INTO cves VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch_data
        )
        conn.executemany(
            "INSERT OR REPLACE INTO cves_fts(cve_id, search_text) VALUES (?,?)", batch_fts
        )
        conn.commit()

    conn.execute("INSERT OR REPLACE INTO rag_meta VALUES ('fts_total', ?)", (str(processed),))
    conn.execute("INSERT OR REPLACE INTO rag_meta VALUES ('fts_built_at', ?)", (datetime.now().isoformat(),))
    conn.commit()
    conn.close()

    elapsed = (datetime.now() - start).seconds
    print(f"[FTS] Done — {processed:,} indexed, {skipped} skipped in {elapsed}s")


# ══════════════════════════════════════════════════════════════════════════════
# INGESTION — OSV.dev secondary feed
# ══════════════════════════════════════════════════════════════════════════════

OSV_API = "https://api.osv.dev/v1"
SUPPORTED_ECOSYSTEMS = ["npm", "PyPI", "Go", "RubyGems", "Maven", "NuGet",
                        "Packagist", "crates.io", "Hex"]


def _parse_osv(vuln: dict) -> Optional[dict]:
    """Convert OSV record to cve_rag.db schema."""
    try:
        import requests as _req
        osv_id   = vuln.get("id", "")
        aliases  = vuln.get("aliases", [])
        cve_id   = next((a for a in aliases if a.startswith("CVE-")), osv_id)

        summary  = vuln.get("summary", "")
        details  = vuln.get("details", "")
        description = f"{summary} {details}".strip()[:2000]

        vendors, products, versions_list = [], [], []
        for aff in vuln.get("affected", []):
            pkg = aff.get("package", {})
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

        cwes = vuln.get("database_specific", {}).get("cwe_ids", [])
        refs = [r.get("url", "") for r in vuln.get("references", []) if r.get("url")][:5]
        published = vuln.get("published", "")
        year = published[:4] if published else ""

        search_text = " ".join(filter(None, [
            cve_id, description,
            " ".join(vendors), " ".join(products),
            " ".join(versions_list), " ".join(cwes)
        ]))

        return {
            "cve_id": cve_id, "year": year, "state": "PUBLISHED",
            "description": description,
            "vendors": json.dumps(vendors), "products": json.dumps(products),
            "versions": json.dumps(versions_list),
            "cvss_score": cvss_score, "cvss_vector": cvss_vector,
            "severity": severity, "cwes": json.dumps(cwes),
            "refs": json.dumps(refs), "date_published": published,
            "search_text": search_text, "source": "osv",
        }
    except Exception as e:
        logger.debug(f"OSV parse error: {e}")
        return None


def ingest_osv(ecosystems: List[str] = None, db_path: str = DB_PATH):
    """Fetch OSV.dev CVEs for given ecosystems and upsert into SQLite."""
    import requests as _req
    if ecosystems is None:
        ecosystems = ["npm", "PyPI", "Go"]

    conn = sqlite3.connect(db_path)
    _init_db(conn)

    for eco in ecosystems:
        print(f"[OSV] Fetching {eco}...")
        inserted = 0
        page_token = ""
        page = 0

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

            batch_data, batch_fts = [], []
            for v in vulns:
                row = _parse_osv(v)
                if row:
                    batch_data.append((
                        row["cve_id"], row["year"], row["state"],
                        row["description"], row["vendors"], row["products"],
                        row["versions"], row["cvss_score"], row["cvss_vector"],
                        row["severity"], row["cwes"], row["refs"],
                        row["date_published"], row["source"]
                    ))
                    batch_fts.append((row["cve_id"], row["search_text"]))

            if batch_data:
                conn.executemany(
                    "INSERT OR IGNORE INTO cves VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    batch_data
                )
                conn.executemany(
                    "INSERT OR IGNORE INTO cves_fts(cve_id, search_text) VALUES (?,?)",
                    batch_fts
                )
                conn.commit()
                inserted += len(batch_data)

            page += 1
            print(f"  page {page} — {inserted} inserted")
            page_token = data.get("next_page_token", "")
            if not page_token:
                break
            time.sleep(0.2)

        print(f"[OSV] {eco} done — {inserted} records")

    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# INGESTION — Vector embeddings (ChromaDB + all-MiniLM-L6-v2)
# ══════════════════════════════════════════════════════════════════════════════

def build_vector_index(db_path: str = DB_PATH, chroma_dir: str = CHROMA_DIR,
                       batch_size: int = 512, limit: int = 0):
    """
    Embed all CVE descriptions into ChromaDB for semantic ANN search.
    Run after build_fts_index(). Takes ~20-40 min on CPU for 337k CVEs.
    limit=0 means all. Set limit=10000 for a quick test.
    """
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise ImportError("pip install chromadb sentence-transformers")

    print("[VEC] Loading all-MiniLM-L6-v2...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    client = chromadb.PersistentClient(path=chroma_dir)
    col = client.get_or_create_collection("cves", metadata={"hnsw:space": "cosine"})

    conn = sqlite3.connect(db_path)
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
        metas = [{"severity": r["severity"] or "", "cvss_score": float(r["cvss_score"] or 0)} for r in batch]
        embeddings = model.encode(texts, show_progress_bar=False).tolist()
        col.add(ids=ids, embeddings=embeddings, metadatas=metas, documents=texts)
        if i % (batch_size * 20) == 0:
            print(f"  {min(i + batch_size, total):,}/{total:,}")

    print(f"[VEC] Done. ChromaDB has {col.count():,} vectors.")


# ══════════════════════════════════════════════════════════════════════════════
# QUERY ENGINE — Hybrid RRF search
# ══════════════════════════════════════════════════════════════════════════════

class RAGEngine:
    """
    Unified CVE retrieval engine.
    Auto-detects what's available (FTS5 only vs full hybrid) and uses the best.

    Usage:
        engine = RAGEngine()                    # auto-init, no args needed
        results = engine.search("react xss")   # hybrid search
        cve     = engine.get("CVE-2021-44228") # exact lookup
        stats   = engine.stats()
    """

    def __init__(self, db_path: str = DB_PATH, chroma_dir: str = CHROMA_DIR):
        self.db_path    = db_path
        self.chroma_dir = chroma_dir
        self._conn: Optional[sqlite3.Connection] = None
        self._col       = None
        self._model     = None
        self._has_vector = False
        self._init()

    def _init(self):
        if not os.path.exists(self.db_path):
            logger.warning(f"RAG DB not found at {self.db_path}. Run: python rag.py --build-fts")
            return
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA query_only=ON")

        # Try loading vector store
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
            if os.path.exists(self.chroma_dir):
                client = chromadb.PersistentClient(path=self.chroma_dir)
                self._col   = client.get_collection("cves")
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                self._has_vector = True
                logger.info(f"RAG: hybrid mode — {self._col.count():,} vectors + FTS5")
            else:
                logger.info("RAG: FTS5-only mode (run --build-vectors for hybrid)")
        except Exception as e:
            logger.info(f"RAG: FTS5-only mode ({e})")

    @property
    def ready(self) -> bool:
        return self._conn is not None

    @property
    def mode(self) -> str:
        return "hybrid (vector + FTS5 + alias resolver)" if self._has_vector else "FTS5 + alias resolver"

    # ── Internal search methods ───────────────────────────────────────────────

    def _fts5(self, terms: List[str], top_k: int = 50) -> List[Dict]:
        if not self._conn:
            return []
        fts_query = " OR ".join(f'"{t}"' for t in terms)
        try:
            rows = self._conn.execute("""
                SELECT c.* FROM cves c
                JOIN cves_fts f ON c.cve_id = f.cve_id
                WHERE cves_fts MATCH ?
                ORDER BY c.cvss_score DESC NULLS LAST
                LIMIT ?
            """, (fts_query, top_k)).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"FTS5 error: {e}")
            return []

    def _vector(self, query: str, top_k: int = 50) -> List[Dict]:
        if not self._has_vector:
            return []
        try:
            emb = self._model.encode([query]).tolist()
            res = self._col.query(query_embeddings=emb, n_results=top_k,
                                  include=["metadatas", "distances"])
            ids  = res["ids"][0]
            dists = res["distances"][0]
            out = []
            for cve_id, dist in zip(ids, dists):
                row = self._conn.execute("SELECT * FROM cves WHERE cve_id=?", (cve_id,)).fetchone()
                if row:
                    d = dict(row)
                    d["_vscore"] = round(1 - dist, 4)
                    out.append(d)
            return out
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []

    @staticmethod
    def _rrf(fts: List[Dict], vec: List[Dict], k: int = 60, top_n: int = 20) -> List[Dict]:
        """Reciprocal Rank Fusion + CVSS boost."""
        scores: Dict[str, float] = {}
        docs:   Dict[str, Dict]  = {}
        for rank, doc in enumerate(fts):
            cid = doc["cve_id"]
            scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
            docs[cid] = doc
        for rank, doc in enumerate(vec):
            cid = doc["cve_id"]
            scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
            docs[cid] = doc
        for cid, doc in docs.items():
            scores[cid] += (float(doc.get("cvss_score") or 0) / 10.0) * 0.05
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [docs[cid] for cid, _ in ranked[:top_n]]

    def _deserialize(self, doc: Dict) -> Dict:
        for field in ("vendors", "products", "versions", "cwes", "refs"):
            try:
                doc[field] = json.loads(doc.get(field) or "[]")
            except Exception:
                doc[field] = []
        doc["references"] = doc.pop("refs", [])
        return doc

    # ── Public API ────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 20) -> List[Dict]:
        """
        Main search. Alias-expands query, runs FTS5 + vector, merges via RRF.
        Falls back to FTS5-only if ChromaDB not available.
        """
        terms   = resolve_aliases(query)
        fts_res = self._fts5(terms, top_k=50)
        vec_res = self._vector(query, top_k=50)
        merged  = self._rrf(fts_res, vec_res, top_n=top_k)
        return [self._deserialize(d) for d in merged]

    def get(self, cve_id: str) -> Optional[Dict]:
        """Exact CVE ID lookup — fastest path."""
        if not self._conn:
            return None
        row = self._conn.execute(
            "SELECT * FROM cves WHERE cve_id=?", (cve_id.upper().strip(),)
        ).fetchone()
        return self._deserialize(dict(row)) if row else None

    def search_product(self, product: str, version: str = "", top_k: int = 10) -> List[Dict]:
        """Search by product + optional version."""
        q = f"{product} {version}".strip()
        return self.search(q, top_k=top_k)

    def by_severity(self, severity: str, year: str = "", limit: int = 20) -> List[Dict]:
        """Filter by severity + optional year."""
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
        """Search multiple products at once — used for nmap enrichment."""
        return {svc: self.search_product(*svc.split(None, 1), top_k=limit_per)
                if " " in svc else self.search_product(svc, top_k=limit_per)
                for svc in service_list}

    def stats(self) -> Dict:
        """Return DB statistics."""
        if not self._conn:
            return {"error": "DB not initialized"}
        total = self._conn.execute("SELECT COUNT(*) FROM cves").fetchone()[0]
        by_sev = dict(self._conn.execute(
            "SELECT severity, COUNT(*) FROM cves WHERE severity!='' GROUP BY severity ORDER BY COUNT(*) DESC"
        ).fetchall())
        by_year = dict(self._conn.execute(
            "SELECT year, COUNT(*) FROM cves GROUP BY year ORDER BY year DESC LIMIT 10"
        ).fetchall())
        by_source = dict(self._conn.execute(
            "SELECT source, COUNT(*) FROM cves GROUP BY source"
        ).fetchall())
        meta = dict(self._conn.execute("SELECT key, value FROM rag_meta").fetchall())
        vec_count = self._col.count() if self._has_vector else 0
        return {
            "total_cves": total,
            "by_severity": by_sev,
            "recent_years": by_year,
            "by_source": by_source,
            "vector_count": vec_count,
            "search_mode": self.mode,
            "fts_built_at": meta.get("fts_built_at", "not built"),
            "db_size_mb": round(os.path.getsize(self.db_path) / 1024 / 1024, 1),
        }

    def format_results(self, cves: List[Dict]) -> str:
        """Format CVE list into a clean report-ready string."""
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

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


# ══════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="CVE RAG System")
    parser.add_argument("--build-fts",     action="store_true", help="Index CVE JSON files into SQLite FTS5")
    parser.add_argument("--build-vectors", action="store_true", help="Embed CVE descriptions into ChromaDB")
    parser.add_argument("--ingest-osv",    nargs="+", metavar="ECO",
                        help="Fetch OSV.dev CVEs (e.g. npm PyPI Go RubyGems)")
    parser.add_argument("--search",  type=str, help="Hybrid search query")
    parser.add_argument("--lookup",  type=str, help="Exact CVE ID lookup")
    parser.add_argument("--stats",   action="store_true", help="Show DB statistics")
    parser.add_argument("--limit",   type=int, default=0, help="Limit for --build-vectors (0=all)")
    parser.add_argument("--top-k",   type=int, default=10)
    args = parser.parse_args()

    if args.build_fts:
        build_fts_index()
    elif args.build_vectors:
        build_vector_index(limit=args.limit)
    elif args.ingest_osv:
        ingest_osv(ecosystems=args.ingest_osv)
    elif args.stats:
        engine = RAGEngine()
        print(json.dumps(engine.stats(), indent=2))
    elif args.search:
        engine = RAGEngine()
        results = engine.search(args.search, top_k=args.top_k)
        print(f"Mode: {engine.mode}\n")
        print(engine.format_results(results))
    elif args.lookup:
        engine = RAGEngine()
        result = engine.get(args.lookup)
        print(json.dumps(result, indent=2) if result else "Not found")
    else:
        parser.print_help()
