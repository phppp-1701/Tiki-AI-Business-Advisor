# 🤖 Tiki AI Business Advisor — Final Version

Dự án **Tiki AI Business Advisor** là một hệ thống phân tích dữ liệu thị trường thương mại điện tử Tiki kết hợp với Trợ lý ảo AI (sử dụng mô hình Google Gemini) để tư vấn định hướng kinh doanh cho người bán hàng.

Hệ thống cho phép người dùng tìm kiếm sản phẩm, xem báo cáo xu hướng giá, dự báo doanh thu, phân tích mức độ cạnh tranh, nhận diện rủi ro từ phản hồi của khách hàng (Sentiment Analysis) và tương tác trực tiếp với Trợ lý AI để lập lộ trình triển khai chi tiết cho từng ý tưởng kinh doanh.

---

## 📁 Cấu Trúc Thư Mục 

```
Project_Cloud/
├── README.md               # Hướng dẫn sử dụng tổng quan này
├── run-local.ps1           # Script khởi chạy nhanh hệ thống trên Windows
└── Tiki_Project/
    ├── api/                # Backend API (FastAPI + Python)
    │   ├── main.py         # Điểm khởi chạy API Server
    │   ├── chat_assistant.py  # Logic cốt lõi của Trợ lý AI & công cụ hỗ trợ
    │   ├── gemini_helper.py   # Quản lý gọi API Gemini & cơ chế tự động xoay vòng key/model
    │   ├── search_engine_v2.py # Công cụ tìm kiếm sản phẩm & phân tích thống kê
    │   ├── context_detection.py# Phân loại ngữ cảnh tìm kiếm chuẩn xác
    │   ├── rag_engine.py      # Bộ máy truy xuất thông tin (RAG) sử dụng ChromaDB
    │   ├── data_loader.py     # Nạp dữ liệu sản phẩm, đánh giá và chuỗi thời gian
    │   ├── model_loader.py    # Nạp các mô hình máy học (KMeans, Prophet)
    │   ├── config.py          # Cấu hình tải biến môi trường
    │   ├── requirements.txt   # Danh sách thư viện Backend cần cài đặt
    │   ├── verify_setup.py    # Script xác thực cài đặt dữ liệu/mô hình
    │   └── .env               # File cấu hình khóa API và đường dẫn dữ liệu
    ├── chroma_db/          # Cơ sở dữ liệu Vector của hệ thống RAG
    ├── data/               # File dữ liệu mẫu về sản phẩm, đánh giá và chuỗi thời gian
    ├── module/             # File weights/metadata của các mô hình học máy đã huấn luyện
    └── website/            # Frontend (HTML/CSS/Vanilla JS - Bootstrap & Tailwind)
        ├── index.html      # Trang giao diện chính
        ├── app.js          # Router và quản lý chuyển đổi giữa các tab
        ├── utils.js        # Thư viện tiện ích dùng chung (vẽ biểu đồ, gọi API, PDF)
        └── pages/          # Giao diện từng màn hình (Single, Market Report, Batch)
```

---

## ⚙️ Hướng Dẫn Cài Đặt & Khởi Chạy

### Cách 1: Khởi chạy nhanh bằng Script (Dành riêng cho Windows)
Dự án cung cấp sẵn script PowerShell [run-local.ps1](file:///c:/Users/dinhh/Downloads/Project_Cloud/run-local.ps1) giúp tự động dọn dẹp tiến trình cũ, kích hoạt môi trường ảo `venv`, cài đặt thư viện thiếu, kiểm tra cấu hình `.env`, và khởi chạy song song cả Backend FastAPI và Web Server chỉ với một cú click.

1. Click chuột phải vào file [run-local.ps1](file:///c:/Users/dinhh/Downloads/Project_Cloud/run-local.ps1) và chọn **Run with PowerShell**, hoặc mở terminal chạy lệnh:
   ```powershell
   .\run-local.ps1
   ```
2. Trình duyệt sẽ tự động mở trang web tại địa chỉ: `http://localhost:5501`.

---

### Cách 2: Khởi chạy thủ công từng phần

#### 1. Khởi chạy Backend API (FastAPI)
1. Mở terminal tại thư mục [api](file:///c:/Users/dinhh/Downloads/Project_Cloud/Tiki_Project/api):
   ```bash
   cd Tiki_Project/api
   ```
2. Tạo và kích hoạt môi trường ảo:
   * **Windows (cmd/powershell):**
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```
   * **macOS/Linux:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
3. Cài đặt các thư viện phụ thuộc:
   ```bash
   pip install -r requirements.txt
   ```
4. Đảm bảo cấu hình file `.env` tại thư mục [api/.env](file:///c:/Users/dinhh/Downloads/Project_Cloud/Tiki_Project/api/.env) đã khai báo khóa API Gemini của bạn:
   ```env
   GEMINI_API_KEY=Khóa_Gemini_Của_Bạn
   DATA_PATH=../data
   MODELS_PATH=../module
   CHROMA_DB_PATH=../chroma_db
   EMBEDDING_MODEL=paraphrase-multilingual-mpnet-base-v2
   API_HOST=0.0.0.0
   API_PORT=8000
   ```
5. Khởi chạy FastAPI Server:
   ```bash
   python main.py
   ```
   * Server sẽ chạy tại địa chỉ: `http://localhost:8000`. Bạn có thể truy cập `http://localhost:8000/docs` để xem tài liệu Swagger API chi tiết.

#### 2. Khởi chạy Frontend Website
1. Mở một cửa sổ terminal mới tại thư mục [website](file:///c:/Users/dinhh/Downloads/Project_Cloud/Tiki_Project/website):
   ```bash
   cd Tiki_Project/website
   ```
2. Khởi chạy Web Server cục bộ bằng Python:
   ```bash
   python -m http.server 5501
   ```
3. Mở trình duyệt và truy cập địa chỉ: `http://localhost:5501`.

---

## 🌟 Các Tính Năng Nổi Bật Đã Được Hoàn Thiện

1. **Giao Diện Chatbot Floating 2 Cột (Flex Layout):**
   * Tích hợp chatbot thông minh hỗ trợ tư vấn dưới dạng khung nổi ở góc dưới bên phải màn hình.
   * Giao diện hai cột (side-by-side flex layout) trực quan:
     * Cột bên trái: Danh sách các phiên hội thoại (tạo mới, chọn, xóa).
     * Cột bên phải: Nội dung cuộc hội thoại đang chọn, tích hợp các phím tắt hỏi nhanh theo ngữ cảnh tìm kiếm.
   * Đồng bộ hóa và lưu trữ lịch sử tin nhắn tự động dưới LocalStorage giúp dữ liệu không bị mất khi chuyển trang.

2. **Cơ Chế Xoay Vòng API Key & Model (Quota & Rate Limit Management):**
   * **Xoay vòng API Key:** Cấu hình biến `GEMINI_API_KEY` trong file `.env` hỗ trợ một danh sách các key phân tách bởi dấu phẩy. Khi bất kỳ key nào gặp lỗi vượt giới hạn (429 Rate Limit / Quota Exhausted), hệ thống sẽ tự động chuyển sang key tiếp theo.
   * **Xoay vòng Model:** Danh sách các model dự phòng được ưu tiên (`gemini-flash-latest` ➜ `gemini-1.5-flash` ➜ `gemini-1.5-flash-8b` ➜ `gemini-1.5-pro`). Hệ thống sẽ chuyển model khi xảy ra lỗi trên cùng một key, và xoay key mới khi thử hết các model.
   * **Reconstruct Chat:** Khi đổi key hoặc model giữa chừng, hệ thống tự động dựng lại phiên chat bằng cách nạp lại lịch sử hội thoại trước đó để đảm bảo trải nghiệm liền mạch cho người dùng.

3. **Phân Tích Ngữ Cảnh & RAG (Retrieval-Augmented Generation):**
   * Tích hợp công nghệ tìm kiếm ngữ cảnh dựa trên AI để phát hiện đúng ý đồ tìm kiếm của người dùng (Ví dụ: "sạc" ➜ Phân loại sang "Thiết bị số - Phụ kiện số").
   * RAG kết hợp ChromaDB và mô hình Sentence-Transformers để truy xuất dữ liệu nội bộ một cách chuẩn xác, trả về câu trả lời đáng tin cậy.

4. **Học Máy Thống Kê & Phân Cụm (Clustering & Opportunities):**
   * Sử dụng mô hình K-Means để phân cụm sản phẩm theo phân khúc giá và độ phổ biến.
   * Tính toán điểm cơ hội kinh doanh (Opportunity Score) giúp xác định những thị trường ngách màu mỡ (Thị trường Đại dương xanh).
   * Mô hình Prophet dự đoán doanh thu tiềm năng trong tương lai.
