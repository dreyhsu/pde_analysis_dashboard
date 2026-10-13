# 檢測數據管理系統

## 專案概述

本專案是一個基於 FastAPI 和 SQLAlchemy 的檢測數據管理系統，提供前端儀表板以可視化檢測事件數據，並支援 CSV 格式的數據下載。系統包含以下功能：

- 動態站點選擇（從資料庫中獲取站點數據）。
- 篩選條件（站點、操作員、日期範圍）查詢檢測事件。
- 顯示總事件數、成功事件數和錯誤事件數，並支援點擊下載符合條件的數據。
- 使用 Chart.js 繪製堆疊柱狀圖，展示每個事件的步驟時長和平均值。

## 專案結構

- `main.py`：後端 FastAPI 應用，包含所有模型定義和 API 端點。
- `init_db.py`：初始化資料庫腳本，用於創建 `stations` 表並插入初始數據。
- `index.html`：前端頁面，提供儀表板和數據可視化功能。
- `example.db`：SQLite 資料庫檔案（自動生成）。

## 依賴項

### 後端依賴
- Python 3.8+
- FastAPI
- SQLAlchemy
- Pandas
- Uvicorn

安裝依賴：
```bash
pip install fastapi sqlalchemy pandas uvicorn
```

若使用 SQLite，無需額外安裝；若使用 PostgreSQL，需安裝：
```bash
pip install psycopg2-binary
```

### 前端依賴
前端使用外部 CDN 載入以下庫，無需手動安裝：
- jQuery
- Luxon
- Chart.js

## 啟動細節

### 1. 初始化資料庫
運行 `init_db.py` 以創建 `stations` 表並插入初始站點數據：
```bash
python init_db.py
```

- 腳本將在當前目錄生成 `example.db`（SQLite 資料庫）。
- 初始數據包含 4 個站點（`站點 STA001` 到 `站點 STA004`），`station_id` 使用 UUID 格式。

**注意**：若資料庫已存在，腳本會檢查並跳過重複初始化。

### 2. 啟動後端服務
使用 Uvicorn 啟動 FastAPI 應用：
```bash
uvicorn main:app --reload --port 8000
```

- 服務將運行在 `http://localhost:8000`。
- `--reload` 啟用自動重載，適合開發環境。

**API 端點**：
- `GET /api/stations`：獲取所有站點數據。
- `POST /api/detection-data`：根據篩選條件返回檢測數據。

### 3. 啟動前端服務
使用 Python 的簡單 HTTP 伺服器啟動前端：
```bash
python -m http.server 8080
```

- 前端將運行在 `http://localhost:8080`。
- 打開瀏覽器，訪問 `http://localhost:8080/index.html`。

### 4. 使用系統
1. **選擇站點**：頁面加載後，`站點` 下拉選單將從後端動態載入站點數據。
2. **設置篩選條件**：
   - 選擇站點（必填）。
   - 可選：輸入操作員 ID、選擇日期範圍。
3. **應用篩選**：點擊「應用篩選」按鈕，查看事件統計和圖表。
4. **下載數據**：點擊「總事件數」、「成功事件數」或「錯誤事件數」卡片，下載符合條件的數據（CSV 格式）。

## 注意事項

- **資料庫**：目前使用 SQLite，若需切換到 PostgreSQL，需修改 `main.py` 和 `init_db.py` 中的 `SQLALCHEMY_DATABASE_URL`。
- **模型定義**：`EventBase` 和 `Details` 模型在 `main.py` 中是假設性定義，需根據實際資料庫結構調整。
- **CSV 編碼**：下載的 CSV 已添加 BOM 前綴，確保中文字在 Excel 中正常顯示。
- **執行順序**：必須先運行 `init_db.py` 初始化資料庫，再啟動後端和前端。


### 下載的 CSV 格式
```
事件ID,組裝開始時間,組裝結束時間,站點ID,操作員ID,產品序列號,批次ID,班次,模型版本,相機ID,組裝結果,影片路徑,組裝記錄寫入時間,檢測項目,檢測結果,異常描述,檢測開始時間,檢測結束時間,檢測持續時間(秒),AI信心分數,檢測記錄寫入時間
"NK-SMT-A_2505040930","2025-05-04 09:30:00","2025-05-04 09:49:00","550e8400-e29b-41d4-a716-446655440000","TW888888","2701-004000-62T","B2504-01","B","YOLOv11.2.3","CAM-03-01","Fail","evidence/event/NK-SMT-A_2505040930.mp4","2025-05-04 09:50:00","board-insertion-01","Pass","","2025-05-04 09:43:30","2025-05-04 09:43:46","16.0","57.9",""
```