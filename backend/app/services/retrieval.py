"""Knowledge base retrieval for grounded resolutions (FR-20).

Articles are first narrowed to the complaint's predicted category, then ranked
by how many distinctive words they share with the complaint (title words count
double). This is deliberately simple: it is explainable, needs no embedding
model, and with a curated knowledge base of a few articles per category the
category filter does most of the work.

The knowledge_articles.embedding column is kept for a later upgrade to
semantic search with pgvector; similarity_search in the repository is ready
for it once an embedding model fills that column.
"""

import re

_WORD = re.compile(r"[a-z]{3,}")

# Common words that carry no signal for matching complaints to articles.
_STOPWORDS = frozenset("""
the and for are was were been being have has had not but you your our they them their
this that these those with from into over under about after before again also any all
can could would should will just than then there here when where which who what why how
very more most some such only own same too out off its his her him she he we us i me my
did does doing done get got make made said say says one two three told tell call called
account company customer please thank thanks still even back time day days month months
xxxx xx
""".split())


def keywords(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS}


def rank_articles(complaint_text: str, articles: list, limit: int = 3) -> list:
    """Return up to `limit` articles, best match first.

    `articles` are objects with .title and .body. An article with no word in
    common still ranks (behind the others), because it matched the category.
    """
    words = keywords(complaint_text)

    def score(article) -> int:
        title_hits = len(words & keywords(article.title))
        body_hits = len(words & keywords(article.body))
        return 2 * title_hits + body_hits

    return sorted(articles, key=score, reverse=True)[:limit]
