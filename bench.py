import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.agent import KnowledgeBaseAgent
from src.chunking import (
    ChunkingStrategyComparator,
    FixedSizeChunker,
    compute_similarity,
)
from src.embeddings import _mock_embed
from src.models import Document
from src.store import EmbeddingStore


def parse_markdown_with_frontmatter(file_path: Path) -> tuple[dict, str]:
    text = file_path.read_text(encoding="utf-8")
    metadata = {}
    content = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            raw_yaml = parts[1]
            content = parts[2].strip()
            for line in raw_yaml.splitlines():
                line = line.strip()
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    metadata[key] = val

    if "doc_id" not in metadata:
        metadata["doc_id"] = file_path.stem

    return metadata, content


def run_baseline_comparison():
    print("=" * 60)
    print("1. RUNNING BASELINE COMPARISON (ChunkingStrategyComparator)")
    print("=" * 60)
    comparator = ChunkingStrategyComparator()
    sample_files = [
        Path("data/return-refund-general.md"),
        Path("data/return-refund-evidence.md"),
        Path("data/return-refund-shipping.md"),
    ]

    for file_path in sample_files:
        if not file_path.exists():
            continue
        _, content = parse_markdown_with_frontmatter(file_path)
        stats = comparator.compare(content, chunk_size=500)
        print(f"\n--- Tài liệu: {file_path.name} (Độ dài: {len(content)} ký tự) ---")
        for strat, data in stats.items():
            print(f"  [{strat:12s}] Count: {data['count']:3d} | Avg Length: {data['avg_length']:.1f} ký tự")


def run_similarity_predictions():
    print("\n" + "=" * 60)
    print("2. RUNNING SIMILARITY PREDICTIONS (compute_similarity on 5 pairs)")
    print("=" * 60)
    pairs = [
        (
            "Người mua có thể yêu cầu trả hàng và hoàn tiền trong vòng 15 ngày.",
            "Thời hạn gửi yêu cầu hoàn tiền đối với đơn hàng là 15 ngày kể từ khi giao thành công.",
            "cao",
        ),
        (
            "Đối với thực phẩm tươi sống và đông lạnh, thời hạn yêu cầu trả hàng là 24 giờ.",
            "Sản phẩm đồ tươi sống cần gửi khiếu nại hoàn tiền trong vòng một ngày.",
            "cao",
        ),
        (
            "Người bán cần phản hồi yêu cầu khiếu nại trong vòng 02 ngày lịch.",
            "Ví ShopeePay sẽ nhận được tiền hoàn trong vòng 24 giờ sau khi chấp nhận.",
            "thấp",
        ),
        (
            "Các phương thức gửi hàng hoàn trả gồm lấy hàng tận nơi và gửi tại bưu cục.",
            "Người mua bắt buộc phải quay video mở kiện hàng làm bằng chứng khiếu nại.",
            "thấp",
        ),
        (
            "Shopee miễn phí vận chuyển cho đơn hàng hoàn trả qua các kênh tích hợp.",
            "Phí gửi trả hàng được Shopee hỗ trợ miễn phí khi dùng đơn vị vận chuyển của sàn.",
            "cao",
        ),
    ]

    for idx, (sent_a, sent_b, expected) in enumerate(pairs, 1):
        vec_a = _mock_embed(sent_a)
        vec_b = _mock_embed(sent_b)
        sim = compute_similarity(vec_a, vec_b)
        print(f"Cặp {idx}:")
        print(f"  Câu A: {sent_a}")
        print(f"  Câu B: {sent_b}")
        print(f"  Dự đoán: {expected} | Điểm thực tế: {sim:.4f}")


def run_benchmark():
    print("\n" + "=" * 60)
    print("3. RUNNING BENCHMARK WITH FixedSizeChunker(chunk_size=500, overlap=50)")
    print("=" * 60)

    chunker = FixedSizeChunker(chunk_size=500, overlap=50)
    store = EmbeddingStore(collection_name="benchmark_store", embedding_fn=_mock_embed)

    data_dir = Path("data")
    md_files = sorted(list(data_dir.glob("return-refund-*.md")))
    all_chunks: list[Document] = []

    for f in md_files:
        metadata, content = parse_markdown_with_frontmatter(f)
        chunks = chunker.chunk(content)
        for i, c in enumerate(chunks):
            doc = Document(
                id=f"{metadata['doc_id']}#{i}",
                content=c,
                metadata={**metadata, "doc_id": metadata["doc_id"], "chunk_index": i},
            )
            all_chunks.append(doc)

    store.add_documents(all_chunks)
    print(f"Đã nạp tổng cộng {len(all_chunks)} chunks từ {len(md_files)} tài liệu vào EmbeddingStore.\n")

    queries = [
        {
            "id": 1,
            "query": "Người mua có thể gửi yêu cầu Trả hàng/Hoàn tiền cho đơn hàng thông thường trong bao lâu?",
            "filter": None,
            "gold": "Người mua có thể gửi yêu cầu Trả hàng/Hoàn tiền trong vòng 15 ngày kể từ khi đơn hàng được cập nhật trạng thái “Giao hàng thành công”",
            "expected_doc": "return-refund-general",
        },
        {
            "id": 2,
            "query": "Thời hạn yêu cầu Trả hàng/Hoàn tiền đối với thực phẩm tươi sống và đông lạnh là bao lâu?",
            "filter": None,
            "gold": "Người mua phải gửi yêu cầu trong vòng 24 giờ kể từ khi đơn hàng được cập nhật trạng thái “Giao hàng thành công”, trừ trường hợp khiếu nại với lý do chưa nhận được hàng.",
            "expected_doc": "return-refund-general",
        },
        {
            "id": 3,
            "query": "Với đơn hàng do Người bán tự vận chuyển, thời hạn yêu cầu Trả hàng/Hoàn tiền được tính như thế nào?",
            "filter": None,
            "gold": "Người mua có thể gửi yêu cầu trong 15 ngày kể từ khi bấm “Đã nhận được hàng”, hoặc 20 ngày kể từ lúc đơn hàng được cập nhật “Lấy hàng thành công” nếu chưa bấm “Đã nhận được hàng”.",
            "expected_doc": "return-refund-general",
        },
        {
            "id": 4,
            "query": "Người mua cần cung cấp những thông tin hoặc bằng chứng gì khi gửi yêu cầu Trả hàng/Hoàn tiền?",
            "filter": None,
            "gold": "Người mua cần chọn lý do khiếu nại, mô tả tình trạng sản phẩm và cung cấp hình ảnh hoặc video làm bằng chứng cho yêu cầu Trả hàng/Hoàn tiền.",
            "expected_doc": "return-refund-evidence",
        },
        {
            "id": 5,
            "query": "Sau khi nhận thông báo liên quan đến yêu cầu Trả hàng/Hoàn tiền, Người bán phải phản hồi trong bao lâu?",
            "filter": {"audience": "seller"},
            "gold": "Người bán cần gửi phản hồi trong vòng 02 ngày lịch kể từ ngày nhận được thông báo của Shopee trong các trường hợp được quy định.",
            "expected_doc": "return-refund-policy",
        },
    ]

    def mock_llm_answer(prompt: str) -> str:
        lines = prompt.split("Context:\n", 1)[-1].split("\n\nQuestion:", 1)[0]
        preview = lines[:250].replace("\n", " ")
        return f"[RAG Answer] Dựa trên tài liệu được truy xuất: {preview}..."

    agent = KnowledgeBaseAgent(store=store, llm_fn=mock_llm_answer)

    print("KẾT QUẢ ĐÁNH GIÁ 5 CÂU HỎI BENCHMARK:")
    print("-" * 60)

    for q in queries:
        qid = q["id"]
        query_text = q["query"]
        filt = q["filter"]
        gold = q["gold"]

        results = store.search_with_filter(query_text, top_k=3, metadata_filter=filt)
        top1 = results[0] if results else None
        top3_ids = [r["id"] for r in results]
        agent_ans = agent.answer(query_text, top_k=3)

        has_relevant = any(q["expected_doc"] in rid for rid in top3_ids)

        print(f"Câu hỏi {qid}: {query_text}")
        if filt:
            print(f"  [Filter]: {filt}")
        print(f"  [Gold Answer]: {gold}")
        if top1:
            print(f"  [Top-1 Chunk]: ID={top1['id']} | Score={top1['score']:.4f}")
            print(f"  [Top-1 Preview]: {top1['content'][:150].replace(chr(10), ' ')}...")
        print(f"  [Top-3 IDs]: {top3_ids}")
        print(f"  [Có chunk liên quan trong top-3?]: {'CÓ' if has_relevant else 'KHÔNG'}")
        print(f"  [Agent Answer]: {agent_ans[:180]}...")
        print("-" * 60)


if __name__ == "__main__":
    run_baseline_comparison()
    run_similarity_predictions()
    run_benchmark()
