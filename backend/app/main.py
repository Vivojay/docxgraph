from fastapi import FastAPI, Depends, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_user
from backend.app.api.router import api_router
from backend.app.db.init_db import init_db
from backend.app.models.case import Case, CaseViewLog

app = FastAPI(title="ExperienceGraph")
templates = Jinja2Templates(directory="backend/app/templates")

app.mount("/static", StaticFiles(directory="backend/app/static"), name="static")
app.include_router(api_router, prefix="/api")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "user": user}
    )


@app.get("/cases/new", response_class=HTMLResponse)
def case_new(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(
        "case_new.html", {"request": request, "user": user}
    )


@app.get("/cases/{case_id}/view", response_class=HTMLResponse)
def case_view(
    case_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    case = db.get(Case, case_id)
    if not case or case.org_id != user.org_id:
        return RedirectResponse(url="/dashboard")
    log = CaseViewLog(case_id=case.id, viewer_id=user.id, org_id=user.org_id)
    db.add(log)
    db.commit()
    tags = [ct.tag.name for ct in case.tags]
    return templates.TemplateResponse(
        "case_view.html",
        {"request": request, "user": user, "case": case, "tags": tags},
    )


@app.get("/search", response_class=HTMLResponse)
def search_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(
        "search.html", {"request": request, "user": user}
    )


@app.get("/match", response_class=HTMLResponse)
def match_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(
        "match.html", {"request": request, "user": user}
    )
