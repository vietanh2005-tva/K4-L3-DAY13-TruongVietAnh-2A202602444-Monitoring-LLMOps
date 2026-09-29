# Alert và runbook

Các alert dưới đây dựa trên triệu chứng người dùng hoặc SLO. Quy trình điều tra
luôn bắt đầu từ khoảng thời gian của metric, sau đó lấy `correlation_id` trong
log và mở trace tương ứng để tìm span gây ảnh hưởng.

## Alert 1: High tail latency

- **Severity:** page
- **Duration:** 10 phút
- **Kênh:** `#ai-api-alerts`
- **Owner:** `ai-api-oncall`
- **Điều kiện:** latency P95 lớn hơn 3000 ms liên tục 10 phút.
- **SLI/SLO:** `fast_successful_requests`; request chậm hơn 3000 ms tiêu thụ error budget.
- **Ảnh hưởng:** phần lớn request vẫn thành công nhưng người dùng ở tail phải chờ lâu.
- **Kiểm tra:** xác định time window trên panel latency; lọc `response_sent` chậm và lấy `correlation_id`; mở trace để so sánh `retrieval` với `generation`.
- **Mitigation:** giảm concurrency hoặc traffic, rollback prompt/model vừa thay đổi, và vô hiệu incident/retry bất thường nếu có.

## Alert 2: Elevated error rate

- **Severity:** page
- **Duration:** 5 phút
- **Kênh:** `#ai-api-alerts`
- **Owner:** `ai-api-oncall`
- **Điều kiện:** error rate lớn hơn 2% liên tục 5 phút.
- **SLI/SLO:** request không có `response_sent` thành công là bad event.
- **Ảnh hưởng:** người dùng nhận HTTP 5xx hoặc không nhận được câu trả lời.
- **Kiểm tra:** xem error breakdown; lọc `request_failed` trong cùng time window; dùng `correlation_id` để mở trace và kiểm tra status của retrieval/generation.
- **Mitigation:** rollback thay đổi gần nhất, tạm dùng fallback, giới hạn retry và khôi phục dependency gây lỗi.

## Alert 3: Low quality proxy

- **Severity:** ticket
- **Duration:** 30 phút
- **Kênh:** `#ai-quality-alerts`
- **Owner:** `ai-quality-owner`
- **Điều kiện:** quality score trung bình nhỏ hơn 0.75 liên tục 30 phút.
- **SLI/SLO:** quality guardrail `quality_score_avg_min: 0.75`.
- **Ảnh hưởng:** request vẫn trả 200 nhưng câu trả lời có thể kém liên quan hoặc thiếu căn cứ.
- **Kiểm tra:** xác định feature bị giảm; lấy mẫu correlation ID có quality thấp; kiểm tra retrieval result, prompt version/label và generation trong trace.
- **Mitigation:** rollback label `production` về prompt ổn định, tăng kiểm tra retrieval và chuyển case rủi ro sang human review.
