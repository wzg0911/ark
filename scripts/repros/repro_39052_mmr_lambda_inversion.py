# ARK repro: langchain#39052 — QdrantVectorStore MMR lambda_mult semantics inversion
# No external server needed: qdrant-client local mode (:memory:)
# Deterministic hand-crafted embeddings, no model downloads.
import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

DIM = 4

# Hand-crafted vector space:
#   query  = [1,0,0,0]
#   docA/B/C = near-duplicates of query direction (high relevance, high mutual redundancy)
#   docD = orthogonal-ish (low relevance, max diversity)
#   docE = another orthogonal direction
VECS = {
    "A: relevant clone 1": [1.00, 0.05, 0.00, 0.00],
    "B: relevant clone 2": [0.99, 0.10, 0.00, 0.00],
    "C: relevant clone 3": [0.98, 0.15, 0.00, 0.00],
    "D: diverse topic 1":  [0.10, 1.00, 0.00, 0.00],
    "E: diverse topic 2":  [0.10, 0.00, 1.00, 0.00],
}
QUERY_VEC = [1.0, 0.0, 0.0, 0.0]

class HandEmb(Embeddings):
    def embed_documents(self, texts):
        return [VECS.get(t, [0.0] * DIM) for t in texts]
    def embed_query(self, text):
        return QUERY_VEC

def cos(a, b):
    a, b = np.array(a, float), np.array(b, float)
    return a.dot(b) / (np.linalg.norm(a) * np.linalg.norm(b))

def manual_mmr(query_vec, names, k, lambda_mult):
    """LangChain documented semantics: score = lam*rel - (1-lam)*redundancy.
    lambda_mult=1 -> pure relevance; lambda_mult=0 -> pure diversity."""
    vecs = [VECS[n] for n in names]
    rel = [cos(query_vec, v) for v in vecs]
    sel = [int(np.argmax(rel))]
    while len(sel) < k:
        best, bi = -1e9, -1
        for i in range(len(vecs)):
            if i in sel:
                continue
            red = max(cos(vecs[i], vecs[j]) for j in sel)
            s = lambda_mult * rel[i] - (1 - lambda_mult) * red
            if s > best:
                best, bi = s, i
        sel.append(bi)
    return [names[i] for i in sel]

names = list(VECS)
docs = [Document(page_content=n) for n in names]

client = QdrantClient(":memory:")
client.create_collection("c", vectors_config=VectorParams(size=DIM, distance=Distance.COSINE))
vs = QdrantVectorStore(client=client, collection_name="c", embedding=HandEmb())
vs.add_documents(docs)

print("=" * 70)
ok_inversion_shown = True
for lam in (0.0, 1.0):
    got = [d.page_content for d in vs.max_marginal_relevance_search("q", k=3, fetch_k=5, lambda_mult=lam)]
    exp = manual_mmr(QUERY_VEC, names, 3, lam)
    # what the OPPOSITE lambda would give under documented semantics:
    opp = manual_mmr(QUERY_VEC, names, 3, 1 - lam)
    print(f"\nlambda_mult={lam}")
    print(f"  documented-semantics expectation : {exp}")
    print(f"  qdrant path actually returned    : {got}")
    print(f"  inverted-lambda ({1-lam}) prediction: {opp}")
    match_doc = got == exp
    match_inv = got == opp
    print(f"  matches documented semantics? {match_doc} | matches INVERTED semantics? {match_inv}")
    if not (match_inv and not match_doc):
        ok_inversion_shown = False

print("\n" + "=" * 70)
print("VERDICT:", "INVERSION CONFIRMED — Qdrant MMR path flips lambda_mult meaning"
      if ok_inversion_shown else "inversion NOT cleanly demonstrated on this dataset")
