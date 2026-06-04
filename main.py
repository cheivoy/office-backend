import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import scan, files, submit, people, verify, reports, eml, batch, sync

app = FastAPI(title="Office Automation API", version="3.0.0")

allowed = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan.router,    prefix="/api")
app.include_router(files.router,   prefix="/api")
app.include_router(submit.router,  prefix="/api")
app.include_router(people.router,  prefix="/api")
app.include_router(verify.router,  prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(eml.router,     prefix="/api")
app.include_router(batch.router,   prefix="/api")
app.include_router(sync.router,    prefix="/api")

@app.get("/")
def root():
    return {"status": "ok", "version": "3.0.0"}


@app.get("/api/health")
def health():
    """檢查資料是否落在持久化 Volume 上。
    persistent=True 表示 DATA_ROOT 已正確指向掛載的 Volume（資料不會在重新部署後消失）。
    persistent=False 表示仍在用容器內暫存空間，重新部署會清空——需到 Railway 設定 Volume + DATA_ROOT。
    """
    import os
    from config import DATA_ROOT, BASE_DIR, PEOPLE_CSV
    data_root = str(DATA_ROOT)
    # 若 DATA_ROOT 環境變數有設、且不在程式目錄底下，視為持久化
    env_set = bool(os.environ.get("DATA_ROOT"))
    inside_app = str(DATA_ROOT).startswith(str(BASE_DIR))
    persistent = env_set and not inside_app
    return {
        "status": "ok",
        "data_root": data_root,
        "data_root_env_set": env_set,
        "persistent": persistent,
        "people_file_exists": PEOPLE_CSV.exists(),
        "hint": (
            "資料已落在持久化 Volume。" if persistent else
            "⚠️ 尚未持久化：請在 Railway 新增 Volume（mount path 例如 /data）"
            "並設定環境變數 DATA_ROOT=/data，否則重新部署會清空資料。"
        ),
    }
