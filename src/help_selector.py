import os

from jira.resources import Comment, Issue

ONLINEHELP_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "onlinehelp")
)


def get_documentation_paths(online_help_dir: str = ONLINEHELP_DIR) -> list[str]:
    """
    Recursively get a list of all relative paths to each .htm document in the online help directory.
    Args:
        online_help_dir (str): Path to the online help directory.
    Returns:
        list[str]: List of documentation paths.
    """
    if not os.path.exists(online_help_dir):
        return []

    documentation_paths: list[str] = []
    for root, _, files in os.walk(online_help_dir):
        for filename in files:
            if filename.endswith(".htm"):
                rel_path = os.path.relpath(
                    os.path.join(root, filename), online_help_dir
                )
                documentation_paths.append(rel_path)
    return documentation_paths


def select_help_documents(
    issue: Issue,
    onlinehelp: Comment,
    online_help_dir: str = ONLINEHELP_DIR,
    *,
    max_documents: int = 10,
) -> list[str]:
    """
    Stub for selecting relevant help documents.
    Args:
        online_help_dir (str): Path to the online help directory.
    Returns:
        list[str]: List of selected help document paths.
    """
    import re

    # Helper: simple keyword extraction (lowercase, remove punctuation, split)
    def extract_keywords(text: str) -> set[str]:
        text = text.lower()
        # Remove punctuation
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        # Split into words, remove short/stop words
        stopwords = set(
            [
                "the",
                "and",
                "for",
                "with",
                "that",
                "this",
                "from",
                "are",
                "was",
                "but",
                "not",
                "have",
                "has",
                "had",
                "you",
                "your",
                "can",
                "will",
                "all",
                "any",
                "our",
                "out",
                "use",
                "how",
                "why",
                "who",
                "what",
                "when",
                "where",
                "which",
                "a",
                "an",
                "of",
                "in",
                "on",
                "to",
                "by",
                "at",
                "as",
                "is",
                "it",
                "be",
                "or",
                "if",
                "do",
                "so",
                "we",
                "i",
                "me",
                "my",
                "their",
                "them",
                "they",
                "he",
                "she",
                "his",
                "her",
                "us",
                "about",
                "also",
                "more",
                "no",
                "yes",
                "was",
                "were",
                "than",
                "then",
                "just",
                "should",
                "would",
                "could",
                "may",
                "might",
                "must",
                "does",
                "did",
                "done",
                "get",
                "got",
                "getting",
                "gotten",
                "see",
                "seen",
                "let",
                "lets",
                "make",
                "made",
                "makes",
                "making",
                "help",
                "online",
                "comment",
                "issue",
                "summary",
                "description",
                "body",
                "doc",
                "docs",
                "document",
                "documents",
                "file",
                "files",
                "htm",
                "html",
                "etc",
            ]
        )
        words = [w for w in text.split() if len(w) > 2 and w not in stopwords]
        return set(words)

    # Extract text from issue and comment
    summary = getattr(issue.fields, "summary", "")
    description = getattr(issue.fields, "description", "") or ""
    comment_body = str(getattr(onlinehelp, "body", ""))
    all_text = f"{summary}\n{description}\n{comment_body}"
    keywords = extract_keywords(all_text)

    # Get all documentation paths
    doc_paths = get_documentation_paths(online_help_dir)

    # Score each doc by keyword matches in filename or path
    scored_docs: list[tuple[int, str]] = []
    for path in doc_paths:
        path_lc = path.lower()
        # Tokenize path (split on /, _, -, ., and space)
        tokens = set(re.split(r"[\\/_.\-\s]", path_lc))
        match_count = len(tokens & keywords)
        if match_count > 0:
            scored_docs.append((match_count, path))

    # Sort by number of matches (descending), then alphabetically
    scored_docs.sort(key=lambda x: (-x[0], x[1]))

    # Return top N (e.g., 10) most relevant docs
    return [path for _, path in scored_docs[:max_documents]]


if __name__ == "__main__":
    from rich import print

    print(
        "Onlinehelp dir",
        ONLINEHELP_DIR,
        "exists" if os.path.exists(ONLINEHELP_DIR) else "does not exist",
    )
    print(f"Found {len(get_documentation_paths())} documentation files.")
