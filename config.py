from pathlib import Path

BASE_DIR   = Path(__file__).parent
INBOX_DIR  = BASE_DIR / "Inbox"
DEPT_DIR   = BASE_DIR / "Departments"
PEOPLE_CSV = BASE_DIR / "data" / "people.json"

INBOX_DIR.mkdir(exist_ok=True)
DEPT_DIR.mkdir(exist_ok=True)
(BASE_DIR / "data").mkdir(exist_ok=True)

# File type keywords for classification
FILE_TYPE_KEYWORDS = {
    "task_report":    ["taskreport", "task_report", "工作報告"],
    "tr_approval":    ["tr_approval", "approval_mail", "approval mail"],
    "ess_approval":   ["ess_approval", "ess approval", "ess"],
    "ot_approval":    ["ot_approval", "ot approval", "_ot_"],
    "ns_approval":    ["ns_approval", "ns approval", "nightshift", "night_shift"],
    "travel_apply":   ["差旅申請", "travel_apply", "travel apply"],
    "travel_approval":["差旅approval", "travel_approval", "差旅 approval"],
    "leave_approval": ["請假approval", "leave_approval", "leave approval"],
}

# Column index mapping for CHT Nokia / DK tables (0-based)
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

# CHT Nokia PM → filename mapping (11 PMs, DK excluded)
CHT_NOKIA_PM_FILES = {
    "Amanda Kuo":       "2026-Nokia_工作天數紀錄表_Amanda_Kuo.xlsx",
    "Angela Lin":       "2026-Nokia_工作天數紀錄表_Angela_Lin.xlsx",
    "Danny Lee":        "2026-Nokia_工作天數紀錄表_Danny_Lee.xlsx",
    "George Liao":      "2026-Nokia_工作天數紀錄表_George_Liao.xlsx",
    "Jessica Lu":       "2026-Nokia_工作天數紀錄表_Jessica_Lu.xlsx",
    "Muller Su":        "2026-Nokia_工作天數紀錄表_Muller_Su.xlsx",
    "Ray Hsu":          "2026-Nokia_工作天數紀錄表_Ray_Hsu.xlsx",
    "Sally":            "2026-Nokia_工作天數紀錄表_Sally.xlsx",
    "Teresa and Dennis":"2026-Nokia_工作天數紀錄表_Teresa_Dennis.xlsx",
    "Victor Chang":     "2026-Nokia_工作天數紀錄表_Victor.xlsx",
    "Winnie Chou":      "2026-Nokia_工作天數紀錄表_Winnie_Chou.xlsx",
}
