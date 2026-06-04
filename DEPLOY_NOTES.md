# 部署與本次修改說明

本次更新解決四個問題：資料持久化、導入失敗、檔案錯置、月份名單覆蓋/刪除。

---

## 1. 資料持久化（最重要）— 解決 Railway 重啟清空

### 原因
舊版把 Inbox / Departments / data 都放在程式目錄底下，Railway 每次重新部署
（ephemeral storage）就會清空，等於每次升級都掉資料。

### 解法
新增環境變數 `DATA_ROOT`，所有「會變動的資料」都集中在它底下：

```
DATA_ROOT/
├── Inbox/
├── Departments/
└── data/
    ├── people.json
    ├── forms.json
    ├── progress.json
    └── roster_2026-P05.json ...
```

固定範本 `templates/`（CHT Nokia / DK）仍跟程式碼走，不需持久化。

### 部署後務必確認（重要）
部署完成後打開：
```
https://<你的後端網址>/api/health
```
- 若 `"persistent": true` → 設定成功，資料不會再因重新部署而消失。
- 若 `"persistent": false` → **代表還沒設定 Volume**，照上面四步驟做完再重新部署。
  在這之前，資料每次 redeploy 都會被清空（這就是「為什麼 redeploy 後資料不見」的原因
  ——程式已支援持久化，但必須在 Railway 掛載 Volume 才會生效）。

### Railway 設定步驟（只需做一次）
1. 進入 service → **Volumes** → New Volume
2. **Mount path** 設為 `/data`
3. 到 **Variables** 新增環境變數：`DATA_ROOT=/data`
4. 重新部署

之後不論部署幾次，資料都保留在 Volume，不會被清空。

### 本機開發
不設 `DATA_ROOT` 時，預設使用專案目錄下的 `./data_root`，行為與舊版相同。

> 進一步（選配）：若日後要做異地備份，可在此架構上加 S3/GCS 定期同步，
> 因為所有資料都已集中在 DATA_ROOT，加備份只需掃這一個資料夾。

---

## 2. 導入失敗

`/api/import-files` 直接用 `f.filename` 組路徑，遇到資料夾上傳（含 `/`）或
含 `..`、絕對路徑的檔名時會失敗，也有路徑穿越風險。已改為先過濾安全的相對
路徑片段（去掉 `""`、`.`、`..`、`/`）再組路徑。

---

## 3. 檔案錯置（導入時顯示正確、實際歸檔錯人）

### 原因
`find_by_name` 用 `any(part in name ...)` 的鬆散比對：只要檔名/名稱出現任何
一段姓名片段（例如 "chen"）就會配到**第一個**符合的人。手動指定 / 重新指定
（move-file、assign-manual）都走這條，導致檔案被默默歸到錯的人。

### 解法
- `find_by_name` 改為**嚴格比對**：英文全名（正規化後）完全相等、或中文全名
  完全相等、或英文「名+姓」兩段 token 都完整出現；**有歧義就回傳 None，絕不亂猜**。
- 新增 `find_by_id`，`assign-manual` 與 `move-file` 改為優先用**員工 ID** 定位。
- 前端 `EmpSelect` 改用員工 id 當選項值，`confirmReview` 送出 `emp_id` / `target_id`。

---

## 4. 月份名單：覆蓋 + 刪除

- **重新匯入同一月份** → 完全覆蓋該月份名單（不再與舊名單合併）。
- **不再污染全域名單**：匯入月份名單時，離職者不會永久殘留在全域。
- 新增：
  - `DELETE /api/people/{id}?period=2026-P05` — 從某月份名單刪一人
  - `DELETE /api/people/roster/{period}` — 刪整份月份名單（之後回退用全域）
  - `POST /api/people?period=2026-P05` — 在某月份名單新增/編輯
- 前端「人員管理」頁在查看月份名單時，新增/編輯/刪除都只影響該月份，
  並新增「🗑 刪除整份名單」按鈕。

---

## 其他
- 已移除本次修改檔案中的未使用 import / 變數，避免部署告警。
- 注意：`excel_svc.py`、`batch_write_svc.py`、`verify_svc.py`、`routers/batch.py`
  仍有少數**既有**未使用 import（屬警告非錯誤，不影響 Python 部署），本次未動，
  如需一併清理可再告知。
