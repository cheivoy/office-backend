# Office Automation — 本地原型後端

## 快速啟動

```bash
cd office-automation
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API 文件：http://localhost:8000/docs

---

## 資料夾結構

```
office-automation/
├── main.py                  # FastAPI 入口
├── config.py                # 路徑、欄位對應、關鍵字設定
├── requirements.txt
├── data/
│   └── people.json          # 員工名單（自動生成）
├── Inbox/                   # 員工丟檔案的地方
├── Departments/             # 掃描後自動分類的目的地
│   └── <專案>/<單位>/<PM>/<英文姓名>/
├── models/
│   └── schemas.py           # Pydantic 資料模型
├── routers/
│   ├── scan.py              # 掃描、導入
│   ├── files.py             # 預覽、下載
│   ├── submit.py            # Excel 寫入
│   └── people.py            # 人員管理 CRUD
└── services/
    ├── people_svc.py        # 員工名單邏輯
    ├── scan_svc.py          # 掃描分類邏輯
    └── excel_svc.py         # Excel 寫入邏輯
```

---

## API 端點總覽

| Method | Path | 說明 |
|--------|------|------|
| POST | `/api/import-files` | 批量上傳檔案到 Inbox |
| POST | `/api/scan-and-classify` | 掃描 Inbox，歸檔，回傳看板資料 |
| GET  | `/api/employee-files/{emp_en}` | 取得員工已歸檔檔案清單 |
| GET  | `/api/preview-file/{emp_en}/{filename}` | 回傳檔案供預覽 |
| GET  | `/api/download-zip/{emp_en}` | 下載單人 zip |
| GET  | `/api/download-all-zip` | 全部員工批量匯出 |
| POST | `/api/submit-data` | 寫入 CHT Nokia / DK Excel |
| POST | `/api/submit-wipro` | 寫入 Wipro SNDA Dashboard |
| GET  | `/api/people` | 取得所有員工 |
| POST | `/api/people` | 新增 / 更新員工 |
| DELETE | `/api/people/{id}` | 刪除員工 |
| POST | `/api/people/import` | 匯入 Excel 名單 |

---

## 寫入 Excel 流程

### CHT Nokia 工作天數表
```
POST /api/submit-data
Content-Type: multipart/form-data

payload_json = {
  "emp_name": "Danny Hsieh",
  "emp_en": "Danny Hsieh",
  "work_days": 20,
  "ess": [{"date":"2026-05-10","tstart":"00:00","tend":"06:00","hours":6.0,"amount":1500,"ns_amount":7000}],
  "ot":  [{"date":"2026-05-23","tstart":"09:00","tend":"18:00","hours":9.0}],
  "ta":  [{"from_date":"2026-05-12","to_date":"2026-05-14","amount":21540}],
  "leave":[{"dates":"0504 0514","type":"sick leave","hours":"3hrs"}],
  "write_target": "cht_nokia"
}
template = <上傳當月 xlsx 檔案>
```

回傳：修改後的 xlsx 檔案（直接下載）

### Wipro SNDA
```
POST /api/submit-wipro
payload_json = {"emp_en":"Ajay Chen","ess_amount":3000,"shift_amount":1000,"ot":[...],"travel_amount":6175}
template = <上傳當月 SNDA xlsx>
sheet_name = "P06_26"   ← 使用者指定，不自動判斷
```

---

## 欄位關鍵字設定（config.py）

在 `FILE_TYPE_KEYWORDS` 中新增關鍵字即可擴充自動分類規則：
```python
FILE_TYPE_KEYWORDS = {
    "task_report": ["taskreport", "task_report", "工作報告"],
    # 新增更多...
}
```

---

## 前端對接

React 前端請將 API base URL 設為 `http://localhost:8000`。
CORS 已設定允許 localhost:3000 和 localhost:5173。
