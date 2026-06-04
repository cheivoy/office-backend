import os
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Persistence root
# ─────────────────────────────────────────────────────────────────────────────
# 為了解決 Railway ephemeral storage（容器重啟資料清空）的問題：
# 所有「會變動的資料」（Inbox / Departments / data）都放在 DATA_ROOT 之下。
# DATA_ROOT 由環境變數控制，指向 Railway 掛載的持久化 Volume。
#
# 設定方式（Railway）：
#   1. 在 service 設定中新增一個 Volume，Mount path 設為 /data
#   2. 設定環境變數 DATA_ROOT=/data
# 本機開發時不設此變數，預設使用專案目錄下的 ./data_root，行為與舊版一致。
#
# templates/（固定範本）屬於程式碼的一部分，跟著 git 走，不放 Volume。
BASE_DIR     = Path(__file__).parent
DATA_ROOT    = Path(os.environ.get("DATA_ROOT", str(BASE_DIR / "data_root")))

INBOX_DIR     = DATA_ROOT / "Inbox"
DEPT_DIR      = DATA_ROOT / "Departments"
DATA_DIR      = DATA_ROOT / "data"
PEOPLE_CSV    = DATA_DIR / "people.json"

# 固定範本仍跟程式碼一起部署（唯讀），不需持久化
TEMPLATE_DIR  = BASE_DIR / "templates"
CHT_NOKIA_DIR = TEMPLATE_DIR / "cht_nokia"
CHT_DK_DIR    = TEMPLATE_DIR / "cht_dk"

for _d in [INBOX_DIR, DEPT_DIR, DATA_DIR, TEMPLATE_DIR, CHT_NOKIA_DIR, CHT_DK_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# File type keywords for classification
# Order matters: more specific patterns first
FILE_TYPE_KEYWORDS = {
    "task_report": [
        "taskreport", "task_report", "task report",
        "daily task report", "daily_task_report",
        "工作報告", "工作日報",
    ],
    "tr_approval": [
        "tr_approval", "tr approval",
        "approval_mail", "approval mail",
        "re_ tr", "re:tr", "re: tr",
        "approved tr", "tr approved",
    ],
    "ess_approval": [
        "ess_approval", "ess approval",
        "ess_rota", "ess rota",
        "re_ ess", "re: ess",
    ],
    "ot_approval": [
        "ot_approval", "ot approval",
        "ot or shift", "ot_or_shift",
        "overtime approval", "overtime request",
        "shift request",
        "re_ ot", "re: ot",
    ],
    "ns_approval": [
        "ns_approval", "ns approval",
        "night shift", "night_shift", "nightshift",
        "ns request",
        "re_ ns", "re: ns",
    ],
    "travel_approval": [
        "travel_approval", "travel approval",
        "travel datasheet", "travel_datasheet",
        "差旅approval", "差旅 approval",
        "re_ travel", "re: travel",
    ],
    "travel_apply": [
        "差旅申請", "travel_apply", "travel apply",
        "travel application", "travel form",
        "出差申請",
    ],
    "leave_approval": [
        "請假approval", "leave_approval", "leave approval",
        "leave request", "leave form",
        "re_ leave", "re: leave",
    ],
}

# CHT Nokia column mapping (0-based)
CHT_COL = {
    "work_days":   3,   # D
    "leave":       4,   # E
    "ot":          5,   # F
    "ess":         6,   # G
    "night_shift": 7,   # H
    "travel":      8,   # I
}

# Wipro SNDA column mapping (0-based)
WIPRO_COL = {
    "ess":    6,   # G
    "shift":  7,   # H
    "ot":     8,   # I
    "travel": 9,   # J
}

# PM → Nokia template filename
CHT_NOKIA_PM_FILES = {
    "Amanda Kuo":        "2026-Nokia_工作天數紀錄表_Amanda_Kuo.xlsx",
    "Angela Lin":        "2026-Nokia_工作天數紀錄表_Angela_Lin.xlsx",
    "Danny Lee":         "2026-Nokia_工作天數紀錄表_Danny_Lee.xlsx",
    "George Liao":       "2026-Nokia_工作天數紀錄表_George_Liao.xlsx",
    "Jessica Lu":        "2026-Nokia_工作天數紀錄表_Jessica_Lu.xlsx",
    "Muller Su":         "2026-Nokia_工作天數紀錄表_Muller_Su.xlsx",
    "Ray Hsu":           "2026-Nokia_工作天數紀錄表_Ray_Hsu.xlsx",
    "Sally":             "2026-Nokia_工作天數紀錄表_Sally.xlsx",
    "Teresa and Dennis": "2026-Nokia_工作天數紀錄表_Teresa_Dennis.xlsx",
    "Victor Chang":      "2026-Nokia_工作天數紀錄表_Victor.xlsx",
    "Winnie Chou":       "2026-Nokia_工作天數紀錄表_Winnie_Chou.xlsx",
}

# DK template
CHT_DK_TEMPLATE = "MN_CHT_工時紀錄表_template.xlsx"

# Sync data paths
FORMS_JSON    = DATA_DIR / "forms.json"
PROGRESS_JSON = DATA_DIR / "progress.json"
