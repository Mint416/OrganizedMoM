from collections import defaultdict

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import Record


def current_records(records):
    groups = defaultdict(list)
    for r in records:
        groups[r.event_id].append(r)
    current, errors = [], []
    for event_id, versions in groups.items():
        revision = max(r.revision for r in versions)
        latest = [r for r in versions if r.revision == revision and r.status != "superseded"]
        if not latest:
            errors.append(f"{event_id}: current revision unavailable")
            continue
        # Equally authoritative disagreements require human review, never arbitrary last-write-wins.
        signatures = {(r.start, r.end, r.child, r.location, r.status) for r in latest}
        if len(signatures) > 1:
            errors.append(f"{event_id}: authoritative sources disagree")
            continue
        r = latest[0]
        if r.status == "cancelled":
            continue
        if r.status != "current":
            errors.append(f"{r.id}: {r.status}")
        elif not r.child or r.confidence < 0.8:
            errors.append(f"{r.id}: child unclear or confidence below 0.80")
        else:
            current.append(r)
    return current, errors


class Retriever:
    """Module 3 TF-IDF + LSA retrieval, with source diversification and exact metadata filters."""

    def search(self, records: list[Record], query, child=None, date=None, k=3):
        eligible = [
            r
            for r in records
            if (not child or r.child == child) and (not date or r.start.date().isoformat() == date)
        ]
        if not eligible:
            return []
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        matrix = vectorizer.fit_transform([f"{r.title} {r.text} {r.source} {r.child}" for r in eligible])
        q = vectorizer.transform([query])
        if min(matrix.shape) > 2:
            svd = TruncatedSVD(n_components=min(32, min(matrix.shape) - 1), random_state=42)
            embedded = svd.fit_transform(matrix)
            similarities = cosine_similarity(svd.transform(q), embedded)[0]
        else:
            similarities = cosine_similarity(q, matrix)[0]
        order = list(np.argsort(-similarities))
        selected = []
        if any(w in query.lower() for w in ("conflict", "overlap", "chinese", "soccer")):
            for source in ("BYGA", "LingoAce"):
                options = [
                    i for i in order if eligible[i].source == source and eligible[i].status == "current"
                ]
                if options:
                    selected.append(options[0])
        for i in order:
            if i not in selected and len(selected) < k:
                selected.append(i)
        return [
            {"record": eligible[i].model_dump(mode="json"), "similarity": round(float(similarities[i]), 4)}
            for i in selected[:k]
        ]
