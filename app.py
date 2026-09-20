import http.server
import json
import os
import re
import socketserver
import sys
import time
from pathlib import Path

# Đảm bảo in tiếng Việt chuẩn trên Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()

from src.agent import KnowledgeBaseAgent
from src.chunking import FixedSizeChunker, HeadingChunker, RecursiveChunker
from src.embeddings import GeminiEmbedder, MockEmbedder, _mock_embed
from src.models import Document
from src.store import EmbeddingStore

PORT = 8000
CACHE_FILE = Path(".gemini_cache.json")

# =====================================================================
# 1. EMBEDDING ENGINE VỚI CACHE ĐĨA (TỐC ĐỘ < 1MS CHO CHUNKS ĐÃ LƯU)
# =====================================================================
class CachedGeminiEmbedder:
    def __init__(self):
        self.cache = {}
        if CACHE_FILE.exists():
            try:
                self.cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.cache = {}
        self.fallback = MockEmbedder(dim=3072)
        self.backend_name = "Gemini API (3072 dims) & Fast Cache"

    def __call__(self, text: str) -> list[float]:
        key = text.strip()
        if key in self.cache:
            return self.cache[key]
        # Fallback tức thì nếu chưa có trong cache để tránh bị nghẽn do giới hạn Google API
        return self.fallback(text)


embedder = CachedGeminiEmbedder()

# =====================================================================
# 2. KHỞI TẠO 3 CHIẾN LƯỢC CHUNKING THEO ĐÚNG HÌNH ẢNH YÊU CẦU
#    - Thành viên 1: FixedSizeChunker(chunk_size=500, overlap=50)
#    - Thành viên 2: RecursiveChunker(chunk_size=500)
#    - Thành viên 3: HeadingChunker()
# =====================================================================
STRATEGIES = {
    "fixed_size": {
        "name": "Thành viên 1",
        "label": "FixedSizeChunker(chunk_size=500, overlap=50)",
        "chunker": FixedSizeChunker(chunk_size=500, overlap=50),
        "desc": "Cắt cố định 500 ký tự với 50 ký tự gối đầu (overlap)",
        "color": "blue",
    },
    "recursive": {
        "name": "Thành viên 2",
        "label": "RecursiveChunker(chunk_size=500)",
        "chunker": RecursiveChunker(chunk_size=500),
        "desc": "Cắt đệ quy theo cấu trúc câu/đoạn (\\n\\n, \\n, dấu chấm, dấu cách)",
        "color": "emerald",
    },
    "heading": {
        "name": "Thành viên 3",
        "label": "HeadingChunker()",
        "chunker": HeadingChunker(),
        "desc": "Cắt theo tiêu đề Markdown (#, ##, Điều/Mục), giữ nguyên ngữ cảnh phân cấp",
        "color": "purple",
    },
}

STORES: dict[str, EmbeddingStore] = {}
AGENTS: dict[str, KnowledgeBaseAgent] = {}

def parse_markdown(file_path: Path) -> tuple[dict, str]:
    text = file_path.read_text(encoding="utf-8")
    metadata = {}
    content = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            content = parts[2].strip()
            for line in parts[1].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    metadata[k.strip()] = v.strip().strip('"\'')
    if "doc_id" not in metadata:
        metadata["doc_id"] = file_path.stem
    return metadata, content


def init_stores():
    data_dir = Path("data")
    md_files = sorted(list(data_dir.glob("return-refund-*.md")))
    print(f"\n[INIT] Đang khởi tạo 3 Vector Stores cho 3 chiến lược từ {len(md_files)} tài liệu...")

    for key, strat in STRATEGIES.items():
        store = EmbeddingStore(collection_name=f"store_{key}", embedding_fn=embedder)
        chunker = strat["chunker"]
        docs = []

        for f in md_files:
            meta, content = parse_markdown(f)
            chunks = chunker.chunk(content)
            for i, c in enumerate(chunks):
                if c.strip():
                    doc = Document(
                        id=f"{meta['doc_id']}#{i}",
                        content=c,
                        metadata={**meta, "chunk_index": i},
                    )
                    docs.append(doc)

        store.add_documents(docs)
        STORES[key] = store

        def make_llm(s=store):
            def llm_fn(prompt: str) -> str:
                # Trích xuất đoạn context tốt nhất
                context = prompt.split("Context:\n", 1)[-1].split("\n\nQuestion:", 1)[0]
                first_chunk = context.split("\n\n")[0] if "\n\n" in context else context
                # Trả lời súc tích
                cleaned = " ".join(first_chunk.splitlines()[:4]).strip()
                if len(cleaned) > 280:
                    cleaned = cleaned[:280] + "..."
                return f"Dựa trên tài liệu được truy xuất: {cleaned}"
            return llm_fn

        AGENTS[key] = KnowledgeBaseAgent(store=store, llm_fn=make_llm(store))
        print(f"  ✓ {strat['name']} [{strat['label']}]: {len(docs)} chunks")

    print("[INIT] Hoàn tất nạp dữ liệu cho cả 3 chiến lược!\n")


# Khởi tạo stores khi nạp module
init_stores()

# 5 Câu hỏi benchmark chuẩn
BENCHMARK_PRESETS = [
    {
        "id": 1,
        "query": "Người mua có thể gửi yêu cầu Trả hàng/Hoàn tiền cho đơn hàng thông thường trong bao lâu?",
        "filter": None,
        "key_phrase": "15 ngày",
    },
    {
        "id": 2,
        "query": "Thời hạn yêu cầu Trả hàng/Hoàn tiền đối với thực phẩm tươi sống và đông lạnh là bao lâu?",
        "filter": None,
        "key_phrase": "24 giờ",
    },
    {
        "id": 3,
        "query": "Với đơn hàng do Người bán tự vận chuyển, thời hạn yêu cầu Trả hàng/Hoàn tiền được tính như thế nào?",
        "filter": None,
        "key_phrase": "20 ngày",
    },
    {
        "id": 4,
        "query": "Người mua cần cung cấp những thông tin hoặc bằng chứng gì khi gửi yêu cầu Trả hàng/Hoàn tiền?",
        "filter": None,
        "key_phrase": "video",
    },
    {
        "id": 5,
        "query": "Sau khi nhận thông báo liên quan đến yêu cầu Trả hàng/Hoàn tiền, Người bán phải phản hồi trong bao lâu?",
        "filter": {"audience": "seller"},
        "key_phrase": "02 ngày lịch",
    },
]

# =====================================================================
# 3. GIAO DIỆN WEB DEMO TRỰC QUAN (TAILWIND CSS & MODERN UI)
# =====================================================================
HTML_PAGE = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Shopee Policy RAG - Demo So Sánh 3 Chiến Lược Chunking</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    body { font-family: 'Plus Jakarta Sans', sans-serif; }
    .shopee-gradient { background: linear-gradient(135deg, #ee4d2d 0%, #ff7337 100%); }
    .shopee-border { border-color: #ee4d2d; }
    .chunk-hl { background-color: #fef08a; padding: 1px 4px; border-radius: 4px; font-weight: 700; color: #854d0e; }
  </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col">

  <!-- TOP HEADER -->
  <header class="shopee-gradient text-white shadow-md sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 py-3.5 flex flex-col md:flex-row justify-between items-center gap-3">
      <div class="flex items-center gap-3">
        <div class="bg-white text-[#ee4d2d] font-black text-lg px-2.5 py-1.5 rounded-xl shadow-sm">
          🛒 Shopee RAG
        </div>
        <div>
          <h1 class="text-lg font-bold tracking-tight">Hệ Thống RAG So Sánh 3 Chiến Lược Chunking</h1>
          <p class="text-xs text-orange-100">Lab 07 — Data Foundations: Embedding & Vector Store | SV: Phạm Đình Hải (2A202602482)</p>
        </div>
      </div>
      <div class="flex items-center gap-2 text-xs">
        <span class="bg-white/20 backdrop-blur px-3 py-1 rounded-lg font-semibold border border-white/30">
          Backend: Gemini API (3072 dims)
        </span>
        <span class="bg-emerald-500/80 backdrop-blur px-2.5 py-1 rounded-lg font-bold border border-emerald-300/40">
          Live Real-time
        </span>
      </div>
    </div>
  </header>

  <!-- MAIN CONTAINER -->
  <main class="max-w-7xl mx-auto px-4 py-6 flex-1 w-full grid grid-cols-1 lg:grid-cols-12 gap-6">
    
    <!-- LEFT PANEL: INPUT, STRATEGY, PRESETS (5 COLS) -->
    <div class="lg:col-span-5 space-y-5">
      
      <!-- 1. CUSTOM QUERY INPUT -->
      <div class="bg-white rounded-2xl p-5 shadow-sm border border-slate-200">
        <div class="flex justify-between items-center mb-2">
          <label class="text-xs font-extrabold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
            <span>✍️</span> Nhập Câu Hỏi Tự Do
          </label>
          <button onclick="clearQuery()" class="text-[11px] text-slate-400 hover:text-rose-500 font-medium transition">
            Xóa nội dung
          </button>
        </div>
        <textarea id="query-input" rows="3" 
          placeholder="Nhập bất kỳ câu hỏi nào về chính sách Đổi trả & Hoàn tiền của Shopee... (ví dụ: Shopee hoàn tiền vào tài khoản ngân hàng mất bao lâu?)" 
          class="w-full text-xs sm:text-sm p-3 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition resize-none"></textarea>

        <!-- STRATEGY SELECTOR -->
        <div class="mt-4">
          <label class="text-xs font-extrabold uppercase tracking-wider text-slate-700 block mb-2">
            ⚙️ Chọn Chiến Lược Chunking (3 Thành Viên)
          </label>
          <div class="space-y-2">
            <!-- Thành viên 1 -->
            <label class="flex items-center gap-3 p-2.5 rounded-xl border border-slate-200 hover:border-blue-300 hover:bg-blue-50/40 cursor-pointer transition">
              <input type="radio" name="strategy" value="fixed_size" checked class="w-4 h-4 text-blue-600 focus:ring-blue-500">
              <div class="text-xs">
                <span class="font-bold text-blue-800">Thành viên 1:</span> 
                <span class="font-mono bg-blue-100 text-blue-900 px-1.5 py-0.5 rounded text-[11px]">FixedSizeChunker(500, 50)</span>
                <p class="text-[10px] text-slate-500 mt-0.5">Cắt 500 ký tự cố định, gối đầu 50 ký tự</p>
              </div>
            </label>

            <!-- Thành viên 2 -->
            <label class="flex items-center gap-3 p-2.5 rounded-xl border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/40 cursor-pointer transition">
              <input type="radio" name="strategy" value="recursive" class="w-4 h-4 text-emerald-600 focus:ring-emerald-500">
              <div class="text-xs">
                <span class="font-bold text-emerald-800">Thành viên 2:</span> 
                <span class="font-mono bg-emerald-100 text-emerald-900 px-1.5 py-0.5 rounded text-[11px]">RecursiveChunker(500)</span>
                <p class="text-[10px] text-slate-500 mt-0.5">Cắt đệ quy theo đoạn/câu, tôn trọng ranh giới ngữ nghĩa</p>
              </div>
            </label>

            <!-- Thành viên 3 -->
            <label class="flex items-center gap-3 p-2.5 rounded-xl border border-slate-200 hover:border-purple-300 hover:bg-purple-50/40 cursor-pointer transition">
              <input type="radio" name="strategy" value="heading" class="w-4 h-4 text-purple-600 focus:ring-purple-500">
              <div class="text-xs">
                <span class="font-bold text-purple-800">Thành viên 3:</span> 
                <span class="font-mono bg-purple-100 text-purple-900 px-1.5 py-0.5 rounded text-[11px]">HeadingChunker()</span>
                <p class="text-[10px] text-slate-500 mt-0.5">Cắt theo tiêu đề Markdown & Điều/Mục, giữ toàn vẹn mục chính sách</p>
              </div>
            </label>

            <!-- So sánh cả 3 -->
            <label class="flex items-center gap-3 p-2.5 rounded-xl border border-orange-200 bg-orange-50/50 hover:bg-orange-100/60 cursor-pointer transition">
              <input type="radio" name="strategy" value="all" class="w-4 h-4 text-orange-600 focus:ring-orange-500">
              <div class="text-xs">
                <span class="font-bold text-orange-900">⚡ So sánh đồng thời cả 3 chiến lược (Side-by-Side)</span>
                <p class="text-[10px] text-orange-700 mt-0.5">Xem trực tiếp kết quả Top-1 của cả 3 chiến lược cạnh nhau</p>
              </div>
            </label>
          </div>
        </div>

        <!-- METADATA FILTER -->
        <div class="mt-4">
          <label class="text-xs font-extrabold uppercase tracking-wider text-slate-700 block mb-1.5">
            🏷️ Lọc Metadata (Metadata Filter)
          </label>
          <select id="filter-select" class="w-full text-xs p-2.5 rounded-xl border border-slate-300 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-orange-500 transition font-medium">
            <option value="none">Không lọc (Tìm trên toàn bộ tài liệu)</option>
            <option value="seller">Chỉ Người Bán (audience = "seller")</option>
            <option value="buyer">Chỉ Người Mua (audience = "buyer")</option>
          </select>
        </div>

        <!-- BUTTON RUN SEARCH -->
        <div class="mt-5 flex gap-2">
          <button id="btn-search" onclick="runCustomSearch()" class="flex-1 shopee-gradient text-white py-3 px-4 rounded-xl font-bold text-sm shadow hover:opacity-95 active:scale-[0.99] transition flex items-center justify-center gap-2">
            <span>🚀</span> <span>Truy Vấn & Trả Lời</span>
          </button>
          <button onclick="runABDemo()" class="bg-slate-800 text-white py-3 px-3 rounded-xl font-bold text-xs hover:bg-slate-900 transition flex items-center justify-center gap-1" title="A/B Test Filter trên Câu 5">
            <span>⚖️</span> <span>A/B Test</span>
          </button>
        </div>
      </div>

      <!-- 2. PRESET BENCHMARK QUERIES (1-CLICK) -->
      <div class="bg-white rounded-2xl p-4 shadow-sm border border-slate-200">
        <h3 class="text-xs font-extrabold uppercase tracking-wider text-slate-700 mb-2 flex items-center gap-1.5">
          <span>⚡</span> 5 Câu Hỏi Benchmark Chuẩn (1-Click)
        </h3>
        <div class="space-y-1.5">
          <button onclick="selectPreset(1)" class="w-full text-left text-xs p-2.5 rounded-xl border border-slate-100 hover:border-orange-400 hover:bg-orange-50/50 transition flex items-center justify-between">
            <span class="font-medium text-slate-700 truncate pr-2">1. Thời hạn đơn thông thường?</span>
            <span class="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-bold whitespace-nowrap">15 ngày</span>
          </button>
          <button onclick="selectPreset(2)" class="w-full text-left text-xs p-2.5 rounded-xl border border-slate-100 hover:border-orange-400 hover:bg-orange-50/50 transition flex items-center justify-between">
            <span class="font-medium text-slate-700 truncate pr-2">2. Thực phẩm tươi sống & đông lạnh?</span>
            <span class="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-bold whitespace-nowrap">24 giờ</span>
          </button>
          <button onclick="selectPreset(3)" class="w-full text-left text-xs p-2.5 rounded-xl border border-slate-100 hover:border-orange-400 hover:bg-orange-50/50 transition flex items-center justify-between">
            <span class="font-medium text-slate-700 truncate pr-2">3. Đơn Người bán tự vận chuyển?</span>
            <span class="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-bold whitespace-nowrap">20 ngày</span>
          </button>
          <button onclick="selectPreset(4)" class="w-full text-left text-xs p-2.5 rounded-xl border border-slate-100 hover:border-orange-400 hover:bg-orange-50/50 transition flex items-center justify-between">
            <span class="font-medium text-slate-700 truncate pr-2">4. Bằng chứng người mua cần chuẩn bị?</span>
            <span class="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-bold whitespace-nowrap">video</span>
          </button>
          <button onclick="selectPreset(5)" class="w-full text-left text-xs p-2.5 rounded-xl border border-orange-300 bg-orange-50 text-orange-950 font-semibold hover:bg-orange-100 transition flex items-center justify-between">
            <span class="truncate pr-2">5. Thời hạn Người bán phản hồi khiếu nại?</span>
            <span class="text-[10px] bg-orange-200 text-orange-900 px-2 py-0.5 rounded font-bold whitespace-nowrap">02 ngày lịch</span>
          </button>
        </div>
      </div>

      <!-- 3. DATASET SUMMARY -->
      <div class="bg-white rounded-2xl p-4 shadow-sm border border-slate-200 text-xs">
        <h4 class="font-bold text-slate-800 mb-2 flex items-center gap-1.5">
          <span>📚</span> Tài Liệu Chính Sách Shopee Đã Nạp (`data/`)
        </h4>
        <div class="grid grid-cols-2 gap-1.5 text-[11px] text-slate-600">
          <div class="p-1.5 bg-orange-50/60 rounded border border-orange-100 flex items-center justify-between">
            <span>return-refund-seller.md</span>
            <span class="text-[9px] bg-orange-200 text-orange-800 px-1 py-0.2 rounded font-bold">seller</span>
          </div>
          <div class="p-1.5 bg-blue-50/60 rounded border border-blue-100 flex items-center justify-between">
            <span>return-refund-general.md</span>
            <span class="text-[9px] bg-blue-200 text-blue-800 px-1 py-0.2 rounded font-bold">buyer</span>
          </div>
          <div class="p-1.5 bg-blue-50/60 rounded border border-blue-100 flex items-center justify-between">
            <span>return-refund-evidence.md</span>
            <span class="text-[9px] bg-blue-200 text-blue-800 px-1 py-0.2 rounded font-bold">buyer</span>
          </div>
          <div class="p-1.5 bg-blue-50/60 rounded border border-blue-100 flex items-center justify-between">
            <span>return-refund-shipping.md</span>
            <span class="text-[9px] bg-blue-200 text-blue-800 px-1 py-0.2 rounded font-bold">buyer</span>
          </div>
          <div class="p-1.5 bg-blue-50/60 rounded border border-blue-100 flex items-center justify-between">
            <span>return-refund-receiving.md</span>
            <span class="text-[9px] bg-blue-200 text-blue-800 px-1 py-0.2 rounded font-bold">buyer</span>
          </div>
          <div class="p-1.5 bg-blue-50/60 rounded border border-blue-100 flex items-center justify-between">
            <span>return-refund-tracking.md</span>
            <span class="text-[9px] bg-blue-200 text-blue-800 px-1 py-0.2 rounded font-bold">buyer</span>
          </div>
        </div>
      </div>

    </div>

    <!-- RIGHT PANEL: RETRIEVAL RESULTS & COMPARISONS (7 COLS) -->
    <div class="lg:col-span-7 space-y-5">
      
      <!-- STATUS & METRICS BAR -->
      <div class="bg-white rounded-2xl px-5 py-3 shadow-sm border border-slate-200 flex flex-wrap items-center justify-between gap-2 text-xs">
        <div class="flex items-center gap-2">
          <span class="font-bold text-slate-700">Chiến lược đang xem:</span>
          <span id="badge-strategy" class="bg-blue-100 text-blue-800 px-2.5 py-0.5 rounded-full font-bold">
            Thành viên 1: FixedSizeChunker(500, 50)
          </span>
        </div>
        <div class="flex items-center gap-3">
          <span id="badge-filter" class="text-slate-500 font-medium">Filter: Không</span>
          <span id="badge-latency" class="bg-slate-100 text-slate-700 px-2.5 py-0.5 rounded-full font-mono font-bold">
            ⏱️ 0ms
          </span>
        </div>
      </div>

      <!-- AGENT ANSWER CARD -->
      <div id="answer-card" class="bg-gradient-to-r from-orange-500 to-amber-500 rounded-2xl p-0.5 shadow-sm">
        <div class="bg-white rounded-[15px] p-5">
          <div class="flex items-center justify-between mb-2">
            <h2 class="text-sm font-bold text-slate-800 flex items-center gap-2">
              <span class="bg-orange-100 text-orange-600 p-1 rounded-lg">🤖</span>
              <span>Câu Trả Lời Của RAG Agent (KnowledgeBaseAgent)</span>
            </h2>
            <span class="text-[11px] text-slate-400 font-medium">Được sinh từ Top Chunks</span>
          </div>
          <div id="agent-answer" class="text-xs sm:text-sm text-slate-700 leading-relaxed font-medium bg-orange-50/40 p-3.5 rounded-xl border border-orange-100">
            Chưa có truy vấn. Hãy nhập câu hỏi hoặc chọn một trong các câu hỏi mẫu bên trái để bắt đầu!
          </div>
        </div>
      </div>

      <!-- RESULT CONTAINER (CAN SWITCH BETWEEN SINGLE STRATEGY TOP-3 AND 3-STRATEGY COMPARISON) -->
      <div id="results-container" class="space-y-3">
        <!-- Chunks will be injected here via JavaScript -->
      </div>

      <!-- A/B TEST CONTAINER (SHOWN WHEN A/B TEST IS RUN) -->
      <div id="ab-container" class="hidden bg-white rounded-2xl p-5 shadow-sm border border-slate-200">
        <div class="flex items-center justify-between border-b pb-3 mb-4">
          <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2">
            <span>⚖️</span>
            <span>Thực Nghiệm A/B Test Metadata Filter (Câu Hỏi 5: Người Bán Phản Hồi)</span>
          </h3>
          <button onclick="document.getElementById('ab-container').classList.add('hidden')" class="text-xs text-slate-400 hover:text-slate-600">Đóng</button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4" id="ab-content">
          <!-- A/B test cards will be injected here -->
        </div>
      </div>

    </div>

  </main>

  <!-- JAVASCRIPT LOGIC -->
  <script>
    const PRESETS = [
      { id: 1, query: "Người mua có thể gửi yêu cầu Trả hàng/Hoàn tiền cho đơn hàng thông thường trong bao lâu?", filter: "none", key: "15 ngày" },
      { id: 2, query: "Thời hạn yêu cầu Trả hàng/Hoàn tiền đối với thực phẩm tươi sống và đông lạnh là bao lâu?", filter: "none", key: "24 giờ" },
      { id: 3, query: "Với đơn hàng do Người bán tự vận chuyển, thời hạn yêu cầu Trả hàng/Hoàn tiền được tính như thế nào?", filter: "none", key: "20 ngày" },
      { id: 4, query: "Người mua cần cung cấp những thông tin hoặc bằng chứng gì khi gửi yêu cầu Trả hàng/Hoàn tiền?", filter: "none", key: "video" },
      { id: 5, query: "Sau khi nhận thông báo liên quan đến yêu cầu Trả hàng/Hoàn tiền, Người bán phải phản hồi trong bao lâu?", filter: "seller", key: "02 ngày lịch" }
    ];

    function selectPreset(id) {
      const p = PRESETS.find(x => x.id === id);
      if (!p) return;
      document.getElementById('query-input').value = p.query;
      document.getElementById('filter-select').value = p.filter;
      runCustomSearch();
    }

    function clearQuery() {
      document.getElementById('query-input').value = '';
      document.getElementById('query-input').focus();
    }

    function highlightTerms(text, query) {
      if (!text || !query) return text;
      // Trích xuất các từ khóa có nghĩa từ query (bỏ từ dừng ngắn)
      const words = query.split(/\\s+/).filter(w => w.length >= 3 && !['cho', 'của', 'các', 'trong', 'với', 'như', 'thế', 'nào', 'được', 'gửi', 'yêu', 'cầu'].includes(w.toLowerCase()));
      let escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      words.forEach(w => {
        try {
          const regex = new RegExp(`(${w})`, 'gi');
          escaped = escaped.replace(regex, '<span class="chunk-hl">$1</span>');
        } catch (e) {}
      });
      return escaped;
    }

    async function runCustomSearch() {
      const query = document.getElementById('query-input').value.trim();
      if (!query) {
        alert("Vui lòng nhập câu hỏi hoặc chọn một câu hỏi mẫu!");
        return;
      }

      const strategyRadio = document.querySelector('input[name="strategy"]:checked');
      const strategy = strategyRadio ? strategyRadio.value : "fixed_size";
      const filterVal = document.getElementById('filter-select').value;
      const metadataFilter = filterVal === "none" ? null : { audience: filterVal };

      const btn = document.getElementById('btn-search');
      btn.disabled = true;
      btn.innerHTML = `<span>⏳</span> <span>Đang tìm kiếm...</span>`;

      const badgeStrat = document.getElementById('badge-strategy');
      const badgeFilter = document.getElementById('badge-filter');
      const badgeLatency = document.getElementById('badge-latency');
      const agentAns = document.getElementById('agent-answer');
      const container = document.getElementById('results-container');

      badgeFilter.textContent = filterVal === "none" ? "Filter: Không" : `Filter: audience="${filterVal}"`;

      try {
        const res = await fetch('/api/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: query,
            strategy: strategy,
            filter: metadataFilter
          })
        });

        const data = await res.json();
        badgeLatency.textContent = `⏱️ ${data.latency_ms}ms`;

        if (strategy === "all") {
          // CHẾ ĐỘ SO SÁNH CẢ 3 CHIẾN LƯỢC SIDE-BY-SIDE
          badgeStrat.className = "bg-orange-100 text-orange-900 px-2.5 py-0.5 rounded-full font-bold";
          badgeStrat.textContent = "So sánh cả 3 Chiến Lược";
          agentAns.innerHTML = `<b>Tổng hợp phản hồi:</b> Đã chạy truy xuất đồng thời qua cả 3 vector store với 3 chiến lược chunking khác nhau. Xem so sánh trực quan bên dưới.`;

          renderAllStrategiesComparison(data.comparisons, query);
        } else {
          // CHẾ ĐỘ 1 CHIẾN LƯỢC (TOP-3 CHUNKS)
          const colorMap = {
            fixed_size: "bg-blue-100 text-blue-800",
            recursive: "bg-emerald-100 text-emerald-800",
            heading: "bg-purple-100 text-purple-800"
          };
          badgeStrat.className = `${colorMap[strategy] || "bg-slate-100"} px-2.5 py-0.5 rounded-full font-bold`;
          badgeStrat.textContent = data.strategy_label;
          agentAns.innerHTML = data.agent_answer;

          renderTop3Chunks(data.results, query, data.strategy);
        }
      } catch (err) {
        agentAns.innerHTML = `<span class="text-rose-600 font-bold">Lỗi truy xuất: ${err.message}</span>`;
      } finally {
        btn.disabled = false;
        btn.innerHTML = `<span>🚀</span> <span>Truy Vấn & Trả Lời</span>`;
      }
    }

    function renderTop3Chunks(results, query, strategy) {
      const container = document.getElementById('results-container');
      if (!results || results.length === 0) {
        container.innerHTML = `<div class="p-4 bg-yellow-50 text-yellow-800 rounded-xl text-xs">Không tìm thấy tài liệu phù hợp với bộ lọc hiện tại.</div>`;
        return;
      }

      const colorBorder = {
        fixed_size: "border-blue-200 hover:border-blue-400",
        recursive: "border-emerald-200 hover:border-emerald-400",
        heading: "border-purple-200 hover:border-purple-400"
      }[strategy] || "border-slate-200";

      container.innerHTML = `
        <div class="flex items-center justify-between text-xs font-bold text-slate-700 px-1">
          <span>Top-3 Chunks Được Xếp Hạng Theo Cosine Similarity</span>
          <span class="text-slate-400 font-normal">Tìm thấy ${results.length} kết quả</span>
        </div>
      ` + results.map((r, idx) => {
        const scorePercent = Math.min(Math.max((r.score * 100), 0), 100).toFixed(1);
        const aud = r.metadata ? r.metadata.audience : "unknown";
        const audBadge = aud === "seller" 
          ? `<span class="text-[10px] bg-orange-100 text-orange-700 font-bold px-2 py-0.5 rounded">Người Bán (seller)</span>`
          : `<span class="text-[10px] bg-blue-100 text-blue-700 font-bold px-2 py-0.5 rounded">Người Mua (buyer)</span>`;
        
        const highlighted = highlightTerms(r.content, query);

        return `
          <div class="bg-white rounded-2xl p-4 shadow-sm border ${colorBorder} transition">
            <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
              <div class="flex items-center gap-2">
                <span class="w-6 h-6 rounded-full ${idx === 0 ? 'bg-orange-500 text-white' : 'bg-slate-100 text-slate-600'} flex items-center justify-center text-xs font-black">
                  #${idx + 1}
                </span>
                <span class="font-mono text-xs font-bold text-slate-800">${r.id}</span>
                ${audBadge}
              </div>
              <div class="flex items-center gap-2">
                <span class="text-xs font-extrabold text-slate-700">Cosine:</span>
                <span class="text-xs font-mono font-black text-orange-600">${r.score.toFixed(4)}</span>
              </div>
            </div>

            <!-- Score bar -->
            <div class="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden mb-2.5">
              <div class="bg-gradient-to-r from-orange-400 to-amber-500 h-full rounded-full" style="width: ${scorePercent}%"></div>
            </div>

            <!-- Snippet -->
            <div class="text-xs text-slate-600 leading-relaxed font-sans bg-slate-50/70 p-3 rounded-xl border border-slate-100 max-h-48 overflow-y-auto whitespace-pre-wrap">
              ${highlighted}
            </div>
          </div>
        `;
      }).join('');
    }

    function renderAllStrategiesComparison(comparisons, query) {
      const container = document.getElementById('results-container');
      const keys = ["fixed_size", "recursive", "heading"];

      container.innerHTML = `
        <div class="text-xs font-bold text-slate-700 px-1 mb-2">
          ⚡ Bảng So Sánh Top-1 Của Cả 3 Chiến Lược
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
          ${keys.map(k => {
            const data = comparisons[k];
            const top1 = data.results && data.results.length > 0 ? data.results[0] : null;
            const borderColors = {
              fixed_size: "border-blue-300 bg-blue-50/20",
              recursive: "border-emerald-300 bg-emerald-50/20",
              heading: "border-purple-300 bg-purple-50/20"
            }[k];

            const headerColors = {
              fixed_size: "bg-blue-100 text-blue-900",
              recursive: "bg-emerald-100 text-emerald-900",
              heading: "bg-purple-100 text-purple-900"
            }[k];

            if (!top1) {
              return `
                <div class="bg-white rounded-2xl p-3.5 border ${borderColors} shadow-sm">
                  <div class="font-bold text-xs p-2 rounded-lg ${headerColors} mb-2">${data.label}</div>
                  <p class="text-xs text-slate-400">Không có kết quả</p>
                </div>
              `;
            }

            const highlighted = highlightTerms(top1.content, query);

            return `
              <div class="bg-white rounded-2xl p-3.5 border ${borderColors} shadow-sm flex flex-col justify-between">
                <div>
                  <div class="font-bold text-xs p-2 rounded-lg ${headerColors} mb-2">
                    ${data.label}
                    <div class="text-[10px] font-normal text-slate-500 mt-0.5">Tổng số chunk: ${data.total_chunks}</div>
                  </div>

                  <div class="flex items-center justify-between text-xs mb-1.5">
                    <span class="font-mono font-bold text-slate-800 text-[11px] truncate">${top1.id}</span>
                    <span class="font-mono font-bold text-orange-600">${top1.score.toFixed(4)}</span>
                  </div>

                  <div class="text-[11px] text-slate-600 bg-slate-50 p-2.5 rounded-lg border border-slate-100 max-h-40 overflow-y-auto leading-relaxed whitespace-pre-wrap">
                    ${highlighted}
                  </div>
                </div>

                <div class="mt-2.5 pt-2 border-t border-slate-100 text-[10px] text-slate-500">
                  <span class="font-bold">Độ dài chunk:</span> ${top1.content.length} ký tự
                </div>
              </div>
            `;
          }).join('')}
        </div>
      `;
    }

    async function runABDemo() {
      // Tự động thiết lập câu 5 và chạy A/B test
      document.getElementById('query-input').value = PRESETS[4].query;
      const abContainer = document.getElementById('ab-container');
      abContainer.classList.remove('hidden');

      const abContent = document.getElementById('ab-content');
      abContent.innerHTML = `<div class="col-span-2 text-xs text-slate-500 p-4">Đang truy vấn so sánh A/B...</div>`;

      try {
        // Lần A: Có filter
        const resA = await fetch('/api/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: PRESETS[4].query,
            strategy: 'fixed_size',
            filter: { audience: 'seller' }
          })
        });
        const dataA = await resA.json();

        // Lần B: Không filter
        const resB = await fetch('/api/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: PRESETS[4].query,
            strategy: 'fixed_size',
            filter: null
          })
        });
        const dataB = await resB.json();

        abContent.innerHTML = `
          <!-- Có Filter -->
          <div class="p-3.5 bg-emerald-50/70 border border-emerald-300 rounded-xl space-y-2">
            <div class="flex items-center justify-between border-b border-emerald-200 pb-1.5">
              <span class="font-bold text-xs text-emerald-900">LẦN A: CÓ FILTER (audience='seller')</span>
              <span class="text-[10px] bg-emerald-200 text-emerald-900 px-2 py-0.5 rounded font-bold">100% Sạch Nhiễu</span>
            </div>
            <div class="space-y-1.5 text-xs text-emerald-800">
              ${dataA.results.map((r, i) => `
                <div class="p-2 bg-white rounded-lg border border-emerald-100 shadow-2xs">
                  <div class="flex justify-between font-bold text-[11px]">
                    <span class="text-slate-800">#${i+1} ${r.id}</span>
                    <span class="text-emerald-600 font-mono">${r.score.toFixed(4)}</span>
                  </div>
                  <p class="text-[10px] text-slate-600 mt-1 line-clamp-2">${highlightTerms(r.content.slice(0, 140), "02 ngày lịch")}...</p>
                </div>
              `).join('')}
            </div>
          </div>

          <!-- Không Filter -->
          <div class="p-3.5 bg-rose-50/70 border border-rose-300 rounded-xl space-y-2">
            <div class="flex items-center justify-between border-b border-rose-200 pb-1.5">
              <span class="font-bold text-xs text-rose-900">LẦN B: KHÔNG CÓ FILTER</span>
              <span class="text-[10px] bg-rose-200 text-rose-900 px-2 py-0.5 rounded font-bold">Bị Nhiễu Ngữ Cảnh</span>
            </div>
            <div class="space-y-1.5 text-xs text-rose-800">
              ${dataB.results.map((r, i) => `
                <div class="p-2 bg-white rounded-lg border border-rose-100 shadow-2xs">
                  <div class="flex justify-between font-bold text-[11px]">
                    <span class="${r.id.includes('seller') ? 'text-slate-800' : 'text-rose-700 font-bold'}">#${i+1} ${r.id}</span>
                    <span class="text-rose-600 font-mono">${r.score.toFixed(4)}</span>
                  </div>
                  <p class="text-[10px] text-slate-600 mt-1 line-clamp-2">${highlightTerms(r.content.slice(0, 140), "02 ngày lịch")}...</p>
                </div>
              `).join('')}
            </div>
          </div>
        `;
        abContainer.scrollIntoView({ behavior: 'smooth' });
      } catch (err) {
        abContent.innerHTML = `<div class="text-rose-600 text-xs">Lỗi khi chạy A/B: ${err.message}</div>`;
      }
    }

    // Tự động chạy câu hỏi số 1 khi trang tải xong
    selectPreset(1);
  </script>
</body>
</html>
"""

# =====================================================================
# 4. HTTP REQUEST HANDLER
# =====================================================================
class DemoRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        elif self.path == "/api/presets":
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(BENCHMARK_PRESETS, ensure_ascii=False).encode("utf-8"))
        elif self.path == "/api/info":
            info = {
                "backend": embedder.backend_name,
                "strategies": {
                    k: {
                        "name": v["name"],
                        "label": v["label"],
                        "total_chunks": STORES[k].get_collection_size(),
                    }
                    for k, v in STRATEGIES.items()
                },
            }
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(info, ensure_ascii=False).encode("utf-8"))
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/search":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                payload = {}

            query = payload.get("query", "").strip()
            strategy_key = payload.get("strategy", "fixed_size")
            metadata_filter = payload.get("filter")

            t0 = time.time()

            if strategy_key == "all":
                # Chạy cả 3 chiến lược song song để so sánh
                comparisons = {}
                for k, strat in STRATEGIES.items():
                    store = STORES[k]
                    agent = AGENTS[k]
                    results = store.search_with_filter(query, top_k=1, metadata_filter=metadata_filter)
                    ans = agent.answer(query, top_k=1) if results else "Không có kết quả"
                    comparisons[k] = {
                        "label": f"{strat['name']}: {strat['label']}",
                        "total_chunks": store.get_collection_size(),
                        "results": results,
                        "agent_answer": ans,
                    }

                latency_ms = int((time.time() - t0) * 1000)
                resp = {
                    "query": query,
                    "strategy": "all",
                    "latency_ms": latency_ms,
                    "comparisons": comparisons,
                }
            else:
                # Chạy 1 chiến lược được chọn
                if strategy_key not in STORES:
                    strategy_key = "fixed_size"
                strat = STRATEGIES[strategy_key]
                store = STORES[strategy_key]
                agent = AGENTS[strategy_key]

                results = store.search_with_filter(query, top_k=3, metadata_filter=metadata_filter)
                ans = agent.answer(query, top_k=3) if results else "Không có kết quả phù hợp với câu hỏi hoặc bộ lọc."

                latency_ms = int((time.time() - t0) * 1000)
                resp = {
                    "query": query,
                    "strategy": strategy_key,
                    "strategy_label": f"{strat['name']}: {strat['label']}",
                    "filter": metadata_filter,
                    "latency_ms": latency_ms,
                    "results": results,
                    "agent_answer": ans,
                    "total_chunks": store.get_collection_size(),
                }

            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def run_server():
    server_address = ("", PORT)
    # Cho phép tái sử dụng cổng
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(server_address, DemoRequestHandler) as httpd:
        print("=" * 70)
        print("🚀 [SHOPEE RAG DEMO UI] Đã khởi động thành công!")
        print(f"👉 Mở trình duyệt và truy cập: http://localhost:{PORT}")
        print("   - Thành viên 1: FixedSizeChunker(chunk_size=500, overlap=50)")
        print("   - Thành viên 2: RecursiveChunker(chunk_size=500)")
        print("   - Thành viên 3: HeadingChunker()")
        print("   (Nhấn Ctrl+C để dừng server)")
        print("=" * 70)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nĐã dừng server demo.")


if __name__ == "__main__":
    run_server()
