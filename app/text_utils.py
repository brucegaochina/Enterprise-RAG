import re

STOPWORDS = frozenset("""
a about above after again against all am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have
having he her here hers herself him himself his how i if in into is it its itself just me more most
my myself no nor not now of off on once only or other our ours ourselves out over own same she
should so some such than that the their theirs them themselves then there these they this those
through to too under until up very was we were what when where which while who whom why will with
would you your yours yourself yourselves get got tell please much many also may might must shall
""".split())


def stem(word: str) -> str:
    """Tiny suffix stripper, good enough for the offline embedder and query terms."""
    for suffix in ("ing", "ies", "es", "ed", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


def keywords(text: str, limit: int = 32) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return list(dict.fromkeys(w for w in words if w not in STOPWORDS and len(w) > 1))[:limit]
