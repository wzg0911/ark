# ARK repro: langchain#39106 — list_keys(before=...) excludes records whose
# updated_at == before, causing silently incomplete cleanup on low-resolution clocks.
#
# Deterministic: freezes the record manager clock to simulate a low-resolution
# time source (as seen on Windows, where consecutive time.time() calls can
# return the identical float). No network, no model downloads.
import asyncio

from langchain_core.documents import Document
from langchain_core.indexing import index
from langchain_core.indexing.base import InMemoryRecordManager
from langchain_core.indexing.in_memory import InMemoryDocumentIndex


class FrozenClockRecordManager(InMemoryRecordManager):
    """Simulates a low-resolution clock: get_time() returns a fixed value
    until manually advanced. On Windows, time.time() resolution can be
    ~15.6ms, so index()'s index_start_dt and the subsequent update() stamps
    routinely collide to the same float."""

    def __init__(self, namespace: str) -> None:
        super().__init__(namespace)
        self.frozen_at = 1_000_000.0

    def get_time(self) -> float:
        return self.frozen_at

    async def aget_time(self) -> float:
        return self.frozen_at

    def advance(self, seconds: float = 1.0) -> None:
        self.frozen_at += seconds


def run_sync() -> dict:
    rm = FrozenClockRecordManager(namespace="repro-39106")
    rm.create_schema()
    doc_index = InMemoryDocumentIndex()

    docs = [
        Document(page_content="doc 1", metadata={"source": "1"}),
        Document(page_content="doc 2", metadata={"source": "2"}),
    ]

    # First indexing run at t=T0: both docs written, updated_at == T0.
    index(docs, rm, doc_index, cleanup="full", key_encoder="sha256")

    # Second run happens "immediately" (clock has not ticked): index_start_dt
    # == T0 as well. Re-indexing an empty list under cleanup="full" should
    # delete both stale docs — but list_keys(before=T0) uses `>=` and skips
    # records whose updated_at == T0.
    result = index([], rm, doc_index, cleanup="full", key_encoder="sha256")
    return result


async def run_async() -> dict:
    from langchain_core.indexing import aindex

    rm = FrozenClockRecordManager(namespace="repro-39106-async")
    rm.create_schema()
    doc_index = InMemoryDocumentIndex()

    docs = [
        Document(page_content="doc 1", metadata={"source": "1"}),
        Document(page_content="doc 2", metadata={"source": "2"}),
    ]
    await aindex(docs, rm, doc_index, cleanup="full", key_encoder="sha256")
    return await aindex([], rm, doc_index, cleanup="full", key_encoder="sha256")


def main() -> None:
    print("=== langchain#39106 repro: cleanup misses records at the `before` boundary ===")

    sync_result = run_sync()
    print(f"[sync ] cleanup='full' re-index with []  -> {sync_result}")
    sync_bug = sync_result["num_deleted"] == 0

    async_result = asyncio.run(run_async())
    print(f"[async] cleanup='full' re-index with []  -> {async_result}")
    async_bug = async_result["num_deleted"] == 0

    print()
    print("expected: num_deleted == 2 (both stale docs removed)")
    if sync_bug or async_bug:
        print(
            "BUG REPRODUCED: num_deleted == 0 — stale records whose updated_at "
            "equals index_start_dt are silently excluded by "
            "list_keys(before=...) strict `>=` comparison."
        )
    else:
        print("bug NOT reproduced on this build (fix may have landed).")


if __name__ == "__main__":
    main()
