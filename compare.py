import sys
from pathlib import Path

# Đảm bảo in tiếng Việt trên console Windows không bị lỗi font
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.chunking import ChunkingStrategyComparator

# 1. Chọn file tài liệu để kiểm tra
file_path = Path("data/return-refund-general.md")
text = file_path.read_text(encoding="utf-8")

# 2. Loại bỏ header YAML frontmatter nếu có
if text.startswith("---"):
    text = text.split("---", 2)[-1].strip()

# 3. Chạy so sánh với chunk_size = 500
comparator = ChunkingStrategyComparator()
results = comparator.compare(text, chunk_size=500)

# 4. In kết quả thống kê
print(f"Tài liệu: {file_path.name}")
print(f"Độ dài văn bản gốc: {len(text)} ký tự\n")

for strategy, stats in results.items():
    count = stats["count"]
    avg_len = stats["avg_length"]
    print(f"Chiến lược: {strategy:<15} | Số chunk: {count:2d} | Độ dài TB: {avg_len:.1f} ký tự")

print("\n--- Xem thử 2 chunk đầu tiên của từng chiến lược ---")
for strategy, stats in results.items():
    print(f"\n[{strategy.upper()}]")
    for i, c in enumerate(stats["chunks"][:2]):
        preview = c.replace("\n", " ")[:100]
        print(f"  Chunk {i} ({len(c)} ký tự): {preview}...")
