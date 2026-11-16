"""Bounded, public project checks. This module does not call another AI provider."""

import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from app.config import GITHUB_TOKEN

USER_AGENT = "StudentResumeScreening/1.0 (public project evidence checker)"
MAX_SITE_BYTES = 500_000
MAX_README_CHARS = 120_000
NON_PROJECT_HOSTS = {
    "linkedin.com", "twitter.com", "x.com", "youtube.com", "youtu.be", "docs.google.com",
    "drive.google.com", "play.google.com", "leetcode.com", "codeforces.com", "codechef.com",
    "hackerrank.com", "hackerearth.com", "atcoder.jp", "topcoder.com", "kaggle.com",
}
DEMO_HOST_SUFFIXES = (
    "vercel.app", "netlify.app", "github.io", "onrender.com", "pages.dev", "web.app",
    "firebaseapp.com", "herokuapp.com", "railway.app", "fly.dev", "streamlit.app",
    "hf.space", "replit.app", "glitch.me", "surge.sh",
)
STOP_WORDS = {
    "experience", "knowledge", "ability", "strong", "skills", "skill", "working", "using",
    "with", "and", "the", "for", "of", "in", "to", "development", "develop", "proficiency",
    "familiarity", "understanding", "demonstrated", "proven", "years", "including", "build",
    "project", "application", "app", "built", "used", "using", "developed", "created", "implemented",
    "frontend", "backend", "fullstack", "full", "stack", "resume", "candidate", "github", "http", "https",
}
TECHNOLOGY_PATTERNS = {
    "React": r"\breact(?:\.js)?\b", "Next.js": r"\bnext(?:\.js)?\b",
    "Vue": r"\bvue(?:\.js)?\b", "Angular": r"\bangular\b",
    "Node.js": r"\bnode(?:\.js)?\b", "Express": r"\bexpress(?:\.js)?\b",
    "Python": r"\bpython\b", "Django": r"\bdjango\b", "FastAPI": r"\bfastapi\b",
    "Flask": r"\bflask\b", "Java": r"\bjava\b", "Spring": r"\bspring(?: boot)?\b",
    "JavaScript": r"\bjavascript\b", "TypeScript": r"\btypescript\b",
    "PostgreSQL": r"\bpostgres(?:ql)?\b", "MySQL": r"\bmysql\b", "MongoDB": r"\bmongo(?:db)?\b",
    "Redis": r"\bredis\b", "Docker": r"\bdocker\b", "AWS": r"\baws\b|amazon web services",
    "Azure": r"\bazure\b", "Google Cloud": r"\bgoogle cloud\b|\bgcp\b",
    "Tailwind CSS": r"\btailwind(?: css)?\b", "GraphQL": r"\bgraphql\b",
    "REST APIs": r"\brest(?:ful)? api(?:s)?\b", "HTML": r"\bhtml5?\b", "CSS": r"\bcss3?\b",
    "C++": r"\bc\+\+\b", "C#": r"\bc#\b", "Go": r"\bgolang\b",
}
TECHNOLOGY_FAMILIES = (
    {"React", "Next.js", "Vue", "Angular"},
    {"Node.js", "Express", "Python", "Django", "FastAPI", "Flask", "Java", "Spring"},
    {"PostgreSQL", "MySQL", "MongoDB"},
)
MANIFESTS = ("package.json", "requirements.txt", "pyproject.toml", "Pipfile", "go.mod",
             "Cargo.toml", "pom.xml", "build.gradle", "composer.json", "Gemfile")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_public_url(url: str) -> tuple[str, str, int]:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("unsafe_url")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in (80, 443):
        raise ValueError("unsafe_url")
    hostname = parsed.hostname.rstrip(".").encode("idna").decode("ascii")
    try:
        resolved = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError:
        raise ValueError("host_unavailable") from None
    addresses = {item[4][0] for item in resolved}
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("unsafe_url")
    return parsed.scheme, hostname, port


class _PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.skip_depth = 0
        self.title = ""
        self.description = ""
        self.parts = []
        self.assets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
        if tag.lower() == "meta" and attrs.get("name", "").casefold() == "description":
            self.description = attrs.get("content", "")[:500]
        if tag.lower() == "script" and attrs.get("src"):
            self.assets.append(attrs["src"])
        if tag.lower() == "link" and attrs.get("href") and ("stylesheet" in attrs.get("rel", "").casefold() or attrs.get("as") == "script"):
            self.assets.append(attrs["href"])
        if tag.lower() == "form":
            self.parts.append("[form]")

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if not self.skip_depth:
            stripped = data.strip()
            if stripped:
                self.parts.append(stripped)


def _website_check(url: str) -> dict:
    current = url
    opener = urllib.request.build_opener(NoRedirect())
    for _ in range(4):
        try:
            _validate_public_url(current)
            request = urllib.request.Request(current, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
            try:
                response = opener.open(request, timeout=6)
            except urllib.error.HTTPError as exc:
                if exc.code in (301, 302, 303, 307, 308) and exc.headers.get("Location"):
                    current = urllib.parse.urljoin(current, exc.headers["Location"])
                    continue
                return {"source_type": "website", "url": current, "reachable": False, "health": "unavailable",
                        "http_status": exc.code, "title": "", "description": "", "evidence": []}
            with response:
                status = response.status
                content_type = response.headers.get_content_type()
                if status != 200:
                    return {"source_type": "website", "url": current, "reachable": False, "health": "unavailable",
                            "http_status": status, "title": "", "description": "", "evidence": []}
                if content_type not in {"text/html", "application/xhtml+xml"}:
                    return {"source_type": "website", "url": current, "reachable": True, "health": "needs_review",
                            "http_status": status, "title": "", "description": "", "evidence": []}
                html = response.read(MAX_SITE_BYTES + 1)[:MAX_SITE_BYTES].decode("utf-8", errors="replace")
            parser = _PageText()
            parser.feed(html)
            title = re.sub(r"\s+", " ", parser.title).strip()[:300]
            page_text = re.sub(r"\s+", " ", " ".join(parser.parts))[:80_000]
            title_looks_error = bool(re.search(r"\b(404|500|error|not found|unavailable)\b", title, re.I))
            # A small, bounded request to a couple of same-host JS/CSS assets checks
            # that the page shell's dependencies are being served too.
            asset_checks = []
            for asset in parser.assets[:2]:
                asset_url = urllib.parse.urljoin(current, asset)
                try:
                    _validate_public_url(asset_url)
                    asset_req = urllib.request.Request(asset_url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-1023"})
                    with urllib.request.build_opener(NoRedirect()).open(asset_req, timeout=4) as asset_response:
                        asset_checks.append({"url": asset_url, "status": asset_response.status,
                                             "ok": asset_response.status < 400})
                except Exception:
                    asset_checks.append({"url": asset_url, "status": None, "ok": False})
            healthy = bool(title and page_text and not title_looks_error and all(item["ok"] for item in asset_checks))
            return {"source_type": "website", "url": current, "reachable": True,
                    "http_status": status, "health": "healthy_shell" if healthy else "needs_review",
                    "checks": {"http_200": True, "html_title": bool(title), "visible_text": bool(page_text),
                               "title_error": title_looks_error, "assets": asset_checks},
                    "title": title, "description": parser.description, "assets": parser.assets[:2],
                    "text": page_text}
        except ValueError as exc:
            return {"source_type": "website", "url": current, "reachable": False, "health": "unavailable",
                    "http_status": None, "error_code": str(exc), "title": "", "description": "", "evidence": []}
        except (urllib.error.URLError, TimeoutError, OSError):
            return {"source_type": "website", "url": current, "reachable": False, "health": "unavailable",
                    "http_status": None, "error_code": "site_unavailable", "title": "", "description": "", "evidence": []}
    return {"source_type": "website", "url": current, "reachable": False, "health": "unavailable",
            "http_status": None, "error_code": "too_many_redirects", "title": "", "description": "", "evidence": []}


def _github_request(path: str):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    request = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = response.read(2_000_000)
            return json.loads(data), response.headers
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429) and (exc.headers.get("X-RateLimit-Remaining") == "0" or exc.code == 429):
            raise RuntimeError("github_rate_limited") from None
        if exc.code in (408, 500, 502, 503, 504):
            raise RuntimeError("github_temporarily_unavailable") from None
        return None, exc.headers
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError("github_temporarily_unavailable") from None


def _raw_github_file(owner: str, repo: str, branch: str, path: str, max_chars: int = 50_000) -> str:
    url = ("https://raw.githubusercontent.com/" + urllib.parse.quote(owner, safe="") + "/" +
           urllib.parse.quote(repo, safe="") + "/" + urllib.parse.quote(branch, safe="/") + "/" +
           urllib.parse.quote(path, safe="/"))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Range": f"bytes=0-{max_chars}"})
    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            return response.read(max_chars + 1).decode("utf-8", errors="replace")[:max_chars]
    except (urllib.error.URLError, TimeoutError, OSError):
        return ""


PROFILE_MATCH_STOP_WORDS = STOP_WORDS | {
    "project", "system", "website", "web", "site", "platform", "full", "stack", "frontend", "backend",
    "management", "application", "software", "based", "responsive", "personal", "portfolio", "using",
    "built", "developed", "created", "designed", "tool", "tools", "service", "online", "student",
    "react", "next", "nextjs", "node", "nodejs", "python", "django", "fastapi", "flask", "javascript",
    "typescript", "html", "css", "mongodb", "postgresql", "mysql", "api", "apis",
}


def _profile_repo_match(name: str, claim: str) -> float:
    """Only associate a profile repo when its name clearly appears in the nearby project claim."""
    normalized_name = re.sub(r"[^a-z0-9]+", " ", name.casefold()).strip()
    claim_without_urls = re.sub(r"https?://\S+", " ", claim.casefold())
    normalized_claim = re.sub(r"[^a-z0-9]+", " ", claim_without_urls)
    if len(normalized_name) >= 5 and re.search(r"(?<![a-z0-9])" + re.escape(normalized_name) + r"(?![a-z0-9])", normalized_claim):
        return 1.0
    name_tokens = {token for token in normalized_name.split() if len(token) >= 3 and token not in PROFILE_MATCH_STOP_WORDS}
    claim_tokens = {token for token in re.findall(r"[a-z0-9]{3,}", normalized_claim) if token not in PROFILE_MATCH_STOP_WORDS}
    overlap = name_tokens & claim_tokens
    if len(name_tokens) >= 2 and len(overlap) >= 2:
        return len(overlap) / len(name_tokens)
    if len(name_tokens) == 1 and len(next(iter(name_tokens))) >= 8 and overlap:
        return 0.8
    return 0.0


def _github_sources(url: str, repo_limit: int = 2, project_claims: list[dict] | None = None) -> list[dict]:
    parsed = urllib.parse.urlsplit(url)
    if (parsed.hostname or "").lower().removeprefix("www.") != "github.com":
        return []
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return []
    if parts[1].lower() in {"repositories", "projects", "topics", "settings", "followers", "following"}:
        return []
    owner, name = parts[0], parts[1].removesuffix(".git")
    repo_data, _ = _github_request(f"/repos/{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(name, safe='')}")
    if not isinstance(repo_data, dict):
        return []
    repositories = [repo_data]
    output = []
    for repo_data in repositories[:repo_limit]:
        owner = (repo_data.get("owner") or {}).get("login", "")
        name = repo_data.get("name", "")
        if not owner or not name:
            continue
        description = repo_data.get("description") or ""
        source_url = repo_data.get("html_url") or f"https://github.com/{owner}/{name}"
        evidence_parts = [description]
        manifest_paths = []
        manifest_parts = []
        source_paths = []
        source_parts = []
        branch = repo_data.get("default_branch") or "main"
        tree, _ = _github_request(f"/repos/{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(name, safe='')}/git/trees/{urllib.parse.quote(branch, safe='')}?recursive=1")
        readme = ""
        if isinstance(tree, dict):
            available = {item.get("path") for item in tree.get("tree", []) if item.get("type") == "blob"}
            readme_path = next((path for path in available if "/" not in path and path.casefold() in {"readme.md", "readme.rst", "readme.txt", "readme"}), None)
            if readme_path:
                readme = _raw_github_file(owner, name, branch, readme_path, MAX_README_CHARS)
            manifest_paths = [path for path in MANIFESTS if path in available][:4]
        readme_technologies = technologies_in(readme)
        evidence_parts.append(readme)
        for manifest_path in manifest_paths:
            manifest_text = _raw_github_file(owner, name, branch, manifest_path)[:30_000]
            if manifest_text:
                manifest_parts.append(manifest_text)
                evidence_parts.append(manifest_text)
        if isinstance(tree, dict):
            source_paths = [
                item["path"] for item in tree.get("tree", [])
                if item.get("type") == "blob"
                and item.get("path", "").lower().endswith((".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".cs", ".cpp"))
                and not any(part.lower() in {"node_modules", "vendor", "dist", "build", ".next", "coverage"}
                            for part in item.get("path", "").split("/"))
            ][:4]
            source_parts = [_raw_github_file(owner, name, branch, path) for path in source_paths]
            evidence_parts.extend(source_parts)
        if repo_data.get("language"):
            evidence_parts.append(repo_data["language"])
        evidence_text = "\n".join(evidence_parts)
        manifest_technologies = technologies_in("\n".join(manifest_parts))
        source_technologies = technologies_in("\n".join(source_parts))
        output.append({"source_type": "github_repository", "url": source_url,
                       "reachable": True, "health": "repository_found",
                       "repository": f"{owner}/{name}", "description": description[:500],
                       "readme_available": bool(readme), "manifest_files": manifest_paths,
                       "technologies": technologies_in(evidence_text),
                       "readme_technologies": readme_technologies,
                       "manifest_technologies": manifest_technologies,
                       "source_technologies": source_technologies,
                       "source_files": source_paths,
                       "_matched_claim_excerpt": repo_data.get("_matched_claim_excerpt"),
                       "_matched_claim_scope": repo_data.get("_matched_claim_scope"),
                       "_matched_project_name": repo_data.get("_matched_project_name"),
                       "_matched_project_group_key": repo_data.get("_matched_project_group_key"),
                       "text": evidence_text[:MAX_README_CHARS]})
    return output


def technologies_in(text: str) -> list[str]:
    return [name for name, pattern in TECHNOLOGY_PATTERNS.items() if re.search(pattern, text, re.I)]


def _snippet_for(text: str, criterion: str) -> str | None:
    searchable = text.casefold()
    tokens = [token for token in re.findall(r"[a-zA-Z0-9+#.]{2,}", criterion.casefold()) if token not in STOP_WORDS]
    for token in tokens:
        match = re.search(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])", searchable)
        if match:
            start, end = max(0, match.start() - 90), min(len(text), match.end() + 130)
            snippet = re.sub(r"\s+", " ", text[start:end]).strip()
            return ("…" if start else "") + snippet + ("…" if end < len(text) else "")
    return None


def inspect_projects(project_urls: list[str], criteria: list[dict], claims: list[dict] | None = None) -> list[dict]:
    """Check explicitly linked repositories and project demos, not GitHub profiles."""
    def claim_key(url: str | None) -> str:
        parsed = urllib.parse.urlsplit(url or "")
        host = (parsed.hostname or "").lower().removeprefix("www.")
        path_parts = [part for part in parsed.path.split("/") if part]
        if host == "github.com" and len(path_parts) >= 2:
            return f"github.com/{path_parts[0].lower()}/{path_parts[1].removesuffix('.git').lower()}"
        return f"{host}{parsed.path.rstrip('/')}"

    claims_by_url = {}
    for item in claims or []:
        claims_by_url.setdefault(claim_key(item.get("url")), []).append(item)
    github_urls, website_urls = [], []
    seen = set()
    for url in project_urls:
        parsed = urllib.parse.urlsplit(url)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        if url in seen:
            continue
        seen.add(url)
        if host == "github.com":
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) < 2 or parts[1].lower() in {"repositories", "projects", "topics", "settings", "followers", "following"}:
                continue
            github_urls.append(url)
        elif host not in NON_PROJECT_HOSTS:
            related_claims = claims_by_url.get(claim_key(url), [])
            known_demo = (any(host == suffix or host.endswith("." + suffix) for suffix in DEMO_HOST_SUFFIXES)
                          or (host == "huggingface.co" and parsed.path.startswith("/spaces/")))
            has_nearby_project_context = any(item.get("scope") == "near_link" for item in related_claims)
            # PDF hyperlink targets have no dependable anchor association. Only
            # check common hosted-app domains unless visible text ties the link to a demo.
            if known_demo or has_nearby_project_context:
                website_urls.append(url)

    sources = []
    repo_limit = 12
    for url in github_urls:
        parsed = urllib.parse.urlsplit(url)
        parts = [part for part in parsed.path.split("/") if part]
        direct_repo = len(parts) >= 2 and parts[1].lower() not in {"repositories", "projects", "topics", "settings", "followers", "following"}
        related_claims = claims_by_url.get(claim_key(url), [])
        if not direct_repo:
            continue
        repos = _github_sources(url, 1, None)
        for source in repos:
            source["link_match_status"] = "direct_repository_link"
            if related_claims:
                source["_matched_claim_excerpt"] = related_claims[0].get("excerpt", "")
                source["_matched_claim_scope"] = related_claims[0].get("scope", "near_link")
                source["_matched_project_name"] = related_claims[0].get("project_name", "")
                source["_matched_project_group_key"] = related_claims[0].get("project_group_key", "")
        sources.extend(repos)
        if not repos:
            sources.append({"source_type": "github_repository", "url": url, "reachable": False,
                            "health": "unavailable", "repository": None, "readme_available": False,
                            "manifest_files": [], "technologies": [], "source_files": [], "evidence": [],
                            "link_match_status": "direct_repository_link"})
        repo_limit -= len(repos)
        if repo_limit <= 0:
            break
    sources.extend(_website_check(url) for url in website_urls)

    evidence = []
    for source in sources:
        text = source.pop("text", "")
        technologies = source.get("technologies") or technologies_in(text)
        source["technologies"] = technologies
        matched_excerpt = source.pop("_matched_claim_excerpt", None)
        matched_scope = source.pop("_matched_claim_scope", None)
        matched_project_name = source.pop("_matched_project_name", "")
        matched_group_key = source.pop("_matched_project_group_key", "")
        claims_for_link = claims_by_url.get(claim_key(source.get("url")), [])
        claim_groups = {item.get("project_group_key") for item in claims_for_link if item.get("project_group_key")}
        claim_is_ambiguous = len(claim_groups) > 1
        claim = ({"excerpt": matched_excerpt, "scope": matched_scope or "near_link",
                  "project_name": matched_project_name, "project_group_key": matched_group_key}
                 if matched_excerpt else (claims_for_link[0] if claims_for_link and not claim_is_ambiguous else None))
        if source.get("source_type") == "github_profile" and source.get("verification_status") == "no_project_match":
            claim = None
        if claim:
            source["project_name"] = claim.get("project_name") or source.get("repository") or source.get("title") or "Project"
            source["project_group_key"] = claim.get("project_group_key") or re.sub(r"[^a-z0-9]+", "-", source["project_name"].casefold()).strip("-")
        elif claim_is_ambiguous:
            source["verification_status"] = "multiple_project_contexts"
            source["project_identity_status"] = "needs_human_review"
            source["project_match_note"] = "This URL appears beside more than one project description, so it was checked but not assigned to a specific project or used in the score."
        if claim:
            claim_text = re.sub(r"https?://\S+", " ", claim.get("excerpt", ""))
            source["candidate_claim_excerpt"] = claim.get("excerpt", "")
            claim_tokens = list(dict.fromkeys(
                token.casefold() for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.]{3,}", claim_text)
                if token.casefold() not in PROFILE_MATCH_STOP_WORDS
            ))[:16]
            claim_matches = []
            searchable = text.casefold()
            for token in claim_tokens:
                match = re.search(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])", searchable)
                if match:
                    start, end = max(0, match.start() - 70), min(len(text), match.end() + 100)
                    claim_matches.append({"term": token, "snippet": re.sub(r"\s+", " ", text[start:end]).strip()})
            source["claim_comparison"] = {
                "claim_terms": claim_tokens,
                "matched_terms": [item["term"] for item in claim_matches],
                "overlap": round(len(claim_matches) / len(claim_tokens), 2) if claim_tokens else None,
                "evidence": claim_matches[:6],
            }
            overlap = source["claim_comparison"]["overlap"]
            claim_name_match = False
            if source.get("source_type") == "github_repository":
                repository_name = (source.get("repository") or "").split("/", 1)[-1]
                claim_name_match = _profile_repo_match(repository_name, claim_text) >= 0.7
            elif source.get("source_type") == "website":
                claim_name_match = (claim.get("scope") != "pdf_page" and
                                    _profile_repo_match(source.get("title", ""), claim_text) >= 0.7)
            public_overlap = (claim.get("scope") != "pdf_page" and overlap is not None
                              and overlap >= 0.25 and len(claim_matches) >= 2)
            confirmed_by_profile = source.get("link_match_status") == "profile_repo_name_matched"
            identity_confirmed = confirmed_by_profile or claim_name_match or public_overlap
            source["project_identity_status"] = "confirmed" if identity_confirmed else "needs_human_review"
            source["verification_status"] = "public_text_overlap_found" if public_overlap else "claim_not_corroborated"
            source["claim_scope"] = claim.get("scope", "near_link")
            source["technology_checks"] = []
            if identity_confirmed and claim.get("scope") != "pdf_page":
                claimed_tech = technologies_in(claim_text)
                for technology in claimed_tech:
                    if technology in (source.get("source_technologies") or []):
                        status = "found_in_source_code"
                    elif technology in (source.get("manifest_technologies") or []):
                        status = "declared_in_dependency_file"
                    elif technology in (source.get("readme_technologies") or []):
                        status = "mentioned_in_readme"
                    else:
                        evidence_technologies = set(source.get("technologies") or [])
                        alternatives = next((family - {technology} for family in TECHNOLOGY_FAMILIES if technology in family), set())
                        status = "possible_mismatch" if evidence_technologies.intersection(alternatives) else "not_verified"
                    source["technology_checks"].append({"technology": technology, "status": status})
        elif source.get("source_type") != "github_profile":
            source.setdefault("project_identity_status", "needs_human_review")
            source.setdefault("verification_status", "claim_not_corroborated")
            source["technology_checks"] = []
        source_findings = []
        if text:
            for criterion in criteria:
                snippet = _snippet_for(text, criterion["name"])
                if snippet:
                    source_findings.append({"criterion": criterion["name"], "snippet": snippet})
        source["evidence"] = source_findings
        evidence.append(source)
    return evidence


def retryable_evidence_error(exc: Exception) -> tuple[bool, str]:
    code = str(exc) if str(exc) in {"github_rate_limited", "github_temporarily_unavailable"} else "project_check_failed"
    return code != "project_check_failed", code
