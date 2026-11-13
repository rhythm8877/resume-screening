"""Small, explainable keyword comparison. This is not an AI hiring prediction."""

import re
from pathlib import Path

from docx import Document
from pypdf import PdfReader

MAX_TEXT_CHARACTERS = 500_000

# Canonical requirement -> common ways it may appear in a resume or job description.
SKILL_ALIASES = {
    "Python": ["python"], "Java": ["java"], "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript", "ts"], "C++": ["c++"], "C#": ["c#", "c sharp"],
    "SQL": ["sql", "postgresql", "mysql", "sqlite"], "Excel": ["excel", "spreadsheets"],
    "Power BI": ["power bi", "powerbi"], "Tableau": ["tableau"], "Looker": ["looker"],
    "Data analysis": ["data analysis", "data analytics", "analyze data", "analysing data"],
    "Statistics": ["statistics", "statistical"], "Machine learning": ["machine learning", "ml"],
    "Deep learning": ["deep learning"], "Natural language processing": ["natural language processing", "nlp"],
    "Data visualization": ["data visualization", "data visualisation"],
    "Communication": ["communication", "communicate"], "Leadership": ["leadership", "led a team"],
    "Project management": ["project management", "managed projects"], "Agile": ["agile", "scrum"],
    "Customer service": ["customer service", "customer support"], "Sales": ["sales", "salesforce"],
    "Marketing": ["marketing", "digital marketing"], "Writing": ["writing", "written content", "copywriting"],
    "Research": ["research", "market research"], "Problem solving": ["problem solving", "problem-solving"],
    "Critical thinking": ["critical thinking"], "Teamwork": ["teamwork", "cross-functional team"],
    "Public speaking": ["public speaking", "presentations"], "Figma": ["figma"],
    "HTML": ["html"], "CSS": ["css"], "React": ["react", "react.js"],
    "Node.js": ["node.js", "nodejs"], "FastAPI": ["fastapi"], "Django": ["django"],
    "Flask": ["flask"], "Git": ["git", "github"], "Linux": ["linux"],
    "AWS": ["aws", "amazon web services"], "Azure": ["azure"], "Google Cloud": ["google cloud", "gcp"],
    "Docker": ["docker"], "Kubernetes": ["kubernetes", "k8s"], "REST APIs": ["rest api", "restful api"],
    "GraphQL": ["graphql"], "CI/CD": ["ci/cd", "continuous integration", "continuous delivery"],
    "Cybersecurity": ["cybersecurity", "information security"], "Networking": ["networking", "tcp/ip"],
    "Accounting": ["accounting", "bookkeeping"], "Financial analysis": ["financial analysis", "financial modelling", "financial modeling"],
}


def normalize(text: str) -> str:
    text = text.lower().replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text)


def contains_term(text: str, term: str) -> bool:
    """Match whole terms so e.g. Java does not match JavaScript."""
    haystack, needle = normalize(text), normalize(term)
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", haystack))


def extract_resume_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path), strict=False)
        if reader.is_encrypted:
            raise ValueError("This PDF is password protected. Upload an unlocked copy.")
        raw = "\n".join((page.extract_text() or "") for page in reader.pages[:150])
    elif suffix == ".docx":
        document = Document(str(path))
        parts = [paragraph.text for paragraph in document.paragraphs]
        parts.extend(cell.text for table in document.tables for row in table.rows for cell in row.cells)
        raw = "\n".join(parts)
    else:
        raise ValueError("Please upload a PDF or DOCX resume.")
    text = re.sub(r"[ \t\r\f\v]+", " ", raw)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    if not text:
        raise ValueError("No readable text was found. Scanned PDFs are not supported yet.")
    return text[:MAX_TEXT_CHARACTERS]


def find_requirements(job_description: str, manual_requirements: str = "") -> list[str]:
    if manual_requirements.strip():
        terms = [part.strip() for part in re.split(r"[,;\n]", manual_requirements) if part.strip()]
        # Keep order while removing duplicate user-entered criteria.
        return list(dict.fromkeys(terms))[:30]
    return [name for name, aliases in SKILL_ALIASES.items()
            if any(contains_term(job_description, alias) for alias in aliases)]


def evidence_snippet(resume_text: str, term: str) -> str:
    aliases = SKILL_ALIASES.get(term, [term])
    lower = normalize(resume_text)
    for alias in aliases:
        match = re.search(r"(?<![a-z0-9])" + re.escape(normalize(alias)) + r"(?![a-z0-9])", lower)
        if match:
            start, end = max(0, match.start() - 80), min(len(resume_text), match.end() + 120)
            excerpt = re.sub(r"\s+", " ", resume_text[start:end]).strip()
            return ("…" if start else "") + excerpt + ("…" if end < len(resume_text) else "")
    return ""


def compare_resume(job_description: str, resume_text: str, manual_requirements: str = "") -> dict:
    requirements = find_requirements(job_description, manual_requirements)
    matched = [term for term in requirements if any(
        contains_term(resume_text, alias) for alias in SKILL_ALIASES.get(term, [term])
    )]
    missing = [term for term in requirements if term not in matched]
    score = round(100 * len(matched) / len(requirements)) if requirements else None
    return {
        "requirements": requirements,
        "matched": [{"term": term, "evidence": evidence_snippet(resume_text, term)} for term in matched],
        "missing": missing,
        "score": score,
    }
