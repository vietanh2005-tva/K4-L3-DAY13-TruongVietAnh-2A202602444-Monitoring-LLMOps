# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Truong Viet Anh
- **MSSV:** 2A202602444
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/vietanh2005-tva/K4-L3-DAY13-TruongVietAnh-2A202602444-Monitoring-LLMOps
- **Commit SHA cuối:** Lấy từ `git rev-parse HEAD` sau commit cuối và nộp cùng URL repository trên LMS
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602444`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.txt` |
| Log validator | `evidence/02-log-validator.txt` |
| Dashboard validator | `evidence/03-dashboard-validator.txt` |
| Structured log | `evidence/04-structured-log.txt` |
| PII redaction | `evidence/05-pii-redaction.txt` |
| Trace list | `evidence/06-trace-list.jpg` (IDs: `06-trace-list.txt`) |
| Trace waterfall | `evidence/07-trace-waterfall.jpg` (chi tiết: `.txt`) |
| Trace metadata | `evidence/08-trace-metadata.jpg` (chi tiết: `.txt`) |
| Prompt versions | `evidence/09-prompt-versions.jpg` (chi tiết: `.txt`) |
| Prompt rollback | `evidence/10a-prompt-promote.jpg`, `evidence/10b-prompt-rollback.jpg`, `evidence/10-prompt-rollback.txt` |
| Dashboard runtime | `evidence/11-dashboard-overview.jpg` (bản vector: `.svg`) |
| Incident metric | `evidence/12-incident-metric.jpg` (giá trị: `.txt`) |
| Incident log | `evidence/13-incident-log.txt` |
| Incident trace | `evidence/14-incident-trace.jpg` (chi tiết: `.txt`) |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | Chưa lưu trước khi triển khai CP1 | 100/100 | Schema, correlation ID, enrichment và PII đều đạt |
| `validate_dashboard.py` | 6/6 contract | 6/6 contract | Dashboard runtime sẽ hoàn thiện ở CP2 |
| `pytest` | Chưa lưu trước khi triển khai CP1 | 30 passed | Gồm test correlation ID, headers, PII, trace structure, dashboard runtime, SLO, alerts và challenge contract |
| Số traces hợp lệ | 10 trace trước khi tạo prompt managed | 18 root traces / 54 observations | 10 workload ban đầu, 3 trace prompt-version, 5 trace challenge |
| Số PII leak | Chưa đo | 0 | Validator kiểm tra toàn bộ `data/logs.jsonl` |
| Latency P95 / TTFT P95 | Baseline khoảng 415 ms / 50 ms | 3382 ms / 50 ms trong cửa sổ có challenge | Tail latency vượt SLO do retrieval chậm; TTFT của LLM không đổi |
| Retrieval success rate | 100% | 100% | Incident là chậm, không phải retrieval lỗi |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware xóa context ở đầu request, nhận `x-request-id` nếu client gửi; nếu thiếu thì sinh `req-<8-hex>`. ID được bind vào `structlog`, lưu ở `request.state` và trả lại trong response header `x-request-id`. Header `x-response-time-ms` ghi thời gian xử lý.
- **Các metadata được ghi vào structured log:** `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`, `env`, cùng latency, TTFT, token, cost, quality và trạng thái retrieval ở event tương ứng.
- **Cách bảo đảm PII được scrub trước khi ghi:** `scrub_event` chạy trước `JsonlFileProcessor` và JSON renderer. Processor duyệt đệ quy chuỗi trong dictionary/list/tuple và che email, số điện thoại Việt Nam, CCCD, thẻ thanh toán và passport.
- **Cách kiểm chứng kết quả:** Chạy workload 10 request, `python scripts/validate_logs.py` đạt 100/100 với 10 correlation ID và 0 PII leak; `python -m pytest -q` đạt 28 tests.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Project `day13-k4-l3a-2A202602444` có 18 root traces. Tôi đối chiếu `correlation_id`, session, feature, timestamp và prompt metadata với log/workload của chính repository. Danh sách ID nằm ở `evidence/06-trace-list.txt`.
- **Cấu trúc root/retrieval/generation observations:** Root `lab-agent-run` chứa child `retrieval` loại retriever và `generation` loại generation. Retrieval chỉ lưu query preview đã scrub và số tài liệu; generation lưu prompt preview/metadata đã scrub, model, usage, cost và answer preview.
- **Cách nối trace với log:** `correlation_id` được bind ở middleware, xuất hiện trong structured log và trace metadata.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** version 1, labels `baseline` và `production` sau rollback.
- **Version/label candidate:** version 2, labels `candidate` và `latest`.
- **Trace ID của mỗi version:** baseline `fd505d18326a4167233c50c8c2c20112`; candidate `cf48b0e571e7ffe9f71569c37e7db6c9`.
- **Cách promote và rollback `production`:** Chuyển `production` sang v2, chạy trace `e8c62112a3d7f036e3059117f3b8a978`, sau đó gắn lại `production` cho v1. Trạng thái cuối được kiểm tra qua SDK và giao diện Langfuse: `production -> v1`, `candidate -> v2`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Endpoint `/dashboard` đọc trực tiếp `data/logs.jsonl`, tự refresh 30 giây và hiển thị đúng 6 panel: latency/TTFT, traffic, errors/retrieval success, cost, tokens và quality. Evidence runtime `11-dashboard-overview.svg` cho thấy P95 3382 ms vượt threshold 3000 ms, error 0%, retrieval success 100%, cost $0.033774, 513 input tokens, 2149 output tokens và quality 0.867.
- **SLO và lý do chọn:** Trong 28 ngày, 99.5% request phải có `response_sent` và latency không quá 3000 ms. Ngưỡng này đo trực tiếp trải nghiệm thành công và tốc độ của người dùng.
- **Cách tính error budget:** `100% - 99.5% = 0.5%`; tương đương tối đa 5 bad requests trên 1000 requests trong cửa sổ đo.
- **Ba alert và runbook tương ứng:** `high_tail_latency`, `elevated_error_rate`, `low_quality_proxy`; chi tiết condition, duration, owner, Slack channel và mitigation nằm trong `config/alert_rules.yaml` và `docs/alerts.md`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** `2026-09-29 14:30:42–14:30:56` Asia/Ho_Chi_Minh (`07:30:42–07:30:56Z`).
- **Triệu chứng từ metrics:** Latency P95 tăng lên 3382 ms, vượt SLO 3000 ms; TTFT P95 vẫn 50 ms, error rate 0% và retrieval success 100%. Phía client, 5 request concurrency đều chờ khoảng 14 giây do bị xếp hàng.
- **Log line và correlation ID liên quan:** `req-8de5e3d9`, event `response_sent`, latency 2652 ms, TTFT 50 ms, retrieval thành công; xem `evidence/13-incident-log.txt`.
- **Trace ID và span gây ảnh hưởng:** trace `dbdfdd1ad30040ef591665fc0ba4884b`; root 2.654 s, child `retrieval` 2.502 s, child `generation` 0.151 s.
- **Root cause:** Challenge `rag_slow` thêm khoảng 2.5 giây vào retrieval. Hàm retrieval đồng bộ chạy trực tiếp trong endpoint async nên event loop bị chặn; với concurrency 5, các request bị xử lý nối tiếp và client quan sát khoảng 14 giây.
- **Fix action:** Tắt incident ngay sau workload; trong production, thay sleep/blocking I/O bằng async client hoặc chạy phần blocking qua thread pool, đồng thời đặt timeout/circuit breaker cho vector store.
- **Preventive measure:** Alert trên P95 trong duration đủ dài, theo dõi riêng retrieval span, đặt SLO/timeout cho dependency và chạy load test concurrency trong CI trước khi promote prompt/model/retriever.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Không capture raw prompt/output trong trace. Chỉ lưu preview đã scrub, usage, cost và metadata cần điều tra để vẫn quan sát được hệ thống mà không đưa PII lên dịch vụ telemetry.
- **Một lỗi/blocker đã gặp:** 10 trace đầu ghi `prompt_source=local-fallback`, `prompt_version=local-v1` vì project chưa có prompt managed `day13-chat`.
- **Cách tìm nguyên nhân và xử lý:** Kiểm tra trace metadata, tạo prompt v1/v2 đúng contract trên Langfuse, chạy lại cùng input với labels `baseline`/`candidate`, sau đó promote và rollback `production`. Các trace sau đó ghi `prompt_source=langfuse` và version thật.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics phát hiện P95 vượt 3000 ms và khoanh vùng thời gian; log trong cửa sổ đó cung cấp `correlation_id`; trace cùng ID tách tổng latency thành retrieval 2.502 s và generation 0.151 s, nhờ vậy kết luận nguyên nhân nằm ở retrieval chứ không phải LLM.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version giúp biết chính xác request dùng nội dung nào và rollback an toàn. Token/cost phát hiện output dài hoặc cost spike. SLO chuyển kỳ vọng thành ngưỡng đo được, còn error budget 0.5% cho biết mức sai hỏng chấp nhận trong cửa sổ 28 ngày.
- **Điều quan trọng nhất đã học:** Một biểu đồ xấu chỉ cho biết triệu chứng; phải nối metric với log và trace của cùng request mới chứng minh được root cause.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Dashboard dùng dữ liệu structured log local thay vì một dịch vụ dashboard bên ngoài; logic và 6 panel vẫn bám đúng `config/dashboard.yaml`. Evidence có cả ảnh giao diện runtime và bản text xuất từ Langfuse API v4 để đối chiếu ID.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả evidence/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và không lộ secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
