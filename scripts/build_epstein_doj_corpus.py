#!/usr/bin/env python3
"""Build compact graph artifacts from the DOJ Epstein disclosure PDFs.

The worker intentionally downloads one DOJ file at a time, extracts derived
metadata and term co-mentions, then deletes the raw PDF unless --keep-raw is
set. It does not store raw PDF text in the site artifact directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - fallback exists for lean environments.
    BeautifulSoup = None


DOJ_BASE_URL = "https://www.justice.gov"
EPSTEIN_LIBRARY_URL = "https://www.justice.gov/epstein"
DOJ_DISCLOSURES_URL = "https://www.justice.gov/epstein/doj-disclosures"
USER_AGENT = "hodge-rank-clustering-local-ingest/1.0 (+https://www.justice.gov/epstein)"
AGE_COOKIE = "justiceGovAgeVerified=true"
PDF_CHUNK_SIZE = 1024 * 1024


DEFAULT_TERM_GROUPS: list[tuple[str, list[str]]] = [
    ("Jeffrey Epstein", ["Jeffrey Epstein", "Epstein"]),
    ("Ghislaine Maxwell", ["Ghislaine Maxwell", "Maxwell"]),
    ("Bill Clinton", ["Bill Clinton", "William J. Clinton", "William Jefferson Clinton", "President Clinton"]),
    ("Hillary Clinton", ["Hillary Clinton"]),
    ("Donald Trump", ["Donald Trump", "President Trump"]),
    ("Prince Andrew", ["Prince Andrew", "Andrew Mountbatten-Windsor", "Duke of York"]),
    ("Alan Dershowitz", ["Alan Dershowitz", "Dershowitz"]),
    ("Les Wexner", ["Les Wexner", "Leslie Wexner", "Wexner"]),
    ("Alexander Acosta", ["Alexander Acosta", "Alex Acosta", "Acosta"]),
    ("Jean-Luc Brunel", ["Jean-Luc Brunel", "Jean Luc Brunel", "Brunel"]),
    ("Sarah Kellen", ["Sarah Kellen", "Sarah Kensington", "Kellen"]),
    ("Nadia Marcinkova", ["Nadia Marcinkova", "Marcinkova"]),
    ("Palm Beach", ["Palm Beach"]),
    ("Little Saint James", ["Little Saint James", "Little St. James", "Little St James"]),
    ("Zorro Ranch", ["Zorro Ranch"]),
    ("Mar-a-Lago", ["Mar-a-Lago", "Mar a Lago"]),
    ("U.S. Virgin Islands", ["U.S. Virgin Islands", "US Virgin Islands", "United States Virgin Islands"]),
    ("FBI", ["FBI", "Federal Bureau of Investigation"]),
    ("DOJ", ["DOJ", "Department of Justice"]),
    ("Federal court", ["federal court", "district court", "court filing"]),
    ("JPMorgan", ["JPMorgan", "J.P. Morgan", "JP Morgan"]),
    ("Deutsche Bank", ["Deutsche Bank"]),
    ("flight log", ["flight log", "flight logs"]),
    ("subpoena", ["subpoena", "subpoenas"]),
    ("deposition", ["deposition", "depositions"]),
    ("redaction", ["redaction", "redacted", "DOJ Redaction"]),
    ("victim", ["victim", "victims"]),
    ("minor", ["minor", "minors"]),
]


@dataclass(frozen=True)
class ManifestEntry:
    id: str
    dataset: int
    file_name: str
    title: str
    url: str
    dataset_page_url: str
    content_length: int | None = None
    content_type: str | None = None


@dataclass(frozen=True)
class TermGroup:
    label: str
    aliases: tuple[str, ...]
    patterns: tuple[re.Pattern[str], ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def request(url: str, method: str = "GET", timeout: int = 60):
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": AGE_COOKIE,
        "Accept": "text/html,application/pdf,application/xhtml+xml,*/*;q=0.8",
    }
    req = Request(url, headers=headers, method=method)
    return urlopen(req, timeout=timeout)


def fetch_text(url: str, timeout: int = 60) -> str:
    with request(url, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for anchor in soup.find_all("a"):
            href = anchor.get("href") or ""
            text = anchor.get_text(" ", strip=True)
            if href:
                links.append((text, urljoin(base_url, href)))
        return links

    link_re = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
    tag_re = re.compile(r"<[^>]+>")
    links = []
    for href, text_html in link_re.findall(html):
        text = re.sub(r"\s+", " ", tag_re.sub(" ", text_html)).strip()
        links.append((text, urljoin(base_url, href)))
    return links


def dataset_number_from_url(url: str) -> int | None:
    match = re.search(r"data-set-(\d+)-files", url, re.I)
    if match:
        return int(match.group(1))
    match = re.search(r"DataSet%20(\d+)|DataSet\s*(\d+)", url, re.I)
    if match:
        return int(match.group(1) or match.group(2))
    return None


def discover_dataset_pages(timeout: int) -> list[tuple[int, str]]:
    html = fetch_text(DOJ_DISCLOSURES_URL, timeout=timeout)
    pages: dict[int, str] = {}
    for _text, href in extract_links(html, DOJ_DISCLOSURES_URL):
        number = dataset_number_from_url(href)
        if number is not None and "/epstein/doj-disclosures/" in href:
            pages[number] = href

    if not pages:
        pages = {
            number: f"{DOJ_DISCLOSURES_URL}/data-set-{number}-files"
            for number in range(1, 13)
        }
    return sorted(pages.items())


def probe_file(url: str, timeout: int) -> tuple[int | None, str | None]:
    try:
        with request(url, method="HEAD", timeout=timeout) as response:
            content_length = response.headers.get("Content-Length")
            return int(content_length) if content_length else None, response.headers.get("Content-Type")
    except (HTTPError, URLError, TimeoutError, OSError):
        return None, None


def discover_manifest(args: argparse.Namespace) -> list[ManifestEntry]:
    dataset_filter = parse_dataset_filter(args.datasets)
    entries: list[ManifestEntry] = []
    seen_urls: set[str] = set()

    for dataset, dataset_page_url in discover_dataset_pages(args.timeout):
        if dataset_filter and dataset not in dataset_filter:
            continue
        html = fetch_text(dataset_page_url, timeout=args.timeout)
        for text, href in extract_links(html, dataset_page_url):
            if ".pdf" not in href.lower() and ".pdf" not in text.lower():
                continue
            if href in seen_urls:
                continue
            seen_urls.add(href)
            file_name = unquote(Path(urlparse(href).path).name)
            if not file_name:
                continue
            doc_id = Path(file_name).stem
            content_length = None
            content_type = None
            if args.probe_sizes:
                content_length, content_type = probe_file(href, args.timeout)
            entries.append(
                ManifestEntry(
                    id=doc_id,
                    dataset=dataset,
                    file_name=file_name,
                    title=text or file_name,
                    url=href,
                    dataset_page_url=dataset_page_url,
                    content_length=content_length,
                    content_type=content_type,
                )
            )
        time.sleep(args.delay)

    return sorted(entries, key=lambda item: (item.dataset, item.file_name))


def write_manifest(entries: list[ManifestEntry], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generatedAt": utc_now(),
        "source": {
            "library": EPSTEIN_LIBRARY_URL,
            "dojDisclosures": DOJ_DISCLOSURES_URL,
            "note": "Discovered from official DOJ Epstein Library disclosure pages.",
        },
        "counts": {
            "documents": len(entries),
            "datasets": len({entry.dataset for entry in entries}),
        },
        "documents": [asdict(entry) for entry in entries],
    }
    path = output_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_manifest(path: Path) -> list[ManifestEntry]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [ManifestEntry(**item) for item in payload["documents"]]


def parse_dataset_filter(value: str | None) -> set[int]:
    if not value:
        return set()
    datasets: set[int] = set()
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_s, end_s = chunk.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            datasets.update(range(min(start, end), max(start, end) + 1))
        else:
            datasets.add(int(chunk))
    return datasets


def parse_term_groups(term_file: Path | None) -> list[TermGroup]:
    raw_groups = list(DEFAULT_TERM_GROUPS)
    if term_file is not None:
        raw_groups = []
        for line_number, raw_line in enumerate(term_file.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split("|") if part.strip()]
            if not parts:
                continue
            if len(parts) == 1:
                parts.append(parts[0])
            raw_groups.append((parts[0], parts[1:]))
            if len(parts[0]) < 2:
                raise ValueError(f"Invalid term label on line {line_number}: {raw_line!r}")

    groups = []
    for label, aliases in raw_groups:
        unique_aliases = tuple(dict.fromkeys(alias.strip() for alias in aliases if alias.strip()))
        if not unique_aliases:
            continue
        patterns = tuple(compile_alias_pattern(alias) for alias in unique_aliases)
        groups.append(TermGroup(label=label, aliases=unique_aliases, patterns=patterns))
    return groups


def compile_alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    escaped = escaped.replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.I)


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            dataset INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            dataset_page_url TEXT NOT NULL,
            status TEXT NOT NULL,
            page_count INTEGER,
            extracted_text_chars INTEGER,
            bytes_downloaded INTEGER,
            sha256 TEXT,
            error TEXT,
            processed_at TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS mentions (
            doc_id TEXT NOT NULL,
            term TEXT NOT NULL,
            count INTEGER NOT NULL,
            pages TEXT NOT NULL,
            PRIMARY KEY (doc_id, term),
            FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_mentions_term ON mentions(term)")
    return con


def already_processed(con: sqlite3.Connection, doc_id: str, retry_failed: bool) -> bool:
    row = con.execute("SELECT status FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if row is None:
        return False
    if retry_failed and row[0].endswith("_error"):
        return False
    return True


def safe_file_name(entry: ManifestEntry) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", entry.file_name)
    return f"dataset_{entry.dataset}_{clean}"


def download_pdf(entry: ManifestEntry, work_dir: Path, timeout: int) -> tuple[Path, str, int]:
    work_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = work_dir / safe_file_name(entry)
    sha256 = hashlib.sha256()
    total = 0
    first_chunk = b""

    with request(entry.url, timeout=timeout) as response:
        with pdf_path.open("wb") as handle:
            while True:
                chunk = response.read(PDF_CHUNK_SIZE)
                if not chunk:
                    break
                if not first_chunk:
                    first_chunk = chunk
                sha256.update(chunk)
                handle.write(chunk)
                total += len(chunk)

    if not first_chunk.lstrip().startswith(b"%PDF"):
        prefix = first_chunk[:80].decode("utf-8", "replace").replace("\n", " ")
        raise RuntimeError(f"DOJ response was not a PDF for {entry.url}: {prefix}")

    return pdf_path, sha256.hexdigest(), total


def extract_pages_with_pymupdf(pdf_path: Path) -> tuple[int, Iterable[str]]:
    import fitz  # type: ignore

    doc = fitz.open(pdf_path)
    try:
        page_count = doc.page_count
        texts = [page.get_text("text") or "" for page in doc]
        return page_count, texts
    finally:
        doc.close()


def extract_pages_with_pypdf(pdf_path: Path) -> tuple[int, Iterable[str]]:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        from PyPDF2 import PdfReader  # type: ignore

    reader = PdfReader(str(pdf_path))
    texts = []
    for page in reader.pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            texts.append("")
    return len(reader.pages), texts


def extract_pdf_mentions(pdf_path: Path, terms: list[TermGroup]) -> tuple[int, int, dict[str, dict[str, object]]]:
    try:
        page_count, page_texts = extract_pages_with_pymupdf(pdf_path)
    except ImportError:
        page_count, page_texts = extract_pages_with_pypdf(pdf_path)

    mention_counts: dict[str, Counter[int]] = {term.label: Counter() for term in terms}
    text_chars = 0
    for page_number, text in enumerate(page_texts, start=1):
        text_chars += len(text)
        if not text:
            continue
        for term in terms:
            count = sum(len(pattern.findall(text)) for pattern in term.patterns)
            if count:
                mention_counts[term.label][page_number] += count

    mentions: dict[str, dict[str, object]] = {}
    for label, page_counts in mention_counts.items():
        total = sum(page_counts.values())
        if total:
            mentions[label] = {
                "count": int(total),
                "pages": compact_pages(page_counts.keys()),
            }
    return page_count, text_chars, mentions


def compact_pages(pages: Iterable[int]) -> str:
    sorted_pages = sorted(set(pages))
    if not sorted_pages:
        return ""
    ranges = []
    start = previous = sorted_pages[0]
    for page in sorted_pages[1:]:
        if page == previous + 1:
            previous = page
            continue
        ranges.append(f"{start}-{previous}" if start != previous else str(start))
        start = previous = page
    ranges.append(f"{start}-{previous}" if start != previous else str(start))
    return ",".join(ranges)


def upsert_document(
    con: sqlite3.Connection,
    entry: ManifestEntry,
    status: str,
    page_count: int | None,
    text_chars: int | None,
    bytes_downloaded: int | None,
    sha256: str | None,
    error: str | None,
    mentions: dict[str, dict[str, object]] | None,
) -> None:
    con.execute(
        """
        INSERT INTO documents (
            id, dataset, file_name, title, url, dataset_page_url, status, page_count,
            extracted_text_chars, bytes_downloaded, sha256, error, processed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            dataset = excluded.dataset,
            file_name = excluded.file_name,
            title = excluded.title,
            url = excluded.url,
            dataset_page_url = excluded.dataset_page_url,
            status = excluded.status,
            page_count = excluded.page_count,
            extracted_text_chars = excluded.extracted_text_chars,
            bytes_downloaded = excluded.bytes_downloaded,
            sha256 = excluded.sha256,
            error = excluded.error,
            processed_at = excluded.processed_at
        """,
        (
            entry.id,
            entry.dataset,
            entry.file_name,
            entry.title,
            entry.url,
            entry.dataset_page_url,
            status,
            page_count,
            text_chars,
            bytes_downloaded,
            sha256,
            error,
            utc_now(),
        ),
    )
    con.execute("DELETE FROM mentions WHERE doc_id = ?", (entry.id,))
    if mentions:
        con.executemany(
            "INSERT INTO mentions (doc_id, term, count, pages) VALUES (?, ?, ?, ?)",
            [
                (entry.id, term, int(payload["count"]), str(payload["pages"]))
                for term, payload in sorted(mentions.items())
            ],
        )
    con.commit()


def process_entry(
    con: sqlite3.Connection,
    entry: ManifestEntry,
    terms: list[TermGroup],
    work_dir: Path,
    keep_raw: bool,
    timeout: int,
    min_text_chars_per_page: int,
) -> str:
    pdf_path: Path | None = None
    sha256 = None
    bytes_downloaded = None
    try:
        pdf_path, sha256, bytes_downloaded = download_pdf(entry, work_dir=work_dir, timeout=timeout)
        page_count, text_chars, mentions = extract_pdf_mentions(pdf_path, terms)
        min_usable_chars = max(1, page_count) * min_text_chars_per_page
        status = "processed" if text_chars >= min_usable_chars else "needs_ocr"
        upsert_document(
            con,
            entry=entry,
            status=status,
            page_count=page_count,
            text_chars=text_chars,
            bytes_downloaded=bytes_downloaded,
            sha256=sha256,
            error=None,
            mentions=mentions,
        )
        return f"{status} pages={page_count} chars={text_chars} mentions={len(mentions)} bytes={bytes_downloaded}"
    except Exception as exc:
        status = "download_error" if pdf_path is None else "extract_error"
        upsert_document(
            con,
            entry=entry,
            status=status,
            page_count=None,
            text_chars=None,
            bytes_downloaded=bytes_downloaded,
            sha256=sha256,
            error=f"{type(exc).__name__}: {exc}",
            mentions=None,
        )
        return f"{status} {type(exc).__name__}: {exc}"
    finally:
        if pdf_path is not None and pdf_path.exists() and not keep_raw:
            pdf_path.unlink()


def export_site_data(
    con: sqlite3.Connection,
    output_dir: Path,
    manifest_entries: list[ManifestEntry],
    terms: list[TermGroup],
    keep_raw: bool,
    work_dir: Path,
    max_graph_nodes: int,
    min_edge_docs: int,
    max_edge_sources: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    docs = [
        dict_from_row(row)
        for row in con.execute(
            """
            SELECT id, dataset, file_name, title, url, dataset_page_url, status, page_count,
                   extracted_text_chars, bytes_downloaded, sha256, error, processed_at
            FROM documents
            ORDER BY dataset, file_name
            """
        )
    ]
    with (output_dir / "documents.jsonl").open("w", encoding="utf-8") as handle:
        for doc in docs:
            handle.write(json.dumps(doc, sort_keys=True) + "\n")

    manifest_by_id = {entry.id: entry for entry in manifest_entries}
    mention_rows = [
        dict_from_row(row)
        for row in con.execute(
            """
            SELECT m.doc_id, m.term, m.count, m.pages, d.dataset, d.file_name, d.url
            FROM mentions m
            JOIN documents d ON d.id = m.doc_id
            ORDER BY m.term, m.doc_id
            """
        )
    ]

    term_counts: Counter[str] = Counter()
    term_doc_counts: Counter[str] = Counter()
    doc_terms: dict[str, set[str]] = defaultdict(set)
    term_examples: dict[str, list[dict[str, object]]] = defaultdict(list)

    for row in mention_rows:
        term = str(row["term"])
        doc_id = str(row["doc_id"])
        term_counts[term] += int(row["count"])
        term_doc_counts[term] += 1
        doc_terms[doc_id].add(term)
        if len(term_examples[term]) < max_edge_sources:
            term_examples[term].append(source_ref(row))

    selected_terms = [
        term
        for term, _count in sorted(
            term_doc_counts.items(),
            key=lambda item: (-item[1], -term_counts[item[0]], item[0].lower()),
        )[:max_graph_nodes]
    ]
    selected_term_set = set(selected_terms)

    nodes = []
    alias_map = {term.label: list(term.aliases) for term in terms}
    for term in selected_terms:
        nodes.append(
            {
                "id": slugify(term),
                "label": term,
                "kind": "source_text_term",
                "documentCount": int(term_doc_counts[term]),
                "mentionCount": int(term_counts[term]),
                "aliases": alias_map.get(term, [term]),
                "sampleSources": term_examples.get(term, []),
            }
        )

    edge_counts: Counter[tuple[str, str]] = Counter()
    edge_samples: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for doc_id, terms_in_doc in doc_terms.items():
        filtered_terms = sorted(term for term in terms_in_doc if term in selected_term_set)
        if len(filtered_terms) < 2:
            continue
        entry = manifest_by_id.get(doc_id)
        if entry is None:
            doc_row = next((doc for doc in docs if doc["id"] == doc_id), None)
            ref = source_ref(doc_row) if doc_row is not None else {"docId": doc_id}
        else:
            ref = {
                "docId": entry.id,
                "dataset": entry.dataset,
                "fileName": entry.file_name,
                "url": entry.url,
            }
        for left, right in combinations(filtered_terms, 2):
            edge_key = (left, right)
            edge_counts[edge_key] += 1
            refs = edge_samples[edge_key]
            if len(refs) < max_edge_sources:
                refs.append(ref)

    edges = []
    for (left, right), count in edge_counts.items():
        if count < min_edge_docs:
            continue
        edges.append(
            {
                "source": slugify(left),
                "target": slugify(right),
                "sourceLabel": left,
                "targetLabel": right,
                "relationship": "co_mentioned_in_same_doj_file",
                "documentCount": int(count),
                "sampleSources": edge_samples[(left, right)],
            }
        )
    edges.sort(key=lambda item: (-int(item["documentCount"]), item["sourceLabel"], item["targetLabel"]))

    (output_dir / "mention_nodes.json").write_text(json.dumps(nodes, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "mention_edges.json").write_text(json.dumps(edges, indent=2, sort_keys=True), encoding="utf-8")

    status_counts = Counter(doc["status"] for doc in docs)
    total_pages = sum(int(doc["page_count"] or 0) for doc in docs)
    total_text_chars = sum(int(doc["extracted_text_chars"] or 0) for doc in docs)
    total_bytes = sum(int(doc["bytes_downloaded"] or 0) for doc in docs)
    summary = {
        "generatedAt": utc_now(),
        "dataset": "DOJ Epstein Library disclosure PDFs",
        "source": {
            "library": EPSTEIN_LIBRARY_URL,
            "dojDisclosures": DOJ_DISCLOSURES_URL,
        },
        "counts": {
            "manifestDocuments": len(manifest_entries),
            "processedDocuments": len(docs),
            "statusCounts": dict(sorted(status_counts.items())),
            "totalPages": total_pages,
            "totalExtractedTextChars": total_text_chars,
            "totalBytesDownloaded": total_bytes,
            "documentsWithMentions": len(doc_terms),
            "distinctTermsWithMentions": len(term_doc_counts),
            "graphNodes": len(nodes),
            "graphEdges": len(edges),
        },
        "artifactFiles": {
            "manifest": "manifest.json",
            "documents": "documents.jsonl",
            "mentionNodes": "mention_nodes.json",
            "mentionEdges": "mention_edges.json",
            "sqliteCheckpoint": "epstein_processing.sqlite",
        },
        "rawDataRetained": keep_raw,
        "rawWorkDirectory": str(work_dir),
        "rawDirectoryExistsAfterRun": work_dir.exists(),
        "caveats": [
            "Edges mean terms were found in the same DOJ file, not that the people or places are connected by conduct.",
            "The default graph uses exact term groups and is not a full named-entity recognizer.",
            "Image-only, handwritten, or otherwise non-searchable PDFs are marked needs_ocr when no text is extracted.",
            "The DOJ library warns that search may be unreliable for some document formats and that sensitive personal information may remain despite redactions.",
            "Raw PDFs are deleted after processing unless --keep-raw is used.",
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")


def dict_from_row(row: sqlite3.Row | tuple[object, ...]) -> dict[str, object]:
    if isinstance(row, sqlite3.Row):
        return {key: row[key] for key in row.keys()}
    raise TypeError("sqlite3.Row factory is required")


def source_ref(row: dict[str, object]) -> dict[str, object]:
    return {
        "docId": row.get("doc_id") or row.get("id"),
        "dataset": row.get("dataset"),
        "fileName": row.get("file_name"),
        "url": row.get("url"),
    }


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="site/data/epstein", help="Directory for compact generated artifacts.")
    parser.add_argument("--db-path", default=None, help="SQLite checkpoint path. Defaults inside output-dir.")
    parser.add_argument("--work-dir", default=None, help="Temporary raw PDF directory. Defaults to .tmp/epstein_doj_raw_<pid>.")
    parser.add_argument("--manifest", default=None, help="Use an existing manifest JSON instead of rediscovering DOJ pages.")
    parser.add_argument("--manifest-only", action="store_true", help="Discover official DOJ files and stop before downloading PDFs.")
    parser.add_argument("--probe-sizes", action="store_true", help="Probe each PDF with HEAD while building the manifest.")
    parser.add_argument("--datasets", default=None, help="Dataset filter such as 1,3,8-12.")
    parser.add_argument("--max-docs", type=int, default=None, help="Maximum unprocessed documents to process in this run.")
    parser.add_argument("--delay", type=float, default=0.15, help="Polite delay between DOJ requests in seconds.")
    parser.add_argument("--timeout", type=int, default=120, help="Network timeout in seconds.")
    parser.add_argument("--keep-raw", action="store_true", help="Keep downloaded PDFs in work-dir instead of deleting them.")
    parser.add_argument("--force", action="store_true", help="Reprocess documents even when they already have a checkpoint row.")
    parser.add_argument("--retry-failed", action="store_true", help="Retry documents with *_error status.")
    parser.add_argument(
        "--min-text-chars-per-page",
        type=int,
        default=40,
        help="Below this extracted-text density, mark a PDF needs_ocr instead of processed.",
    )
    parser.add_argument("--terms-file", default=None, help="Optional term file; each line is Label|alias one|alias two.")
    parser.add_argument("--max-graph-nodes", type=int, default=80, help="Maximum term nodes exported to the graph.")
    parser.add_argument("--min-edge-docs", type=int, default=1, help="Minimum co-mentioned documents required for an edge.")
    parser.add_argument("--max-edge-sources", type=int, default=8, help="Maximum source document refs stored on each node or edge.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    work_dir = Path(args.work_dir) if args.work_dir else Path(".tmp") / f"epstein_doj_raw_{os.getpid()}"
    db_path = Path(args.db_path) if args.db_path else output_dir / "epstein_processing.sqlite"
    term_file = Path(args.terms_file) if args.terms_file else None

    if args.manifest:
        manifest_entries = load_manifest(Path(args.manifest))
    else:
        manifest_entries = discover_manifest(args)
    manifest_path = write_manifest(manifest_entries, output_dir)
    print(f"Manifest: {manifest_path} ({len(manifest_entries)} DOJ PDF links)", flush=True)

    if args.manifest_only:
        return 0

    terms = parse_term_groups(term_file)
    con = init_db(db_path)
    con.row_factory = sqlite3.Row

    try:
        pending = []
        for entry in manifest_entries:
            if args.force or not already_processed(con, entry.id, args.retry_failed):
                pending.append(entry)
        if args.max_docs is not None:
            pending = pending[: args.max_docs]

        print(f"Processing {len(pending)} pending DOJ PDFs into {db_path}", flush=True)
        for index, entry in enumerate(pending, start=1):
            result = process_entry(
                con,
                entry=entry,
                terms=terms,
                work_dir=work_dir,
                keep_raw=args.keep_raw,
                timeout=args.timeout,
                min_text_chars_per_page=args.min_text_chars_per_page,
            )
            print(f"[{index}/{len(pending)}] {entry.id}: {result}", flush=True)
            time.sleep(args.delay)

        if not args.keep_raw and work_dir.exists():
            shutil.rmtree(work_dir)

        export_site_data(
            con,
            output_dir=output_dir,
            manifest_entries=manifest_entries,
            terms=terms,
            keep_raw=args.keep_raw,
            work_dir=work_dir,
            max_graph_nodes=args.max_graph_nodes,
            min_edge_docs=args.min_edge_docs,
            max_edge_sources=args.max_edge_sources,
        )
        print(f"Exported compact site artifacts to {output_dir}", flush=True)
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
