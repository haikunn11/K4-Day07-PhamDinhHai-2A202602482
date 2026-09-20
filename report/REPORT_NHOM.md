# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** BotVN
**Thành viên:** 
- Trần Tuấn Hoàng - 2A202602832
- Nguyễn Văn Đại - 2A202602477
- Phạm Đình Hải - 2A202602482
**Ngày:** 20/09/2026

> **Nộp 1 bản / nhóm.** Phần cá nhân (hướng tiếp cận, kết quả riêng, dự đoán…) mỗi thành viên nộp riêng trong `REPORT_CANHAN.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần nhóm: 40** = Lựa chọn tài liệu (10) + Thiết kế chiến lược (15) + Chất lượng truy xuất (10) + Thuyết trình (5).

---

## 1. Lựa chọn tài liệu (Document Set Quality) — Nhóm (10 điểm)

### Chủ đề (Domain) & Lý Do Chọn

**Chủ đề:** Chính sách Trả hàng và Hoàn tiền Shopee (E-commerce Return & Refund Policy)

**Tại sao nhóm chọn chủ đề này?**
> Nhóm chọn chủ đề "Chính sách Trả hàng và Hoàn tiền Shopee" vì đây là tập tài liệu thực tế chứa nhiều quy định phức tạp, các mốc thời gian và điều kiện ràng buộc đa dạng. Đặc thù của các chính sách thương mại điện tử này tạo ra một kịch bản hỏi đáp (Q&A) lý tưởng để thử nghiệm hệ thống truy xuất thông tin. Qua đó, nhóm có thể đánh giá một cách rõ nét hiệu quả của các chiến lược phân mảnh dữ liệu (chunking) cũng như khả năng tìm kiếm ngữ nghĩa của Vector Store trong bài Lab 7.

### Danh sách tài liệu (Data Inventory)

| # | Tên tài liệu | Nguồn (Source URL) | Ngày lấy / Phiên bản | Số ký tự | Metadata đã gán |
|---|--------------|------------|--------------------|----------|-----------------|
| 1 | Trả hàng/Hoàn tiền - Hướng dẫn chuẩn bị bằng chứng khi yêu cầu Trả hàng/Hoàn tiền | https://help.shopee.vn/portal/4/article/79467 | 2026-09-20 / not-stated | 4661 | `doc_id`: return-refund-evidence, `audience`: buyer, `category`: returns-policy |
| 2 | Trả hàng/Hoàn tiền - Những quy định chung về Trả hàng/Hoàn tiền của Shopee | https://help.shopee.vn/portal/4/article/188931 | 2026-09-20 / not-stated | 8654 | `doc_id`: return-refund-general, `audience`: buyer, `category`: returns-policy |
| 3 | Thời hạn đổi trả và hoàn tiền (Chính sách Trả hàng và Hoàn tiền) | https://help.shopee.vn/portal/4/article/77251 | 2026-09-20 / not-stated | 25718 | `doc_id`: return-refund-policy, `audience`: seller, `category`: returns-policy |
| 4 | Trả hàng/Hoàn tiền - Thời gian nhận tiền hoàn và cách kiểm tra tiền hoàn | https://help.shopee.vn/portal/4/article/189473 | 2026-09-20 / not-stated | 5136 | `doc_id`: return-refund-receiving, `audience`: buyer, `category`: returns-policy |
| 5 | Trả hàng/Hoàn tiền - Thời gian nhận tiền hoàn và cách kiểm tra tiền hoàn | https://help.shopee.vn/portal/4/article/79467 | 2026-09-20 / not-stated | 5136 | `doc_id`: return-refund-seller, `audience`: buyer, `category`: returns-policy |
| 6 | Trả hàng/Hoàn tiền - Các phương thức gửi hàng hoàn trả và phí hoàn trả | https://help.shopee.vn/portal/4/article/189477 | 2026-09-20 / not-stated | 8027 | `doc_id`: return-refund-shipping, `audience`: buyer, `category`: returns-policy |
| 7 | Trả hàng/Hoàn tiền - Theo dõi tình trạng Trả hàng/Hoàn tiền trên Shopee | https://help.shopee.vn/portal/4/article/79298 | 2026-09-20 / not-stated | 2097 | `doc_id`: return-refund-tracking, `audience`: buyer, `category`: returns-policy |

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
| Tài liệu | Chiến lược (Chunker) | Số chunk | Độ dài TB (ký tự) | Đánh giá & Nhận xét chất lượng chunk |
| :--- | :--- | :---: | :---: | :--- |
| `return-refund-evidence.md` | RecursiveChunker (`recursive`) | 11 | 398.5 | **Tốt nhất (Hạng 1):** Ranh giới chunk tự nhiên theo đoạn (`\n\n`) và câu; giữ trọn các danh mục tài liệu bằng chứng và ví dụ đi kèm mà không gây phân mảnh ngữ nghĩa. |
| | FixedSizeChunker (`fixed_size`) | 10 | 465.2 | **Khá (Hạng 2):** Chiều dài chunk rất đồng đều; phần overlap 50 ký tự gối đầu hỗ trợ giảm thiểu hiện tượng mất mốc thời gian hoặc đứt từ so với fixed size không overlap. |
| | HeadingChunker (`heading_based`) | 14 | 285.4 | **Tệ nhất (Hạng 3):** Độ dài chunk chênh lệch quá lớn giữa các mục; xuất hiện nhiều chunk ngắn mang tính tiêu đề thuần túy, gây loãng vector embedding và giảm hiệu quả truy vấn. |
| `return-refund-general.md` | RecursiveChunker (`recursive`) | 19 | 415.8 | **Tốt nhất (Hạng 1):** Phân chia mượt mà theo từng cặp câu hỏi - giải đáp (Q&A); không bị ngắt cụt câu trả lời, kích thước chunk vừa vặn với context window. |
| | FixedSizeChunker (`fixed_size`) | 18 | 472.0 | **Khá (Hạng 2):** Cắt theo kích thước cố định nên đôi lúc ranh giới rơi vào giữa câu, tuy nhiên overlap 50 ký tự giữ lại được từ khóa ngữ cảnh cốt lõi. |
| | HeadingChunker (`heading_based`) | 24 | 310.2 | **Tệ nhất (Hạng 3):** Việc tự động thêm heading vào đầu chunk con gây dư thừa ký tự và nhiễu ngữ cảnh lặp lại; nhiều phần giải thích bị bẻ gãy không tự nhiên. |
| `return-refund-policy.md` | RecursiveChunker (`recursive`) | 58 | 425.6 | **Tốt nhất (Hạng 1):** Tôn trọng tuyệt đối phân cấp văn bản pháp lý; bảo toàn mối liên hệ logic giữa điều khoản chung và các điểm hướng dẫn cụ thể mà không làm tràn context. |
| | FixedSizeChunker (`fixed_size`) | 57 | 481.3 | **Khá (Hạng 2):** Đạt độ đồng nhất dữ liệu cao; kích thước 500 ký tự cùng overlap 50 ký tự giữ được tính toàn vẹn cơ bản của hầu hết các điều khoản quy định. |
| | HeadingChunker (`heading_based`) | 76 | 322.8 | **Tệ nhất (Hạng 3):** Các điều khoản dài bị phân mảnh thành nhiều chunk con gắn lặp tiêu đề cha; các tiểu mục ngắn tạo thành các chunk rác có dung lượng quá nhỏ, làm giảm độ chính xác của BM25 và Vector Search. |

### Chiến lược của từng thành viên

> Mỗi thành viên thử nghiệm một chiến lược khác nhau trên cùng tập dữ liệu `data/return-refund/`.

**Thành viên 1 — [Tên Thành viên 1 - R1]**
- **Loại chiến lược:** FixedSizeChunker (`chunk_size=500, overlap=50`)
- **Mô tả & lý do chọn cho chủ đề này:** Dùng làm đường cơ sở (baseline) so sánh. Việc áp dụng overlap 50 ký tự gối đầu giữa các chunk giúp hạn chế việc đứt gãy thông tin quan trọng (như các mốc thời gian 15 ngày, 24 giờ) khi chúng vô tình rơi đúng vào ranh giới chia cắt cố định.
- **Code snippet (nếu custom):** Sử dụng `FixedSizeChunker` mặc định có sẵn trong `src/chunking.py`.

**Thành viên 2 — [Tên bạn - R2]**
- **Loại chiến lược:** RecursiveChunker (`chunk_size=500, separators=["\n\n", "\n", ". ", " ", ""]`)
- **Mô tả & lý do chọn:** Cắt văn bản theo thứ bậc ưu tiên phân cấp tự nhiên của văn bản. Chiến lược này đặc biệt phù hợp với tài liệu chính sách đổi trả vì nó ưu tiên giữ nguyên khối các đoạn văn (`\n\n`) và câu hoàn chỉnh, tránh sinh ra các mẩu vụn ngắn và tối ưu hóa độ liên kết ngữ nghĩa của từng đoạn.
- **Code snippet (nếu custom):** Sử dụng `RecursiveChunker` đã hoàn thiện trong `src/chunking.py`.

**Thành viên 3 — [Tên Thành viên 3 - R3]**
- **Loại chiến lược:** HeadingChunker (Custom Chunker chia theo cấu trúc Tiêu đề / Điều khoản Markdown)
- **Mô tả & lý do chọn:** Khai thác đặc thù cấu trúc pháp lý của chính sách TMĐT vốn được biên soạn sẵn theo từng Điều khoản / Mục (`#`, `##`, `Điều ...`). Mỗi section tạo thành một đơn vị ngữ nghĩa độc lập. Đối với các section dài quá ngưỡng, chunker tự động chia nhỏ nhưng luôn gắn kèm tiêu đề mục ở đầu mỗi chunk con để đảm bảo ngữ cảnh không bị mất (*context preservation*).

### So Sánh Giữa Các Thành Viên

| Thành viên | Chiến lược (Strategy) | Điểm truy xuất (/10) | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|
| Thành viên 1 | FixedSizeChunker (overlap=50) | 8 / 10 | Đơn giản, độ dài chunk ổn định, overlap hỗ trợ các câu giáp ranh. | Dễ bị cắt đứt giữa câu hoặc ngắt rời điều kiện khỏi tiêu đề, giảm độ mạch lạc ngữ nghĩa. |
| Thành viên 2 | RecursiveChunker | 9 / 10 | Giữ trọn câu và đoạn văn tự nhiên, độ dài tối ưu, tính mạch lạc cao. | Chưa tự động truyền tiêu đề cấp cao của điều khoản vào các đoạn con nằm sâu bên dưới. |
| Thành viên 3 | HeadingChunker | 3 / 10 | Bảo toàn trọn vẹn ngữ nghĩa từng điều khoản | Đòi hỏi tài liệu nguồn phải có định dạng tiêu đề chuẩn; các mục quá dài vẫn cần xử lý đệ quy. |

**Chiến lược nào tốt nhất cho chủ đề này? Tại sao?**
> **Chiến lược HeadingChunker (kết hợp phân đoạn theo tiêu đề và gom đoạn)** là chiến lược tốt nhất cho chủ đề chính sách đổi trả / bảo hành TMĐT. Văn bản chính sách có tính phân cấp rất chặt chẽ theo từng điều khoản độc lập; việc giữ nguyên khối theo tiêu đề giúp chunk chứa đầy đủ cả chủ thể áp dụng lẫn chế tài/thời hạn, loại bỏ tình trạng câu trả lời bị cắt rời khỏi điều kiện quy định. Khi kết hợp với bộ lọc metadata `audience`, chiến lược này đạt độ chính xác truy xuất cao nhất cho toàn bộ 5 câu hỏi benchmark.

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
| 1 | Người mua có thể gửi yêu cầu Trả hàng/Hoàn tiền cho đơn hàng thông thường trong bao lâu? | **RecursiveChunker** (Thành viên 2) | Có | `RecursiveChunker` đưa đúng chunk chứa mốc 15 ngày của `return-refund-general` lên Top-1 (score +0.8040, 2/2 điểm). `FixedSizeChunker` đáp án nằm ở Top-2 (1/2 điểm). |
| 2 | Thời hạn yêu cầu Trả hàng/Hoàn tiền đối với thực phẩm tươi sống và đông lạnh là bao lâu? | **FixedSizeChunker** (Thành viên 1) | Có | `FixedSizeChunker` đạt 2/2 điểm khi trúng ngay Top-1 điều khoản thực phẩm tươi sống. `RecursiveChunker` đưa tài liệu policy lên Top-1 và tài liệu general chứa "24 giờ" ở Top-2 (1/2 điểm). |
| 3 | Với đơn hàng do Người bán tự vận chuyển, thời hạn yêu cầu Trả hàng/Hoàn tiền được tính như thế nào? | **RecursiveChunker & FixedSizeChunker** (Thành viên 1 & 2) | Có | Cả hai chiến lược đều đưa đúng chunk mục 1.2 của `return-refund-general` lên Top-1 (score ~0.77–0.79), Agent trả lời chính xác cả mốc 15 ngày và 20 ngày (2/2 điểm). |
| 4 | Người mua cần cung cấp những thông tin hoặc bằng chứng gì khi gửi yêu cầu Trả hàng/Hoàn tiền? | **RecursiveChunker** (Thành viên 2) | Có | `RecursiveChunker` ghép các đoạn liền kề tối ưu, giữ trọn vẹn cả lý do khiếu nại và yêu cầu hình ảnh/video trong một chunk Top-1 duy nhất (+0.8604, 2/2 điểm). |
| 5 | Sau khi nhận thông báo liên quan đến yêu cầu Trả hàng/Hoàn tiền, Người bán phải phản hồi trong bao lâu? | **Cả 3 chiến lược** (kết hợp Metadata Filter) | Có | Khi kích hoạt `metadata_filter={'audience': 'seller'}`, cả 3 thành viên đều đạt 2/2 điểm tuyệt đối ở Top-1, trích xuất chính xác quy định "02 ngày lịch" từ `return-refund-seller`. |

**Lọc bằng metadata có giúp ích không? Ở câu hỏi nào?**
> **Lọc bằng metadata cực kỳ hữu ích, thể hiện rõ rệt nhất ở Câu hỏi 5.** Khi không sử dụng bộ lọc (`metadata_filter=None`), các tài liệu dành cho Người mua (`return-refund-policy`, `return-refund-receiving`) chiếm lĩnh vị trí Top-1 (điểm tương đồng từ 0.8290 đến 0.8318) do tần suất xuất hiện dày đặc của các từ khóa chung như "thông báo", "yêu cầu", "trả hàng", dễ khiến Agent trả lời nhầm sang thời hạn của người mua. Khi kích hoạt tiền lọc `metadata_filter={'audience': 'seller'}`, cả 3 thành viên đều loại bỏ 100% tài liệu nhiễu, đưa chính xác chunk quy định thời hạn "02 ngày lịch" của Người bán lên Top-1 (đạt 2/2 điểm tuyệt đối).

---

## 4. Thuyết trình (Demo) & Bài học nhóm — Nhóm (5 điểm)

**Những phân tích (insights) hay nhất nhóm sẽ trình bày:**
1. **Cấu trúc tài liệu quyết định chất lượng chunking (Domain-driven Chunking):** Với văn bản quy định/chính sách TMĐT, việc chia cắt theo ký tự cố định (`FixedSize`) dễ làm đứt gãy giữa điều kiện và mốc thời gian quy định. Ngược lại, chiến lược phân tách theo tiêu đề điều khoản (`HeadingChunker`) giúp bảo toàn trọn vẹn ngữ nghĩa của từng chế tài và điều kiện đổi trả.
2. **Vai trò then chốt của Metadata Pre-filtering (Bằng chứng A/B Test):** Khi tra cứu nghĩa vụ của Người Bán, nếu không lọc `metadata_filter={"audience": "seller"}`, top-3 kết quả hoàn toàn bị chiếm lĩnh bởi tài liệu của Người Mua (`buyer`) do từ vựng người mua xuất hiện áp đảo. Lọc metadata trước khi search là điều kiện bắt buộc để agent không trả lời sai chủ thể.
3. **Sự đánh đổi giữa Precision và Recall trong kích thước Chunk:** Chunk quá nhỏ (100–200 ký tự) làm mất ngữ cảnh điều kiện, trong khi chunk quá lớn (>1000 ký tự) làm loãng điểm tương đồng cosine do lẫn nhiều thông tin không liên quan. Mức kích thước 400–600 ký tự kết hợp tiêu đề mục là điểm cân bằng lý tưởng cho văn bản quy định.

**Bài học rút ra khi so sánh trong nhóm:**
- Cùng một bộ tài liệu và cùng 5 câu hỏi đánh giá, sự khác biệt giữa các chiến lược chunking thể hiện rõ rệt: `HeadingChunker` đạt độ chính xác cao nhất (9/10) nhờ giữ nguyên khối quy định; `RecursiveChunker` cân bằng tốt tính mạch lạc của câu đoạn; trong khi `FixedSizeChunker` dễ làm rơi rụng thông tin mốc ngày giờ ở các điểm biên.
- Nhóm nhận thấy chất lượng của hệ thống RAG phụ thuộc phần lớn vào bước chuẩn bị và định hình cấu trúc dữ liệu (Data Foundations), hơn là chỉ trông chờ vào khả năng suy luận của mô hình ngôn ngữ ở tầng cuối.

**Nếu làm lại, nhóm sẽ thay đổi gì trong chiến lược dữ liệu (data strategy)?**
- Nhóm sẽ bổ sung thêm metadata phân loại chi tiết hơn ngay từ lúc crawl, ví dụ: `topic: [deadline, evidence, refund_method, exception]` và `product_category: [general, fresh_food, mall]` để hỗ trợ lọc đa tầng.
- Nhóm sẽ triển khai kỹ thuật gắn tiêu đề phân cấp dạng breadcrumb (ví dụ: *Chính sách Shopee > Điều 5. Quyền của Người Bán > Phản hồi*) vào đầu mỗi chunk con, giúp mô hình luôn nắm bắt được ngữ cảnh đầy đủ ngay cả khi văn bản phải chia nhỏ sâu.

---

## Tự Đánh Giá (Phần Nhóm)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Lựa chọn tài liệu (Document Set Quality) | 9/ 10 |
| Thiết kế chiến lược (Strategy Design) | 15/ 15 |
| Chất lượng truy xuất (Retrieval Quality) | 9/ 10 |
| Thuyết trình (Demo) | 4/ 5 |
| **Tổng phần nhóm** | 37/ 40** |
