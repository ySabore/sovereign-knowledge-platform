from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, health, organizations

app = FastAPI(
    title="Sovereign Knowledge Platform API",
    version="0.1.0",
    description="Phase 0–1 scaffold — auth, orgs, workspaces.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(organizations.router)
app.include_router(organizations.router_w)
