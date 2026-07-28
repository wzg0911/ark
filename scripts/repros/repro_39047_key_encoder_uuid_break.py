# ARK repro: langchain#39047 — index() key_encoder sha256/sha512/blake2b produce non-UUID IDs, breaking Qdrant
# Deterministic, no external server (qdrant-client :memory:), no model downloads.
import uuid
import warnings

from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.indexing import InMemoryRecordManager, index
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams


def make_store():
    embeddings = DeterministicFakeEmbedding(size=32)
    client = QdrantClient(":memory:")
    client.create_collection(
        "test", vectors_config=VectorParams(size=32, distance=Distance.COSINE)
    )
    return QdrantVectorStore(client=client, collection_name="test", embedding=embeddings)


def try_encoder(key_encoder):
    store = make_store()
    rm = InMemoryRecordManager(namespace=f"ns_{key_encoder}")
    rm.create_schema()
    docs = [Document(page_content="hello world", metadata={"source": "doc1.txt"})]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = index(
                docs, rm, store,
                cleanup="incremental", source_id_key="source",
                key_encoder=key_encoder,
            )
        keys = rm.list_keys()
        is_uuid = all(_valid_uuid(k) for k in keys)
        return ("OK", res, keys, is_uuid)
    except Exception as e:
        return ("FAIL", type(e).__name__, str(e)[:120], None)


def _valid_uuid(s):
    try:
        uuid.UUID(str(s))
        return True
    except Exception:
        return False


def main():
    print("=" * 78)
    print("ARK repro #39047: key_encoder x Qdrant UUID validation")
    print("=" * 78)
    results = {}
    for enc in ("sha1", "sha256", "sha512", "blake2b"):
        r = try_encoder(enc)
        results[enc] = r
        if r[0] == "OK":
            print(f"[{enc:8s}] OK    indexed={r[1]}  ids_are_uuid={r[3]}  sample_id={r[2][0] if r[2] else '-'}")
        else:
            print(f"[{enc:8s}] FAIL  {r[1]}: {r[2]}")

    # Additionally show the warning that *recommends* the failing encoders
    print("-" * 78)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        store = make_store()
        rm = InMemoryRecordManager(namespace="ns_warn")
        rm.create_schema()
        index(
            [Document(page_content="x", metadata={"source": "s"})],
            rm, store, cleanup="incremental", source_id_key="source",
        )  # default key_encoder
        for wi in w:
            if "sha" in str(wi.message).lower() or "blake" in str(wi.message).lower():
                print("Default-encoder UserWarning emitted by langchain-core:")
                print("  ", str(wi.message)[:300])

    print("=" * 78)
    ok_sha1 = results["sha1"][0] == "OK"
    fail_others = all(results[e][0] == "FAIL" for e in ("sha256", "sha512", "blake2b"))
    if ok_sha1 and fail_others:
        print("VERDICT: REPRODUCED — sha1 (deprecated) works; every recommended encoder")
        print("         (sha256/sha512/blake2b) raises 'Point id ... is not a valid UUID'.")
        print("         The library's own deprecation advice leads users into a hard crash.")
    else:
        print("VERDICT: NOT (fully) reproduced — check version drift.")
    print("=" * 78)


if __name__ == "__main__":
    main()
