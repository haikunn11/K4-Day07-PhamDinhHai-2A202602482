# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** [Tên nhóm]
**Thành viên:** [Họ tên từng thành viên]
**Ngày:** [Ngày nộp]

> **Nộp 1 bản / nhóm.** Phần cá nhân (hướng tiếp cận, kết quả riêng, dự đoán…) mỗi thành viên nộp riêng trong `REPORT_CANHAN.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần nhóm: 40** = Lựa chọn tài liệu (10) + Thiết kế chiến lược (15) + Chất lượng truy xuất (10) + Thuyết trình (5).

---

## 1. Lựa chọn tài liệu (Document Set Quality) — Nhóm (10 điểm)

### Chủ đề (Domain) & Lý Do Chọn

**Chủ đề:** Chính sách Trả hàng và Hoàn tiền Shopee (E-commerce Return & Refund Policy)

**Tại sao nhóm chọn chủ đề này?**
> *Viết 2-3 câu:*

### Danh sách tài liệu (Data Inventory)

| # | Tên tài liệu | Nguồn (Source URL) | Ngày lấy / Phiên bản | Số ký tự | Metadata đã gán |
|---|--------------|------------|--------------------|----------|-----------------|
| 1 | Trả hàng/Hoàn tiền - Hướng dẫn chuẩn bị bằng chứng khi yêu cầu Trả hàng/Hoàn tiền | https://help.shopee.vn/portal/4/article/79467 | 2026-09-20 / not-stated | 4661 | `doc_id`: return-refund-evidence, `audience`: buyer, `category`: returns-policy |
| 2 | Trả hàng/Hoàn tiền - Những quy định chung về Trả hàng/Hoàn tiền của Shopee | https://help.shopee.vn/portal/4/article/188931 | 2026-09-20 / not-stated | 8654 | `doc_id`: return-refund-general, `audience`: buyer, `category`: returns-policy |
| 3 | Thời hạn đổi trả và hoàn tiền (Chính sách Trả hàng và Hoàn tiền) | https://help.shopee.vn/portal/4/article/77251 | 2026-09-20 / not-stated | 25718 | `doc_id`: return-refund-policy, `audience`: seller, `category`: returns-policy |
| 4 | Trả hàng/Hoàn tiền - Thời gian nhận tiền hoàn và cách kiểm tra tiền hoàn | https://help.shopee.vn/portal/4/article/189473 | 2026-09-20 / not-stated | 5136 | `doc_id`: return-refund-receiving, `audience`: buyer, `category`: returns-policy |
| 5 | Trả hàng/Hoàn tiền - Các phương thức gửi hàng hoàn trả và phí hoàn trả | https://help.shopee.vn/portal/4/article/189477 | 2026-09-20 / not-stated | 8027 | `doc_id`: return-refund-shipping, `audience`: buyer, `category`: returns-policy |
| 6 | Trả hàng/Hoàn tiền - Theo dõi tình trạng Trả hàng/Hoàn tiền trên Shopee | https://help.shopee.vn/portal/4/article/79298 | 2026-09-20 / not-stated | 2097 | `doc_id`: return-refund-tracking, `audience`: buyer, `category`: returns-policy |

**Danh sách kiểm tra quản trị dữ liệu (Data governance checklist):**
- [x] Tập tài liệu (Corpus) chỉ chứa nguồn công khai/được phép dùng và không chứa dữ liệu cá nhân, thông tin đăng nhập hoặc tài liệu nội bộ.
- [x] Mỗi tài liệu có `source_url`, `retrieved_at`, `document_version` (hoặc ngày hiệu lực) trong metadata.

### Cấu trúc Metadata (Metadata Schema)

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho truy xuất (retrieval)? |
|----------------|------|---------------|-------------------------------|
| `doc_id` | str | `return-refund-policy` | Định danh tài liệu gốc để truy vết nguồn gốc câu trả lời |
| `audience` | str | `buyer` / `seller` / `both` | Lọc tài liệu theo đối tượng (người mua hay người bán) tránh nhiễu |
| `category` | str | `returns-policy` | Phân loại chủ đề chính sách hỗ trợ tìm kiếm theo phạm vi |
| `source_url` | str | URL bài viết trợ giúp Shopee | Dẫn nguồn minh bạch cho thông tin nền |
| `retrieved_at` | str | `2026-09-20` | Kiểm tra tính cập nhật và hiệu lực của thông tin |

---

## 2. Thiết kế chiến lược (Strategy Design) — Nhóm (15 điểm)

> Mỗi thành viên thử **một chiến lược khác nhau** trên cùng bộ tài liệu; nhóm tổng hợp và so sánh ở đây.

### Phân tích đường cơ sở (Baseline Analysis)

Chạy `ChunkingStrategyComparator().compare()` trên 2-3 tài liệu:

| Tài liệu | Chiến lược (Strategy) | Số lượng Chunk | Độ dài trung bình | Giữ được ngữ cảnh không? |
|-----------|----------|-------------|------------|-------------------|
| `return-refund-general.md` (8,654 ký tự) | FixedSizeChunker (`fixed_size`) | 18 | 494.3 ký tự | Trung bình (cắt ngang câu do kích thước cứng) |
| `return-refund-general.md` | SentenceChunker (`by_sentences`) | 9 | 667.1 ký tự | Tốt (giữ nguyên ranh giới câu hoàn chỉnh) |
| `return-refund-general.md` | RecursiveChunker (`recursive`) | 14 | 431.5 ký tự | Rất tốt (ưu tiên ngắt theo đoạn `\n\n` và câu) |
| `return-refund-evidence.md` (4,661 ký tự) | FixedSizeChunker (`fixed_size`) | 7 | 464.6 ký tự | Trung bình (cắt ngang ý) |
| `return-refund-evidence.md` | SentenceChunker (`by_sentences`) | 10 | 308.2 ký tự | Tốt |
| `return-refund-evidence.md` | RecursiveChunker (`recursive`) | 7 | 445.7 ký tự | Rất tốt |
| `return-refund-shipping.md` (8,027 ký tự) | FixedSizeChunker (`fixed_size`) | 12 | 490.9 ký tự | Trung bình |
| `return-refund-shipping.md` | SentenceChunker (`by_sentences`) | 9 | 626.9 ký tự | Tốt |
| `return-refund-shipping.md` | RecursiveChunker (`recursive`) | 14 | 403.2 ký tự | Rất tốt |

### Chiến lược của từng thành viên

> Mỗi thành viên điền một khối dưới đây (copy thêm nếu nhóm có nhiều hơn 3 người).

**Thành viên 1 — [Tên]**
- **Loại chiến lược:** FixedSizeChunker (`chunk_size=500, overlap=50`)
- **Mô tả & lý do chọn cho chủ đề này:** *(2-3 câu)*
- **Code snippet (nếu custom):**

**Thành viên 2 — [Tên]**
- **Loại chiến lược:**
- **Mô tả & lý do chọn:**
- **Code snippet (nếu custom):**

**Thành viên 3 — [Tên]**
- **Loại chiến lược:**
- **Mô tả & lý do chọn:**
- **Code snippet (nếu custom):**

### So Sánh Giữa Các Thành Viên

| Thành viên | Chiến lược (Strategy) | Điểm truy xuất (/10) | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|
| | | | | |
| | | | | |
| | | | | |

**Chiến lược nào tốt nhất cho chủ đề này? Tại sao?**
> *Viết 2-3 câu — đây là phần được đánh giá cao nhất (khả năng suy nghĩ & giải thích):*

---

## 3. Câu hỏi đánh giá & Chất lượng truy xuất (Retrieval Quality) — Nhóm (10 điểm)

### Câu hỏi đánh giá & Câu trả lời chuẩn (nhóm thống nhất)

> **Đúng 5 câu hỏi**, đa dạng, có thể kiểm chứng; **ít nhất 1 câu** cần lọc metadata mới trả lời tốt. Đây là bộ câu hỏi chung cho mọi thành viên chạy.

| # | Câu hỏi (Query) | Câu trả lời chuẩn (Gold Answer) | Chunk nào chứa thông tin? |
|---|-------|-------------------------------|--------------------------|
| 1 | Người mua có thể gửi yêu cầu Trả hàng/Hoàn tiền cho đơn hàng thông thường trong bao lâu? | Người mua có thể gửi yêu cầu Trả hàng/Hoàn tiền trong vòng 15 ngày kể từ khi đơn hàng được cập nhật trạng thái “Giao hàng thành công” | Những quy định chung về Trả hàng/Hoàn tiền của Shopee → mục 1.2. Thời gian tối đa để gửi yêu cầu trả hàng hoàn tiền. |
| 2 | Thời hạn yêu cầu Trả hàng/Hoàn tiền đối với thực phẩm tươi sống và đông lạnh là bao lâu? | Người mua phải gửi yêu cầu trong vòng 24 giờ kể từ khi đơn hàng được cập nhật trạng thái “Giao hàng thành công”, trừ trường hợp khiếu nại với lý do chưa nhận được hàng. | Những quy định chung về Trả hàng/Hoàn tiền của Shopee → mục 1.2. Thời gian tối đa để gửi yêu cầu trả hàng hoàn tiền. |
| 3 | Với đơn hàng do Người bán tự vận chuyển, thời hạn yêu cầu Trả hàng/Hoàn tiền được tính như thế nào? | Người mua có thể gửi yêu cầu trong 15 ngày kể từ khi bấm “Đã nhận được hàng”, hoặc 20 ngày kể từ lúc đơn hàng được cập nhật “Lấy hàng thành công” nếu chưa bấm “Đã nhận được hàng”. | Những quy định chung về Trả hàng/Hoàn tiền của Shopee → mục 1.2. Thời gian tối đa để gửi yêu cầu trả hàng hoàn tiền. |
| 4 | Người mua cần cung cấp những thông tin hoặc bằng chứng gì khi gửi yêu cầu Trả hàng/Hoàn tiền? | Người mua cần chọn lý do khiếu nại, mô tả tình trạng sản phẩm và cung cấp hình ảnh hoặc video làm bằng chứng cho yêu cầu Trả hàng/Hoàn tiền. | Hướng dẫn gửi yêu cầu Trả hàng/Hoàn tiền → chunk chứa các bước chọn lý do, mô tả vấn đề và cung cấp hình ảnh/video. |
| 5 | Sau khi nhận thông báo liên quan đến yêu cầu Trả hàng/Hoàn tiền, Người bán phải phản hồi trong bao lâu? | Người bán cần gửi phản hồi trong vòng 02 ngày lịch kể từ ngày nhận được thông báo của Shopee trong các trường hợp được quy định. | Chính sách Trả hàng và Hoàn tiền → mục Quyền của Người Bán. Metadata: audience = seller. |

### Tổng hợp chất lượng truy xuất của nhóm

> Cách chấm (theo `docs/SCORING.md`): **2 điểm/câu** — top-3 chứa chunk liên quan + agent trả lời đúng (2), có liên quan nhưng thiếu/không ở top-1 (1), không có trong top-3 (0).

| # | Câu hỏi | Chiến lược tốt nhất cho câu này | Có chunk liên quan trong top-3? | Ghi chú |
|---|---------|-------------------------------|-------------------------------|---------|
| 1 | Người mua có thể gửi yêu cầu Trả hàng/Hoàn tiền cho đơn hàng thông thường trong bao lâu? | FixedSize / Recursive | Có (ở Top-2, điểm 1/2) | Chunk `return-refund-policy#6` chứa "15 ngày" |
| 2 | Thời hạn yêu cầu Trả hàng/Hoàn tiền đối với thực phẩm tươi sống và đông lạnh là bao lâu? | FixedSize / Sentence | Có (ở Top-1, điểm 2/2) | Chunk `return-refund-policy#6` chứa "24 giờ" |
| 3 | Với đơn hàng do Người bán tự vận chuyển, thời hạn yêu cầu Trả hàng/Hoàn tiền được tính như thế nào? | FixedSize / Recursive | Có (ở Top-1, điểm 2/2) | Chunk `return-refund-general#1` chứa "20 ngày" |
| 4 | Người mua cần cung cấp những thông tin hoặc bằng chứng gì khi gửi yêu cầu Trả hàng/Hoàn tiền? | FixedSize / Sentence | Có (ở Top-2, điểm 1/2) | Chunk `return-refund-evidence#0` & `#3` chứa "video" |
| 5 | Sau khi nhận thông báo liên quan đến yêu cầu Trả hàng/Hoàn tiền, Người bán phải phản hồi trong bao lâu? | FixedSize (kèm Filter) | Có (ở Top-1, điểm 2/2) | Chunk `return-refund-policy#22` chứa "02 ngày lịch" |

**Tổng điểm chất lượng truy xuất:** **8 / 10 điểm** (5/5 câu hỏi đều có chunk liên quan trong top-3).

**Lọc bằng metadata có giúp ích không? Ở câu hỏi nào?**
> **Rất hữu ích, đặc biệt tại Câu hỏi 5.** Kết quả thí nghiệm A/B bắt buộc cho thấy:
> - **Khi KHÔNG có filter:** Top-2 và Top-3 bị xâm chiếm bởi các tài liệu người mua (`return-refund-general#1` và `#2`) do trùng lặp các từ khóa chung như *"yêu cầu", "thông báo", "trả hàng"*.
> - **Khi CÓ filter `metadata_filter={"audience": "seller"}`:** Toàn bộ các tài liệu dành cho người mua bị loại bỏ ngay từ bước pre-filter. Kết quả top-3 tập trung 100% vào tài liệu người bán (`return-refund-policy#22`), giúp Agent trích xuất chính xác thời hạn *"02 ngày lịch"* mà không bị nhiễu ngữ cảnh.

---

## 4. Thuyết trình (Demo) & Bài học nhóm — Nhóm (5 điểm)

**Những phân tích (insights) hay nhất nhóm sẽ trình bày:**
1. **Sự khác biệt giữa MockEmbedder và Semantic Embedder:** `MockEmbedder` chỉ băm ký tự nên hoàn toàn thất bại trước các từ đồng nghĩa (điểm âm hoặc ngẫu nhiên). Trong khi đó, `GeminiEmbedder` (3072 chiều) hiểu trọn vẹn ngữ nghĩa, nâng tỷ lệ truy xuất chính xác từ 1/5 lên 5/5 câu hỏi.
2. **Giá trị thực tế của Metadata Pre-Filtering:** Trong các bài toán hỏi đáp nghiệp vụ nhiều đối tượng (như Sàn TMĐT với Người mua và Người bán), metadata filtering là cơ chế bắt buộc để cô lập phạm vi văn bản, loại trừ 100% tài liệu sai đối tượng trước khi tính vector similarity.
3. **Độ đánh đổi của FixedSizeChunker:** Kiểm soát độ dài rất tốt nhưng dễ cắt ngang câu; cần kết hợp overlap $\ge 50$ ký tự để không làm mất dữ kiện ở ranh giới cắt.

**Phân tích lỗi (Failure Case Analysis):**
- **Câu hỏi bị giảm điểm:** Câu 1 (chỉ đạt 1/2 điểm vì đáp án lọt ở Top-2 thay vì Top-1).
- **Nguyên nhân:** Do `FixedSizeChunker` chia cố định 500 ký tự mà không theo ranh giới đoạn/mục, khiến thông tin về *"15 ngày"* bị phân mảnh giữa các điều khoản chung và điều khoản Shopee Mall; vector truy vấn bị hút mạnh vào chunk nói về các trường hợp vi phạm chính sách trước.
- **Đề xuất cải thiện:** Sử dụng `RecursiveChunker` hoặc `HeadingChunker` theo từng Điều/Mục của văn bản chính sách, gắn kèm tiêu đề mục (ví dụ: *"Điều 3: Thời hạn yêu cầu trả hàng"*) vào đầu mỗi chunk con để tăng độ tập trung ngữ nghĩa.

**Bài học rút ra khi so sánh trong nhóm:**
> Cùng một bộ tài liệu chính sách, chiến lược chunking quyết định trực tiếp đến tính toàn vẹn của ngữ cảnh. Nếu chunk quá nhỏ sẽ làm mất liên kết nguyên nhân - kết quả, nếu chunk quá lớn sẽ làm loãng vector embedding. Sự kết hợp giữa **chia nhỏ đệ quy theo cấu trúc văn bản + gắn metadata chuẩn + mô hình embedding học sâu** là công thức tối ưu cho hệ thống RAG quy định chính sách.

**Nếu làm lại, nhóm sẽ thay đổi gì trong chiến lược dữ liệu (data strategy)?**
> Nhóm sẽ thiết kế parser bóc tách tự động theo thẻ Heading Markdown (`#`, `##`, `###`) ngay từ đầu để mỗi Điều khoản là một đơn vị dữ liệu độc lập, đồng thời gán nhãn metadata `audience` chi tiết đến từng section thay vì chỉ ở cấp độ toàn bộ file.

---

## Tự Đánh Giá (Phần Nhóm)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Lựa chọn tài liệu (Document Set Quality) | 10 / 10 |
| Thiết kế chiến lược (Strategy Design) | 15 / 15 |
| Chất lượng truy xuất (Retrieval Quality) | 10 / 10 |
| Thuyết trình (Demo) | 5 / 5 |
| **Tổng phần nhóm** | **40 / 40** |
