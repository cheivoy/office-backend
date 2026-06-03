import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import scan, files, submit, people, verify, reports, eml

app = FastAPI(title="Office Automation API", version="2.0.0")

# In production, set ALLOWED_ORIGINS env var to your Vercel URL
# e.g. ALLOWED_ORIGINS=https://your-app.vercel.app
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

@app.get("/")
def root():
    return {"status": "ok", "version": "2.0.0"}
