"""Tests for Binary Quantization RAG and cloud-optimized chain grouping (v18.0)."""

import pytest
import math


# ---------------------------------------------------------------------------
# Binary Quantization helpers
# ---------------------------------------------------------------------------

class TestBinaryQuantize:
    """Tests for binary_quantize() function."""

    def test_basic_quantization(self):
        from src.rag_engine import binary_quantize
        emb = [0.5, -0.3, 0.1, -0.8, 0.0, 0.9, -0.1, 0.2]
        result = binary_quantize(emb)
        assert isinstance(result, bytes)
        assert len(result) == 1  # 8 dims → 1 byte

    def test_positive_values_become_ones(self):
        from src.rag_engine import binary_quantize
        emb = [1.0] * 8
        result = binary_quantize(emb)
        assert result == bytes([0xFF])  # all 1s

    def test_negative_values_become_zeros(self):
        from src.rag_engine import binary_quantize
        emb = [-1.0] * 8
        result = binary_quantize(emb)
        assert result == bytes([0x00])  # all 0s

    def test_zero_becomes_zero(self):
        from src.rag_engine import binary_quantize
        emb = [0.0] * 8
        result = binary_quantize(emb)
        assert result == bytes([0x00])

    def test_mixed_values(self):
        from src.rag_engine import binary_quantize
        # [+, -, +, -, +, -, +, -] → 10101010 = 0xAA
        emb = [1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0]
        result = binary_quantize(emb)
        assert result == bytes([0xAA])

    def test_larger_dimension(self):
        from src.rag_engine import binary_quantize
        emb = [0.5] * 1024  # bge-large-en-v1.5 dimensions
        result = binary_quantize(emb)
        assert len(result) == 128  # 1024 / 8 = 128 bytes

    def test_32x_compression(self):
        from src.rag_engine import binary_quantize
        dims = 1024
        emb = [0.1 * (i % 7 - 3) for i in range(dims)]
        result = binary_quantize(emb)
        float32_bytes = dims * 4  # 4096 bytes
        binary_bytes = len(result)  # 128 bytes
        ratio = float32_bytes / binary_bytes
        assert ratio == 32.0

    def test_non_multiple_of_8_padded(self):
        from src.rag_engine import binary_quantize
        emb = [1.0, -1.0, 1.0]  # 3 dims → pads to 8
        result = binary_quantize(emb)
        assert len(result) == 1  # Still 1 byte


class TestBinaryQuantizeBatch:
    """Tests for binary_quantize_batch() function."""

    def test_batch_of_two(self):
        from src.rag_engine import binary_quantize_batch
        embeddings = [
            [1.0] * 8,
            [-1.0] * 8,
        ]
        results = binary_quantize_batch(embeddings)
        assert len(results) == 2
        assert results[0] == bytes([0xFF])
        assert results[1] == bytes([0x00])

    def test_empty_batch(self):
        from src.rag_engine import binary_quantize_batch
        results = binary_quantize_batch([])
        assert results == []

    def test_consistency_with_single(self):
        from src.rag_engine import binary_quantize, binary_quantize_batch
        emb = [0.1 * (i % 5 - 2) for i in range(16)]
        single_result = binary_quantize(emb)
        batch_result = binary_quantize_batch([emb])[0]
        assert single_result == batch_result


# ---------------------------------------------------------------------------
# Hamming distance
# ---------------------------------------------------------------------------

class TestHammingDistance:
    """Tests for hamming_distance() function."""

    def test_identical_vectors(self):
        from src.rag_engine import hamming_distance
        a = bytes([0xFF, 0x00])
        assert hamming_distance(a, a) == 0

    def test_completely_different(self):
        from src.rag_engine import hamming_distance
        a = bytes([0xFF])
        b = bytes([0x00])
        assert hamming_distance(a, b) == 8

    def test_one_bit_difference(self):
        from src.rag_engine import hamming_distance
        a = bytes([0b11111111])
        b = bytes([0b11111110])
        assert hamming_distance(a, b) == 1

    def test_half_bits_different(self):
        from src.rag_engine import hamming_distance
        a = bytes([0b10101010])
        b = bytes([0b01010101])
        assert hamming_distance(a, b) == 8  # All bits flipped

    def test_different_lengths_truncates(self):
        from src.rag_engine import hamming_distance
        a = bytes([0xFF, 0xFF])
        b = bytes([0xFF])
        # Should compare only the overlapping portion
        assert hamming_distance(a, b) == 0


# ---------------------------------------------------------------------------
# BinaryQuantizedRAG
# ---------------------------------------------------------------------------

class TestBinaryQuantizedRAG:
    """Tests for BinaryQuantizedRAG class."""

    def test_empty_search(self):
        from src.rag_engine import BinaryQuantizedRAG
        bq = BinaryQuantizedRAG()
        assert not bq.is_ready
        assert bq.search([0.1] * 8) == []

    def test_index_and_search(self):
        from src.rag_engine import BinaryQuantizedRAG
        bq = BinaryQuantizedRAG()
        docs = ["Python is great", "Java is verbose", "Rust is fast"]
        # Create synthetic embeddings (8 dims)
        embeddings = [
            [0.9, 0.8, 0.1, -0.3, 0.5, -0.1, 0.2, -0.4],  # Python
            [-0.5, 0.3, 0.8, 0.2, -0.1, 0.6, -0.3, 0.1],   # Java
            [0.7, 0.6, 0.2, -0.5, 0.4, -0.2, 0.3, -0.6],   # Rust (similar to Python)
        ]
        stats = bq.index_documents(docs, embeddings)
        assert stats["indexed"] == 3
        assert bq.is_ready
        assert bq.size == 3

        # Query similar to Python/Rust
        query = [0.8, 0.7, 0.15, -0.4, 0.45, -0.15, 0.25, -0.5]
        results = bq.search(query, top_k=2)
        assert len(results) == 2
        # Python and Rust should be more similar than Java
        result_docs = [r["content"] for r in results]
        assert "Java is verbose" not in result_docs

    def test_search_returns_scores(self):
        from src.rag_engine import BinaryQuantizedRAG
        bq = BinaryQuantizedRAG()
        docs = ["doc1"]
        embeddings = [[1.0] * 8]
        bq.index_documents(docs, embeddings)

        results = bq.search([1.0] * 8, top_k=1)
        assert len(results) == 1
        assert results[0]["score"] == 1.0  # Identical → distance 0 → score 1.0
        assert results[0]["hamming_distance"] == 0

    def test_mismatched_lengths_raises(self):
        from src.rag_engine import BinaryQuantizedRAG
        bq = BinaryQuantizedRAG()
        with pytest.raises(ValueError, match="must have the same length"):
            bq.index_documents(["doc1", "doc2"], [[1.0] * 8])

    def test_clear(self):
        from src.rag_engine import BinaryQuantizedRAG
        bq = BinaryQuantizedRAG()
        bq.index_documents(["doc"], [[0.1] * 8])
        assert bq.is_ready
        bq.clear()
        assert not bq.is_ready
        assert bq.size == 0

    def test_stats(self):
        from src.rag_engine import BinaryQuantizedRAG
        bq = BinaryQuantizedRAG()
        stats = bq.get_stats()
        assert stats["status"] == "empty"

        bq.index_documents(
            ["doc1", "doc2"],
            [[0.1] * 1024, [-0.1] * 1024],
        )
        stats = bq.get_stats()
        assert stats["status"] == "ready"
        assert stats["documents"] == 2
        assert stats["compression_ratio"] == "32x"
        assert stats["bq_memory_bytes"] == 256  # 2 * 128 bytes
        assert stats["float32_equivalent_bytes"] == 256 * 32

    def test_metadata_preserved(self):
        from src.rag_engine import BinaryQuantizedRAG
        bq = BinaryQuantizedRAG()
        bq.index_documents(
            ["content"],
            [[0.5] * 8],
            metadatas=[{"source_file": "test.md", "chunk_index": 0}],
        )
        results = bq.search([0.5] * 8, top_k=1)
        assert results[0]["source"] == "test.md"


# ---------------------------------------------------------------------------
# Cloud-optimized chain grouping
# ---------------------------------------------------------------------------

class TestGroupChainCloud:
    """Tests for group_chain_cloud() function."""

    def test_basic_dmarket_chain(self):
        from src.pipeline_utils import group_chain_cloud
        chain = ["Planner", "Coder", "Auditor"]
        groups = group_chain_cloud(chain)
        assert groups == [("Planner",), ("Coder",), ("Auditor",)]

    def test_openclaw_core_chain_parallelizes_executors(self):
        from src.pipeline_utils import group_chain_cloud
        chain = ["Planner", "Foreman", "Executor_Tools", "Executor_Architect", "Auditor"]
        groups = group_chain_cloud(chain)
        assert groups == [
            ("Planner",),
            ("Foreman",),
            ("Executor_Tools", "Executor_Architect"),
            ("Auditor",),
        ]

    def test_full_openclaw_chain(self):
        from src.pipeline_utils import group_chain_cloud
        chain = [
            "Planner", "Foreman",
            "Executor_Tools", "Executor_Architect",
            "Auditor", "State_Manager", "Archivist",
        ]
        groups = group_chain_cloud(chain)
        # Planner → Foreman are sequential
        # Executors parallelized
        # Auditor sequential
        # State_Manager + Archivist parallelized
        assert groups == [
            ("Planner",),
            ("Foreman",),
            ("Executor_Tools", "Executor_Architect"),
            ("Auditor",),
            ("State_Manager", "Archivist"),
        ]

    def test_research_ops_chain(self):
        from src.pipeline_utils import group_chain_cloud
        chain = ["Researcher", "Analyst", "Summarizer"]
        groups = group_chain_cloud(chain)
        # Researcher and Analyst are parallelizable; Summarizer is unknown → sequential
        assert groups == [("Researcher", "Analyst"), ("Summarizer",)]

    def test_single_role_chain(self):
        from src.pipeline_utils import group_chain_cloud
        chain = ["Planner"]
        groups = group_chain_cloud(chain)
        assert groups == [("Planner",)]

    def test_empty_chain(self):
        from src.pipeline_utils import group_chain_cloud
        groups = group_chain_cloud([])
        assert groups == []

    def test_original_group_chain_unchanged(self):
        """Verify the original group_chain still works for local mode."""
        from src.pipeline_utils import group_chain
        chain = ["Planner", "Executor_Tools", "Executor_Architect", "Auditor"]
        groups = group_chain(chain)
        assert groups == [
            ("Planner",),
            ("Executor_Tools", "Executor_Architect"),
            ("Auditor",),
        ]

    def test_cloud_groups_more_parallel_than_local(self):
        """Cloud mode should produce >= as many parallel batches as local."""
        from src.pipeline_utils import group_chain, group_chain_cloud
        chain = [
            "Planner", "Foreman",
            "Executor_Tools", "Executor_Architect",
            "Auditor", "State_Manager", "Archivist",
        ]
        local_groups = group_chain(chain)
        cloud_groups = group_chain_cloud(chain)

        # Count total parallel slots
        local_parallel = sum(1 for g in local_groups if len(g) > 1)
        cloud_parallel = sum(1 for g in cloud_groups if len(g) > 1)
        assert cloud_parallel >= local_parallel


# ---------------------------------------------------------------------------
# Integration: Summarizer should NOT be in _PARALLELIZABLE_ROLES
# (it needs prior Researcher/Analyst output)
# ---------------------------------------------------------------------------

class TestSummarizerSequential:
    """Summarizer depends on prior analysis output and must stay sequential
    unless explicitly batched with context injection."""

    def test_summarizer_not_parallelizable_alone(self):
        from src.pipeline_utils import _PARALLELIZABLE_ROLES
        # Summarizer is NOT in _PARALLELIZABLE_ROLES because it depends
        # on prior Researcher/Analyst output and must run sequentially.
        assert "Summarizer" not in _PARALLELIZABLE_ROLES

    def test_auditor_is_sequential(self):
        from src.pipeline_utils import _SEQUENTIAL_ROLES
        assert "Auditor" in _SEQUENTIAL_ROLES

    def test_planner_is_sequential(self):
        from src.pipeline_utils import _SEQUENTIAL_ROLES
        assert "Planner" in _SEQUENTIAL_ROLES
