import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from docx import Document
from pypdf import PdfReader

from app.config import MAX_RESUME_TEXT

URL_PATTERN = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
PROJECT_SECTIONS = {"projects", "personal projects", "selected projects", "academic projects", "technical projects", "project experience"}
OTHER_SECTIONS = {"experience", "work experience", "education", "skills", "technical skills", "certifications", "achievements", "coding profiles", "profiles", "competitive programming", "languages", "contact", "summary", "publications", "links"}
NON_PROJECT_HOSTS = {
    "linkedin.com", "www.linkedin.com", "twitter.com", "x.com", "youtube.com", "www.youtube.com", "youtu.be",
    "leetcode.com", "www.leetcode.com", "codeforces.com", "www.codeforces.com", "codechef.com", "www.codechef.com",
    "hackerrank.com", "www.hackerrank.com", "hackerearth.com", "www.hackerearth.com", "atcoder.jp",
    "topcoder.com", "www.topcoder.com", "kaggle.com", "www.kaggle.com", "geeksforgeeks.org", "www.geeksforgeeks.org",
    "codingninjas.com", "www.codingninjas.com", "codolio.com", "www.codolio.com", "medium.com", "dev.to",
    "docs.google.com", "drive.google.com", "play.google.com",
}
DEMO_HOST_SUFFIXES = (
    "vercel.app", "netlify.app", "github.io", "onrender.com", "pages.dev", "web.app",
    "firebaseapp.com", "herokuapp.com", "railway.app", "fly.dev", "streamlit.app",
    "hf.space", "replit.app", "glitch.me", "surge.sh",
)
SNIPPET_STOPWORDS = {"the", "and", "for", "with", "from", "experience", "knowledge", "skill", "skills", "ability", "proficient", "strong", "working"}
JOB_STOPWORDS = SNIPPET_STOPWORDS | {"this", "that", "will", "you", "your", "our", "their", "they", "are", "not", "have", "has", "who", "what", "when", "where", "which", "while", "about", "across", "within", "role", "team", "company", "position", "candidate", "responsibilities", "responsibility", "requirements", "required", "preferred", "including", "support", "supporting", "related", "ability", "work", "working", "years", "year", "must", "should", "can", "using", "used", "use", "ensure", "provide", "develop", "building", "build", "strong", "excellent", "good", "skills", "skill"}


def extract_resume_text(path: Path) -> str:
    linked_urls = []
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path), strict=False)
        if reader.is_encrypted:
            raise ValueError("encrypted_pdf")
        page_text = []
        for page_number, page in enumerate(reader.pages[:150], 1):
            page_links = []
            for annotation_ref in page.get("/Annots", []) or []:
                try:
                    annotation = annotation_ref.get_object()
                    target = (annotation.get("/A") or {}).get("/URI")
                    if isinstance(target, str) and target.lower().startswith(("http://", "https://")):
                        linked_urls.append(target)
                        page_links.append(f"PDF hyperlink (page {page_number}): {target}")
                except (AttributeError, TypeError):
                    continue
            page_text.append("\n".join([f"[[PDF PAGE {page_number}]]", page.extract_text() or "", *page_links]))
        text = "\n".join(page_text)
    elif path.suffix.lower() == ".docx":
        document = Document(str(path))
        paragraphs = list(document.paragraphs)
        paragraphs.extend(paragraph for table in document.tables for row in table.rows
                          for cell in row.cells for paragraph in cell.paragraphs)
        parts = []
        for paragraph in paragraphs:
            paragraph_text = paragraph.text
            for hyperlink in paragraph._p.xpath(".//w:hyperlink"):
                rel_id = hyperlink.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                relation = document.part.rels.get(rel_id) if rel_id else None
                target = getattr(relation, "target_ref", "") if relation else ""
                link_text = "".join(node.text or "" for node in hyperlink.xpath(".//w:t"))
                if target.lower().startswith(("http://", "https://")):
                    linked_urls.append(target)
                    if target not in paragraph_text:
                        paragraph_text += f" {link_text}: {target}" if link_text else f" {target}"
            parts.append(paragraph_text)
        text = "\n".join(parts)
    else:
        raise ValueError("unsupported_file")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    if not text:
        raise ValueError("empty_text")
    linked_urls = list(dict.fromkeys(linked_urls))[:12]
    link_text = "\n".join(f"Resume hyperlink: {url}" for url in linked_urls if url not in text)
    if link_text:
        remaining = max(0, MAX_RESUME_TEXT - len(link_text) - 2)
        text = text[:remaining].rstrip() + "\n\n" + link_text
    return text[:MAX_RESUME_TEXT]


def find_project_urls(text: str, limit: int = 12) -> list[str]:
    seen, found = set(), []
    for value in URL_PATTERN.findall(text):
        url = value.rstrip(".,;:!?)]")
        if url not in seen:
            seen.add(url)
            found.append(url)
        if len(found) >= limit:
            break
    return found


def project_claims_for_urls(text: str, urls: list[str]) -> list[dict]:
    """Keep a separate nearby description for every occurrence of each project link."""
    claims, seen = [], set()
    for url in urls:
        for match in re.finditer(re.escape(url), text, re.IGNORECASE):
            start = match.start()
            pdf_page_scope = "PDF hyperlink" in text[max(0, text.rfind("\n", 0, start) + 1):start]
            if pdf_page_scope:
                page_start = text.rfind("[[PDF PAGE", 0, start)
                next_page = text.find("[[PDF PAGE", start)
                left = page_start if page_start >= 0 else max(0, start - 800)
                right = next_page if next_page >= 0 else min(len(text), start + 3000)
                excerpt = re.sub(r"\s+", " ", text[left:right]).strip()[:1600]
            else:
                previous_line = text.rfind("\n", 0, start - 1) if start else 0
                left = text.rfind("\n", 0, previous_line) + 1 if previous_line > 0 else 0
                right = text.find("\n", start + len(url))
                if right >= 0:
                    next_line = text.find("\n", right + 1)
                    right = next_line if next_line >= 0 else right
                if right < 0:
                    right = min(len(text), start + len(url) + 500)
                excerpt = re.sub(r"\s+", " ", text[left:min(right, start + len(url) + 800)]).strip()[:800]
            key = (url.casefold(), excerpt.casefold())
            if excerpt and key not in seen:
                claims.append({"url": url, "excerpt": excerpt,
                               "scope": "pdf_page" if pdf_page_scope else "near_link"})
                seen.add(key)
    return claims


def extract_project_links(text: str, limit: int = 12) -> list[dict]:
    """Extract only links tied to a resume project, not general profile links."""
    lines = text.splitlines()
    offsets = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line) + 1

    def line_number(position: int) -> int:
        index = 0
        while index + 1 < len(offsets) and offsets[index + 1] <= position:
            index += 1
        return index

    def heading_kind(value: str) -> str | None:
        normalized = re.sub(r"[^a-z ]", "", value.casefold()).strip()
        if normalized in PROJECT_SECTIONS:
            return "projects"
        if normalized in OTHER_SECTIONS:
            return "other"
        return None

    section_state = []
    active_section = ""
    for line in lines:
        kind = heading_kind(line)
        if kind:
            active_section = kind
        section_state.append(active_section)

    results, seen = [], set()
    for match in URL_PATTERN.finditer(text):
        url = match.group(0).rstrip(".,;:!?)]}")
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        if host in {item.removeprefix("www.") for item in NON_PROJECT_HOSTS}:
            continue
        index = line_number(match.start())
        line = lines[index] if index < len(lines) else ""
        context_start = max(0, index - 4)
        context_lines = lines[context_start:min(len(lines), index + 3)]
        context = " ".join(context_lines)
        pdf_link = "PDF hyperlink" in line
        pdf_project_names = []
        project_section = index < len(section_state) and section_state[index] == "projects"
        if pdf_link:
            page_match = re.search(r"PDF hyperlink \(page (\d+)\)", line, re.I)
            page_number = page_match.group(1) if page_match else ""
            page_start = text.find(f"[[PDF PAGE {page_number}]]") if page_number else -1
            page_end = text.find("[[PDF PAGE", page_start + 1) if page_start >= 0 else -1
            page_text = text[page_start:page_end if page_end >= 0 else len(text)] if page_start >= 0 else ""
            page_lines = page_text.splitlines()
            project_heading = next((i for i, item in enumerate(page_lines) if heading_kind(item) == "projects"), None)
            if project_heading is not None:
                section_end = next((i for i in range(project_heading + 1, len(page_lines)) if heading_kind(page_lines[i]) == "other"), len(page_lines))
                project_page_lines = page_lines[project_heading:section_end]
                context = " ".join(project_page_lines)
                for page_line in project_page_lines[1:]:
                    title_line = re.sub(r"https?://\S+", "", page_line)
                    title_line = re.sub(r"^\s*(?:github|live demo|demo|source code|repository|repo|deployed|hosted)\s*[:\-]?\s*", "", title_line, flags=re.I)
                    title_line = re.split(r"\s+(?:\||•|·|—|–)\s+", title_line, maxsplit=1)[0].strip(" -*\t|:")
                    title_line = re.sub(r"\s*\([^)]{1,40}\)\s*$", "", title_line).strip()
                    starts_description = bool(re.match(r"^(built|developed|created|implemented|designed|engineered|allows|enables|provides|supports|used|using|responsible|worked|integrated)\b", title_line, re.I))
                    if not starts_description and not title_line.endswith((".", "!", "?")) and 2 <= len(title_line.split()) <= 8:
                        if title_line.casefold() not in PROJECT_SECTIONS | OTHER_SECTIONS and title_line not in pdf_project_names:
                            pdf_project_names.append(title_line[:100])
                project_section = True

        github = host in {"github.com"}
        path_parts = [part for part in parsed.path.split("/") if part]
        is_repository = github and len(path_parts) >= 2 and path_parts[1].lower() not in {"repositories", "projects", "topics", "settings", "followers", "following"}
        context_text = URL_PATTERN.sub(" ", context)
        context_text = re.sub(r"PDF hyperlink \(page \d+\):?", " ", context_text, flags=re.I)
        explicit_project_context = bool(re.search(r"\b(project|repository|repo|source code|live demo|demo|deployed|hosted)\b", context_text, re.I))
        if github:
            # A profile is not a project link. Stage 2 checks only repositories
            # explicitly named in the resume, never other profile repositories.
            if not is_repository:
                continue
            if not project_section and not explicit_project_context:
                continue
        else:
            demo_link = bool(re.search(r"\b(live demo|demo|deployed|hosted|live site|website)\b", context_text, re.I))
            known_demo_host = (any(host == suffix or host.endswith("." + suffix) for suffix in DEMO_HOST_SUFFIXES)
                               or (host == "huggingface.co" and parsed.path.startswith("/spaces/")))
            # Hidden PDF links have no reliable anchor text. Accept only known
            # hosted-app domains there; for visible links require demo context.
            if not known_demo_host and (pdf_link or not (demo_link and explicit_project_context)):
                continue

        clean_records = []
        for offset, item in enumerate(context_lines):
            cleaned = re.sub(r"https?://\S+", "", item)
            cleaned = re.sub(r"\[\[PDF PAGE \d+\]\]|PDF hyperlink \(page \d+\):?", "", cleaned, flags=re.I)
            cleaned = re.sub(r"^\s*(?:github\s+profile|github|live demo|demo|source code|repository|repo|deployed|hosted|profile)\s*[:\-]?\s*", "", cleaned, flags=re.I)
            cleaned = re.sub(r"\s+", " ", cleaned).strip(" -*\t|:")
            if cleaned and cleaned.casefold() not in PROJECT_SECTIONS and cleaned.casefold() not in OTHER_SECTIONS:
                clean_records.append((context_start + offset, cleaned))
        project_name = ""
        project_title_line = None
        for line_index, candidate in reversed([item for item in clean_records if item[0] <= index]):
            titled = re.sub(r"^project\s*\d*\s*[:#-]\s*", "", candidate, flags=re.I)
            if re.search(r"\b(github|repository|repo|live demo|demo|source code|deployed|hosted)\b", titled, re.I):
                titled = re.sub(r"\b(github|repository|repo|live demo|demo|source code|deployed|hosted)\b", "", titled, flags=re.I).strip(" -:|")
            titled = re.split(r"\s+(?:\||•|·|—|–)\s+", titled, maxsplit=1)[0]
            titled = re.sub(r"\s*\([^)]{1,40}\)\s*$", "", titled).strip()
            if re.fullmatch(r"(?:github\s*)?(?:profile|account|link|url|repository|repo|demo|source code)", titled, re.I):
                continue
            starts_description = bool(re.match(r"^(built|developed|created|implemented|designed|engineered|allows|enables|provides|supports|used|using|responsible|worked|integrated)\b", titled, re.I))
            looks_like_sentence = titled.endswith((".", "!", "?")) or len(titled.split()) > 9
            if not starts_description and not looks_like_sentence and len(re.findall(r"[A-Za-z]{3,}", titled)) >= 2:
                project_name = titled[:100]
                project_title_line = line_index
                break
        if not project_name and is_repository:
            project_name = re.sub(r"[-_]+", " ", path_parts[1].removesuffix(".git"))
        if pdf_link and len(pdf_project_names) == 1:
            project_name = pdf_project_names[0]
        project_group_key = re.sub(r"[^a-z0-9]+", "-", project_name.casefold()).strip("-") or url.casefold()
        if pdf_link:
            excerpt = context[:1600]
        else:
            summary_parts = [project_name] if project_name else []
            for line_index, candidate in clean_records:
                if project_title_line is not None and line_index <= project_title_line:
                    continue
                if line_index > index + 2 or candidate == project_name:
                    continue
                starts_description = bool(re.match(r"^(built|developed|created|implemented|designed|engineered|allows|enables|provides|supports|used|using|responsible|worked|integrated)\b", candidate, re.I))
                looks_like_title = len(candidate.split()) <= 6 and not re.search(r"[.!?]", candidate) and not starts_description
                if looks_like_title and summary_parts:
                    break
                if candidate not in summary_parts:
                    summary_parts.append(candidate)
                if len(summary_parts) >= 3:
                    break
            excerpt = " ".join(summary_parts)[:320]
        key = (url.casefold(), project_group_key)
        if key in seen:
            continue
        results.append({"url": url, "project_name": project_name, "project_group_key": project_group_key,
                        "excerpt": excerpt, "scope": "pdf_page" if pdf_link else "near_link"})
        seen.add(key)
        if len(results) >= limit:
            break
    return results


def parse_criteria(mandatory: str = "", preferred: str = "", equivalents: str = "") -> list[dict]:
    criteria = []
    for category, text in (("mandatory", mandatory), ("preferred", preferred), ("equivalent", equivalents)):
        names = list(dict.fromkeys(line.strip(" -*\t") for line in text.splitlines() if line.strip(" -*\t")))
        if len(names) > 12 or any(len(name) > 120 for name in names):
            raise ValueError("criteria_invalid")
        criteria.extend({"name": name, "category": category} for name in names)
    if len(criteria) > 24:
        raise ValueError("criteria_invalid")
    return criteria


def extract_job_terms(job_description: str, limit: int = 12) -> list[dict]:
    words = [word.casefold() for word in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.]{2,}", job_description)
             if word.casefold() not in JOB_STOPWORDS]
    counts = Counter(words)
    first_position = {word: words.index(word) for word in counts}
    selected = sorted(counts, key=lambda word: (-counts[word], first_position[word]))[:limit]
    return [{"name": word} for word in selected]


def criterion_excerpt(resume_text: str, criterion: str) -> str:
    normalized = re.sub(r"\s+", " ", resume_text).strip()
    for term in re.findall(r"[a-zA-Z0-9+#.]{2,}", criterion):
        if term.casefold() in SNIPPET_STOPWORDS:
            continue
        match = re.search(r"(?<![a-zA-Z0-9])" + re.escape(term) + r"(?![a-zA-Z0-9])", normalized, re.IGNORECASE)
        if match:
            start, end = max(0, match.start() - 90), min(len(normalized), match.end() + 130)
            return ("…" if start else "") + normalized[start:end] + ("…" if end < len(normalized) else "")
    return ""
