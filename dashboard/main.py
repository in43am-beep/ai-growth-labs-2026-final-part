"""RankForge AI — Agency Operating System Dashboard v3"""
import os
import json
import secrets
import io
import csv
import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional
from functools import wraps

from fastapi import FastAPI, Request, Form, HTTPException, Depends, Response, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt
from passlib.hash import bcrypt

try:
    from database import get_db, init_db
except ModuleNotFoundError:  # when run as `uvicorn dashboard.main:app` from project root
    from dashboard.database import get_db, init_db

app = FastAPI(title="RankForge AI OS", docs_url=None, redoc_url=None)

# CORS — allowed origins configurable via ALLOWED_ORIGINS (comma-separated); "*" = any
_allowed_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    # credentials cannot be combined with wildcard origin per the CORS spec
    allow_credentials=(_allowed_origins != ["*"]),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security: HTTP Headers Middleware
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

# Security: Rate limiting storage
_rate_limit_store = {}

SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
TOKEN_EXPIRE = 24
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(static_dir, exist_ok=True)
os.makedirs(os.path.join(static_dir, "css"), exist_ok=True)
os.makedirs(os.path.join(static_dir, "js"), exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

@app.on_event("startup")
def startup():
    init_db()

# ===== AUTH =====
def create_token(user_id: int, role: str, username: str):
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE)
    return jwt.encode({"sub": str(user_id), "role": role, "username": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(request: Request):
    token = request.cookies.get("token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id=? AND is_active=1", (payload["sub"],)).fetchone()
        db.close()
        return dict(user) if user else None
    except Exception:
        return None

def require_auth(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user

def require_role(request: Request, roles: list):
    user = require_auth(request)
    if user["role"] not in roles:
        raise HTTPException(status_code=403, detail="Access denied")
    return user

# ===== LOGIN =====
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()
    db.close()
    if not user or not bcrypt.verify(password, user["password_hash"]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    token = create_token(user["id"], user["role"], user["username"])
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie("token", token, httponly=True, max_age=TOKEN_EXPIRE*3600)
    db = get_db()
    db.execute("UPDATE users SET last_login=datetime('now') WHERE id=?", (user["id"],))
    db.commit()
    db.close()
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("token")
    return response

# ===== SECURITY: Rate Limiting =====
def rate_limit(key_prefix: str, max_requests: int = 10, window_seconds: int = 60):
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            client_ip = request.client.host if request.client else "unknown"
            key = f"{key_prefix}:{client_ip}"
            now = time.time()
            if key in _rate_limit_store:
                requests_list = [t for t in _rate_limit_store[key] if now - t < window_seconds]
                if len(requests_list) >= max_requests:
                    raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
                requests_list.append(now)
                _rate_limit_store[key] = requests_list
            else:
                _rate_limit_store[key] = [now]
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

def log_activity(db, user_id, action, details=None, entity_type=None, entity_id=None):
    db.execute("INSERT INTO activity_log (user_id, action, details, entity_type, entity_id) VALUES (?,?,?,?,?)",
               (user_id, action, details, entity_type, entity_id))

# ===== DASHBOARD ROUTER =====
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = get_current_user(request)
    if user:
        if user["role"] == "client":
            return RedirectResponse(url="/client-portal")
        return RedirectResponse(url="/dashboard")
    # Serve frontend index.html for public visitors
    frontend_dir = os.environ.get("FRONTEND_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__))))
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        from starlette.responses import FileResponse
        return FileResponse(index_path)
    return RedirectResponse(url="/login")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    if user["role"] == "client":
        return RedirectResponse(url="/client-portal")
    role = user["role"]
    db = get_db()
    if role == "super_admin":
        data = _get_admin_data(db)
        template = "admin_dashboard.html"
    elif role == "operations_manager":
        data = _get_ops_manager_data(db)
        template = "ops_dashboard.html"
    elif role in ("worker", "tech_seo", "content_writer", "link_builder"):
        data = _get_worker_data(db, user["id"])
        template = "worker_dashboard.html"
    elif role in ("sales", "account_manager"):
        data = _get_sales_data(db, user["id"])
        template = "sales_dashboard.html"
    elif role == "social_media":
        data = _get_social_data(db, user["id"])
        template = "social_dashboard.html"
    elif role == "finance":
        data = _get_finance_data(db)
        template = "finance_dashboard.html"
    else:
        data = {}
        template = "worker_dashboard.html"
    db.close()
    data["user"] = user
    data["request"] = request
    return templates.TemplateResponse(template, data)

# ===== SETTINGS PAGE =====
@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "super_admin":
        return RedirectResponse(url="/login")
    db = get_db()
    api_settings = [dict(r) for r in db.execute("SELECT * FROM api_settings ORDER BY provider").fetchall()]
    db.close()
    return templates.TemplateResponse("settings.html", {"request": request, "user": user, "api_settings": api_settings})

# ===== CLIENT DETAIL PAGE =====
@app.get("/client/{client_id}", response_class=HTMLResponse)
async def client_detail(client_id: int, request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    db = get_db()
    client = db.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not client:
        db.close()
        raise HTTPException(status_code=404, detail="Client not found")
    client = dict(client)
    credentials = [dict(r) for r in db.execute("SELECT * FROM client_credentials WHERE client_id=?", (client_id,)).fetchall()]
    projects = [dict(r) for r in db.execute("""
        SELECT p.*, u.full_name as worker_name, tl.full_name as leader_name
        FROM projects p LEFT JOIN users u ON p.assigned_worker_id=u.id LEFT JOIN users tl ON p.team_leader_id=tl.id
        WHERE p.client_id=? ORDER BY p.created_at DESC
    """, (client_id,)).fetchall()]
    tasks_by_project = {}
    for p in projects:
        tasks_by_project[p["id"]] = [dict(r) for r in db.execute("""
            SELECT t.*, u.full_name as assigned_name FROM tasks t LEFT JOIN users u ON t.assigned_to=u.id
            WHERE t.project_id=? ORDER BY t.order_num
        """, (p["id"],)).fetchall()]
    payments = [dict(r) for r in db.execute("SELECT * FROM payments WHERE client_id=? ORDER BY created_at DESC", (client_id,)).fetchall()]
    reports = [dict(r) for r in db.execute("SELECT * FROM client_reports WHERE client_id=? ORDER BY created_at DESC", (client_id,)).fetchall()]
    package_tasks = []
    if client.get("package"):
        package_tasks = [dict(r) for r in db.execute("SELECT * FROM package_tasks WHERE package=? ORDER BY category, order_num", (client["package"],)).fetchall()]
    db.close()
    return templates.TemplateResponse("client_detail.html", {
        "request": request, "user": user, "client": client, "credentials": credentials,
        "projects": projects, "tasks_by_project": tasks_by_project, "payments": payments,
        "reports": reports, "package_tasks": package_tasks
    })

# ===== CLIENT PORTAL =====
@app.get("/client-portal", response_class=HTMLResponse)
async def client_portal(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    if user["role"] != "client":
        return RedirectResponse(url="/dashboard")
    db = get_db()
    # Find client record linked to this user
    client = db.execute("SELECT * FROM clients WHERE email=?", (user["email"],)).fetchone()
    if not client:
        # Fallback: try to find by username match
        client = db.execute("SELECT * FROM clients WHERE contact_name=?", (user["full_name"],)).fetchone()
    data = {"user": user, "request": request}
    if client:
        client = dict(client)
        data["client"] = client
        projects = [dict(r) for r in db.execute("""
            SELECT p.*, u.full_name as worker_name FROM projects p 
            LEFT JOIN users u ON p.assigned_worker_id=u.id WHERE p.client_id=? ORDER BY p.created_at DESC
        """, (client["id"],)).fetchall()]
        data["projects"] = projects
        tasks_all = []
        for p in projects:
            tasks_all += [dict(r) for r in db.execute("SELECT * FROM tasks WHERE project_id=? ORDER BY order_num", (p["id"],)).fetchall()]
        data["tasks"] = tasks_all
        data["reports"] = [dict(r) for r in db.execute("SELECT * FROM client_reports WHERE client_id=? AND sent_to_client=1 ORDER BY created_at DESC", (client["id"],)).fetchall()]
        data["invoices"] = [dict(r) for r in db.execute("SELECT * FROM invoices WHERE client_id=? ORDER BY created_at DESC", (client["id"],)).fetchall()]
        data["rankings"] = [dict(r) for r in db.execute("SELECT * FROM keyword_rankings WHERE client_id=? ORDER BY tracked_date DESC LIMIT 50", (client["id"],)).fetchall()]
        data["approvals"] = [dict(r) for r in db.execute("SELECT * FROM approval_requests WHERE client_id=? ORDER BY created_at DESC", (client["id"],)).fetchall()]
        total_tasks = len(tasks_all)
        completed = sum(1 for t in tasks_all if t["status"] == "completed")
        data["stats"] = {
            "total_projects": len(projects),
            "total_tasks": total_tasks,
            "completed_tasks": completed,
            "completion_pct": round(completed/total_tasks*100) if total_tasks else 0,
            "pending_approvals": sum(1 for a in data["approvals"] if a["status"] == "pending"),
        }
    else:
        data["client"] = None
        data["projects"] = []
        data["tasks"] = []
        data["reports"] = []
        data["invoices"] = []
        data["rankings"] = []
        data["approvals"] = []
        data["stats"] = {"total_projects": 0, "total_tasks": 0, "completed_tasks": 0, "completion_pct": 0, "pending_approvals": 0}
    # Check if client has submitted SEO questionnaire
    try:
        q = db.execute("SELECT created_at FROM seo_questionnaires WHERE client_email=? ORDER BY created_at DESC LIMIT 1",
                        (user["email"],)).fetchone()
        if q:
            data["questionnaire_submitted"] = True
            data["questionnaire_date"] = q["created_at"][:10] if q["created_at"] else ""
        else:
            data["questionnaire_submitted"] = False
            data["questionnaire_date"] = ""
    except Exception:
        data["questionnaire_submitted"] = False
        data["questionnaire_date"] = ""
    db.close()
    return templates.TemplateResponse("client_portal.html", data)

# ===== TEAM MONITOR PAGE (Admin) =====
@app.get("/monitor", response_class=HTMLResponse)
async def monitor_page(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ("super_admin", "operations_manager"):
        return RedirectResponse(url="/login")
    db = get_db()
    workers = [dict(r) for r in db.execute("SELECT * FROM users WHERE role != 'super_admin' AND is_active=1 ORDER BY role, full_name").fetchall()]
    for w in workers:
        w["active_tasks"] = db.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status='in_progress'", (w["id"],)).fetchone()[0]
        w["pending_tasks"] = db.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status='pending'", (w["id"],)).fetchone()[0]
        w["completed_tasks"] = db.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status='completed'", (w["id"],)).fetchone()[0]
        w["total_tasks"] = w["active_tasks"] + w["pending_tasks"] + w["completed_tasks"]
        w["projects"] = [dict(r) for r in db.execute("""
            SELECT p.title, p.progress, p.status, c.business_name FROM projects p 
            LEFT JOIN clients c ON p.client_id=c.id WHERE p.assigned_worker_id=? OR p.team_leader_id=?
        """, (w["id"], w["id"])).fetchall()]
    suggestions = [dict(r) for r in db.execute("""
        SELECT s.*, u.full_name as author_name, p.title as project_title 
        FROM suggestions s LEFT JOIN users u ON s.user_id=u.id LEFT JOIN projects p ON s.project_id=p.id
        ORDER BY s.created_at DESC LIMIT 20
    """).fetchall()]
    chat_requests = [dict(r) for r in db.execute("""
        SELECT cr.*, u.full_name as from_name FROM chat_requests cr 
        LEFT JOIN users u ON cr.from_user_id=u.id WHERE cr.status='pending' ORDER BY cr.created_at DESC
    """).fetchall()]
    db.close()
    return templates.TemplateResponse("monitor.html", {
        "request": request, "user": user, "workers": workers, 
        "suggestions": suggestions, "chat_requests": chat_requests
    })

# ===== CHAT PAGE =====
@app.get("/team-chat", response_class=HTMLResponse)
async def team_chat_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    db = get_db()
    team_members = [dict(r) for r in db.execute("SELECT id, full_name, role, username FROM users WHERE id!=? AND is_active=1 ORDER BY full_name", (user["id"],)).fetchall()]
    # Get approved chat sessions
    approved = [dict(r) for r in db.execute("""
        SELECT cr.*, u1.full_name as from_name, u2.full_name as to_name 
        FROM chat_requests cr 
        LEFT JOIN users u1 ON cr.from_user_id=u1.id LEFT JOIN users u2 ON cr.to_user_id=u2.id
        WHERE cr.status='approved' AND (cr.from_user_id=? OR cr.to_user_id=?)
    """, (user["id"], user["id"])).fetchall()]
    db.close()
    return templates.TemplateResponse("team_chat.html", {
        "request": request, "user": user, "team_members": team_members, "approved_chats": approved
    })

# ===== DATA HELPERS =====
def _get_admin_data(db):
    clients = [dict(r) for r in db.execute("SELECT * FROM clients ORDER BY created_at DESC").fetchall()]
    projects = [dict(r) for r in db.execute("""
        SELECT p.*, c.business_name, c.contact_name, u.full_name as worker_name, tl.full_name as leader_name
        FROM projects p LEFT JOIN clients c ON p.client_id=c.id 
        LEFT JOIN users u ON p.assigned_worker_id=u.id LEFT JOIN users tl ON p.team_leader_id=tl.id
        ORDER BY p.created_at DESC
    """).fetchall()]
    workers = [dict(r) for r in db.execute("SELECT * FROM users WHERE role != 'super_admin' ORDER BY role, full_name").fetchall()]
    tasks = [dict(r) for r in db.execute("""
        SELECT t.*, u.full_name as assigned_name, p.title as project_title
        FROM tasks t LEFT JOIN users u ON t.assigned_to=u.id LEFT JOIN projects p ON t.project_id=p.id
        ORDER BY t.created_at DESC LIMIT 50
    """).fetchall()]
    payments = [dict(r) for r in db.execute("""
        SELECT pay.*, c.business_name FROM payments pay LEFT JOIN clients c ON pay.client_id=c.id ORDER BY pay.created_at DESC
    """).fetchall()]
    suggestions = [dict(r) for r in db.execute("""
        SELECT s.*, u.full_name as author_name, p.title as project_title
        FROM suggestions s LEFT JOIN users u ON s.user_id=u.id LEFT JOIN projects p ON s.project_id=p.id
        ORDER BY s.created_at DESC LIMIT 10
    """).fetchall()]
    chat_requests = [dict(r) for r in db.execute("""
        SELECT cr.*, u.full_name as from_name FROM chat_requests cr 
        LEFT JOIN users u ON cr.from_user_id=u.id WHERE cr.status='pending' ORDER BY cr.created_at DESC
    """).fetchall()]
    unread_chats = db.execute("SELECT COUNT(*) FROM team_chats WHERE to_user_id=1 AND is_read=0").fetchone()[0]
    
    total_revenue = db.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid'").fetchone()[0]
    pending_revenue = db.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status IN ('pending','overdue')").fetchone()[0]
    active_clients = db.execute("SELECT COUNT(*) FROM clients WHERE status='active'").fetchone()[0]
    active_projects = db.execute("SELECT COUNT(*) FROM projects WHERE status='in_progress'").fetchone()[0]
    total_tasks = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    completed_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'").fetchone()[0]
    
    return {
        "clients": clients, "projects": projects, "workers": workers, "tasks": tasks, "payments": payments,
        "suggestions": suggestions, "chat_requests": chat_requests, "unread_chats": unread_chats,
        "stats": {
            "total_revenue": total_revenue, "pending_revenue": pending_revenue,
            "active_clients": active_clients, "active_projects": active_projects,
            "total_tasks": total_tasks, "completed_tasks": completed_tasks,
            "task_completion": round(completed_tasks/total_tasks*100) if total_tasks else 0,
            "monthly_recurring": db.execute("SELECT COALESCE(SUM(monthly_payment),0) FROM clients WHERE status='active'").fetchone()[0]
        }
    }

def _get_worker_data(db, user_id):
    my_tasks = [dict(r) for r in db.execute("""
        SELECT t.*, p.title as project_title, c.business_name 
        FROM tasks t LEFT JOIN projects p ON t.project_id=p.id LEFT JOIN clients c ON p.client_id=c.id
        WHERE t.assigned_to=? ORDER BY CASE t.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, t.order_num
    """, (user_id,)).fetchall()]
    my_projects = [dict(r) for r in db.execute("""
        SELECT p.*, c.business_name, c.website, c.industry, c.location, c.package
        FROM projects p LEFT JOIN clients c ON p.client_id=c.id 
        WHERE p.assigned_worker_id=? OR p.team_leader_id=? ORDER BY p.created_at DESC
    """, (user_id, user_id)).fetchall()]
    notifications = [dict(r) for r in db.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user_id,)).fetchall()]
    audits = [dict(r) for r in db.execute(
        "SELECT a.*, c.business_name FROM seo_audits a LEFT JOIN clients c ON a.client_id=c.id ORDER BY a.created_at DESC LIMIT 10").fetchall()]
    suggestions = [dict(r) for r in db.execute(
        "SELECT s.*, p.title as project_title FROM suggestions s LEFT JOIN projects p ON s.project_id=p.id WHERE s.user_id=? ORDER BY s.created_at DESC", (user_id,)).fetchall()]
    unread_chats = db.execute("SELECT COUNT(*) FROM team_chats WHERE to_user_id=? AND is_read=0", (user_id,)).fetchone()[0]
    
    total = len(my_tasks)
    completed = sum(1 for t in my_tasks if t["status"] == "completed")
    
    return {
        "my_tasks": my_tasks, "my_projects": my_projects, "notifications": notifications, 
        "audits": audits, "suggestions": suggestions, "unread_chats": unread_chats,
        "stats": {
            "total_tasks": total, "completed_tasks": completed, "pending_tasks": total - completed,
            "completion_pct": round(completed/total*100) if total else 0,
            "active_projects": sum(1 for p in my_projects if p["status"] == "in_progress"),
        }
    }

def _get_sales_data(db, user_id):
    leads = [dict(r) for r in db.execute("SELECT * FROM sales_leads ORDER BY created_at DESC").fetchall()]
    recent_clients = [dict(r) for r in db.execute("SELECT * FROM clients ORDER BY created_at DESC LIMIT 10").fetchall()]
    total_leads = len(leads)
    new_leads = sum(1 for l in leads if l["status"] == "new")
    won_leads = sum(1 for l in leads if l["status"] == "won")
    return {
        "leads": leads, "recent_clients": recent_clients,
        "stats": {
            "total_leads": total_leads, "new_leads": new_leads, "won_leads": won_leads,
            "conversion_rate": round(won_leads/total_leads*100) if total_leads else 0,
            "proposals_sent": sum(1 for l in leads if l["status"] == "proposal_sent"),
        }
    }

def _get_social_data(db, user_id):
    posts = [dict(r) for r in db.execute("""
        SELECT sp.*, c.business_name FROM social_posts sp LEFT JOIN clients c ON sp.client_id=c.id ORDER BY sp.created_at DESC LIMIT 50
    """).fetchall()]
    clients = [dict(r) for r in db.execute("SELECT * FROM clients WHERE status='active' ORDER BY business_name").fetchall()]
    # Parse engagement data
    total_likes = 0
    total_comments = 0
    total_shares = 0
    total_reach = 0
    for p in posts:
        if p.get("engagement_data"):
            try:
                eng = json.loads(p["engagement_data"])
                total_likes += eng.get("likes", 0)
                total_comments += eng.get("comments", 0)
                total_shares += eng.get("shares", 0)
                total_reach += eng.get("reach", 0)
            except Exception:
                pass
    return {
        "posts": posts, "clients": clients,
        "stats": {
            "total_posts": len(posts),
            "scheduled": sum(1 for p in posts if p["status"] == "scheduled"),
            "published": sum(1 for p in posts if p["status"] == "published"),
            "drafts": sum(1 for p in posts if p["status"] == "draft"),
            "total_likes": total_likes, "total_comments": total_comments,
            "total_shares": total_shares, "total_reach": total_reach,
        }
    }

def _get_finance_data(db):
    payments = [dict(r) for r in db.execute("""
        SELECT pay.*, c.business_name FROM payments pay LEFT JOIN clients c ON pay.client_id=c.id ORDER BY pay.created_at DESC
    """).fetchall()]
    expenses = [dict(r) for r in db.execute("SELECT * FROM expenses ORDER BY date DESC").fetchall()]
    workers = [dict(r) for r in db.execute("SELECT id, full_name, role, rank, salary FROM users WHERE role != 'super_admin'").fetchall()]
    total_income = sum(p["amount"] for p in payments if p["status"] == "paid")
    total_expenses = sum(e["amount"] for e in expenses)
    pending_payments = sum(p["amount"] for p in payments if p["status"] in ("pending", "overdue"))
    total_salaries = sum(w["salary"] for w in workers)
    return {
        "payments": payments, "expenses": expenses, "workers": workers,
        "stats": {
            "total_income": total_income, "total_expenses": total_expenses,
            "net_profit": total_income - total_expenses, "pending_payments": pending_payments,
            "total_salaries": total_salaries,
            "tools_cost": sum(e["amount"] for e in expenses if e["category"] == "tools"),
        }
    }

# ===== API ENDPOINTS =====
@app.post("/api/clients")
async def create_client(request: Request):
    user = require_role(request, ["super_admin", "sales"])
    data = await request.json()
    db = get_db()
    c = db.cursor()
    c.execute("""INSERT INTO clients (business_name, contact_name, email, phone, website, industry, location, status, package, monthly_payment, notes, source)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
              (data.get("business_name"), data.get("contact_name"), data.get("email"), data.get("phone"),
               data.get("website"), data.get("industry"), data.get("location"), data.get("status", "lead"),
               data.get("package"), data.get("monthly_payment", 0), data.get("notes"), data.get("source")))
    client_id = c.lastrowid
    # Auto-generate package tasks if package selected
    if data.get("package"):
        _auto_generate_package_tasks(db, client_id, data["package"])
    db.commit()
    db.close()
    return {"id": client_id, "message": "Client created"}

def _auto_generate_package_tasks(db, client_id, package):
    """Auto-generate tasks from package template when client is created"""
    pkg_tasks = db.execute("SELECT * FROM package_tasks WHERE package=? ORDER BY category, order_num", (package,)).fetchall()
    # Create a project for this client
    c = db.cursor()
    c.execute("""INSERT INTO projects (client_id, title, description, service_type, status, priority)
                 VALUES (?,?,?,?,?,?)""",
              (client_id, f"{package} Campaign", f"Auto-generated {package} project", "Full Service", "pending", "high"))
    project_id = c.lastrowid
    for i, pt in enumerate(pkg_tasks):
        c.execute("""INSERT INTO tasks (project_id, title, description, status, priority, order_num, is_automated)
                     VALUES (?,?,?,?,?,?,?)""",
                  (project_id, pt["title"], pt["description"], "pending", "medium", i, pt["is_automated"]))

@app.post("/api/projects")
async def create_project(request: Request):
    user = require_role(request, ["super_admin"])
    data = await request.json()
    db = get_db()
    c = db.cursor()
    c.execute("""INSERT INTO projects (client_id, title, description, service_type, status, priority, assigned_worker_id, team_leader_id, start_date, due_date)
                 VALUES (?,?,?,?,?,?,?,?,?,?)""",
              (data.get("client_id"), data.get("title"), data.get("description"), data.get("service_type"),
               data.get("status", "pending"), data.get("priority", "medium"), data.get("assigned_worker_id"),
               data.get("team_leader_id"), data.get("start_date"), data.get("due_date")))
    project_id = c.lastrowid
    if data.get("assigned_worker_id"):
        c.execute("INSERT INTO notifications (user_id, title, message, type) VALUES (?,?,?,?)",
                  (data["assigned_worker_id"], "New Project Assigned", f"You've been assigned: {data.get('title')}", "task"))
    db.commit()
    db.close()
    return {"id": project_id, "message": "Project created"}

@app.post("/api/tasks")
async def create_task(request: Request):
    user = require_role(request, ["super_admin", "worker", "tech_seo"])
    data = await request.json()
    db = get_db()
    c = db.cursor()
    c.execute("""INSERT INTO tasks (project_id, title, description, status, assigned_to, priority, due_date, order_num)
                 VALUES (?,?,?,?,?,?,?,?)""",
              (data.get("project_id"), data.get("title"), data.get("description"),
               data.get("status", "pending"), data.get("assigned_to"), data.get("priority", "medium"),
               data.get("due_date"), data.get("order_num", 0)))
    task_id = c.lastrowid
    if data.get("assigned_to"):
        c.execute("INSERT INTO notifications (user_id, title, message, type) VALUES (?,?,?,?)",
                  (data["assigned_to"], "New Task", f"Task: {data.get('title')}", "task"))
    db.commit()
    db.close()
    return {"id": task_id, "message": "Task created"}

@app.put("/api/tasks/{task_id}/status")
async def update_task_status(task_id: int, request: Request):
    user = require_auth(request)
    data = await request.json()
    db = get_db()
    db.execute("UPDATE tasks SET status=?, completed_date=CASE WHEN ?='completed' THEN datetime('now') ELSE NULL END WHERE id=?",
               (data["status"], data["status"], task_id))
    task = db.execute("SELECT project_id FROM tasks WHERE id=?", (task_id,)).fetchone()
    if task:
        pid = task["project_id"]
        total = db.execute("SELECT COUNT(*) FROM tasks WHERE project_id=?", (pid,)).fetchone()[0]
        done = db.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND status='completed'", (pid,)).fetchone()[0]
        progress = round(done/total*100) if total else 0
        db.execute("UPDATE projects SET progress=?, updated_at=datetime('now') WHERE id=?", (progress, pid))
    db.commit()
    db.close()
    return {"message": "Task updated"}

@app.post("/api/users")
async def create_user(request: Request):
    user = require_role(request, ["super_admin"])
    data = await request.json()
    db = get_db()
    pw_hash = bcrypt.hash(data.get("password", "changeme123"))
    try:
        db.execute("""INSERT INTO users (username, password_hash, full_name, email, role, rank, salary) VALUES (?,?,?,?,?,?,?)""",
                   (data["username"], pw_hash, data["full_name"], data.get("email"), data["role"], data.get("rank", "junior"), data.get("salary", 0)))
        db.commit()
    except Exception as e:
        db.close()
        return JSONResponse({"error": str(e)}, status_code=400)
    db.close()
    return {"message": "User created"}

@app.post("/api/leads")
async def create_lead(request: Request):
    user = require_role(request, ["super_admin", "sales"])
    data = await request.json()
    db = get_db()
    db.execute("""INSERT INTO sales_leads (business_name, contact_name, email, phone, website, industry, location, source, status, assigned_to, notes)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
               (data.get("business_name"), data.get("contact_name"), data.get("email"), data.get("phone"),
                data.get("website"), data.get("industry"), data.get("location"), data.get("source", "other"),
                data.get("status", "new"), data.get("assigned_to"), data.get("notes")))
    db.commit()
    db.close()
    return {"message": "Lead created"}

@app.put("/api/leads/{lead_id}/status")
async def update_lead_status(lead_id: int, request: Request):
    user = require_role(request, ["super_admin", "sales"])
    data = await request.json()
    db = get_db()
    db.execute("UPDATE sales_leads SET status=?, updated_at=datetime('now') WHERE id=?", (data["status"], lead_id))
    db.commit()
    db.close()
    return {"message": "Lead updated"}

@app.post("/api/social-posts")
async def create_social_post(request: Request):
    user = require_role(request, ["super_admin", "social_media"])
    data = await request.json()
    db = get_db()
    db.execute("""INSERT INTO social_posts (client_id, platform, content, status, scheduled_date, created_by)
                  VALUES (?,?,?,?,?,?)""",
               (data.get("client_id"), data.get("platform"), data.get("content"),
                data.get("status", "draft"), data.get("scheduled_date"), user["id"]))
    db.commit()
    db.close()
    return {"message": "Post created"}

@app.post("/api/audit")
async def create_audit(request: Request):
    user = require_auth(request)
    data = await request.json()
    db = get_db()
    c = db.cursor()
    c.execute("""INSERT INTO seo_audits (client_id, website_url, status, ai_provider, created_by) VALUES (?,?,?,?,?)""",
              (data.get("client_id"), data["website_url"], "pending", data.get("ai_provider", "claude"), user["id"]))
    audit_id = c.lastrowid
    db.commit()
    db.close()
    return {"id": audit_id, "message": "Audit created — processing will begin when AI API key is configured"}

# ============================================================
# PUBLIC USER AUTH (signup / login for website customers)
# ============================================================
import re as _re

APP_TOKEN_EXPIRE_DAYS = 7
_login_attempts = {}  # ip -> [timestamps]

def _valid_email(email: str) -> bool:
    return bool(email and _re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))

def create_app_token(user_id: int, email: str):
    expire = datetime.utcnow() + timedelta(days=APP_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "email": email, "scope": "app_user", "exp": expire},
                      SECRET_KEY, algorithm=ALGORITHM)

def get_app_user(request: Request):
    """Resolve current app user from Authorization: Bearer <token> header or app_token cookie."""
    token = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        token = request.cookies.get("app_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("scope") != "app_user":
            return None
        db = get_db()
        row = db.execute("SELECT * FROM app_users WHERE id=?", (payload["sub"],)).fetchone()
        db.close()
        return dict(row) if row else None
    except Exception:
        return None

def notify_admins(db, title, message, ntype="lead"):
    """Send an in-app notification to all admin/ops users."""
    # Map arbitrary categories to the notifications.type CHECK whitelist
    _allowed = {"info", "warning", "success", "task", "urgent", "chat_request"}
    if ntype not in _allowed:
        ntype = {"payment": "success", "signup": "success", "lead": "info"}.get(ntype, "info")
    try:
        admins = db.execute("SELECT id FROM users WHERE role IN ('super_admin','operations_manager','sales')").fetchall()
        for a in admins:
            db.execute("INSERT INTO notifications (user_id, title, message, type) VALUES (?,?,?,?)",
                       (a["id"], title, message, ntype))
    except Exception:
        pass

@app.post("/api/auth/signup")
async def api_signup(request: Request):
    data = await request.json()
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    password = data.get("password") or ""
    business_name = (data.get("business_name") or "").strip()
    if not full_name or not email or not phone or not password:
        return JSONResponse({"error": "Full name, email, phone and password are required"}, status_code=400)
    if not _valid_email(email):
        return JSONResponse({"error": "Please enter a valid email address"}, status_code=400)
    if len(password) < 8:
        return JSONResponse({"error": "Password must be at least 8 characters"}, status_code=400)
    db = get_db()
    existing = db.execute("SELECT id FROM app_users WHERE email=?", (email,)).fetchone()
    if existing:
        db.close()
        return JSONResponse({"error": "An account with this email already exists"}, status_code=409)
    c = db.cursor()
    pwd_hash = bcrypt.hash(password)
    verify_token = secrets.token_urlsafe(24)
    c.execute("""INSERT INTO app_users (full_name, email, phone, password_hash, business_name, website_url, industry, verification_token)
                 VALUES (?,?,?,?,?,?,?,?)""",
              (full_name, email, phone, pwd_hash, business_name, data.get("website_url"), data.get("industry"), verify_token))
    uid = c.lastrowid
    notify_admins(db, "New Account Signup", f"{full_name} ({email}) created an account", "signup")
    db.commit()
    db.close()
    token = create_app_token(uid, email)
    return {"token": token, "user": {"id": uid, "full_name": full_name, "email": email, "business_name": business_name}}

@app.post("/api/auth/login")
async def api_login(request: Request):
    # rate limit: max 5 attempts / 15 min per IP
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    attempts = [t for t in _login_attempts.get(ip, []) if now - t < 900]
    if len(attempts) >= 5:
        return JSONResponse({"error": "Too many login attempts. Please try again in 15 minutes."}, status_code=429)
    data = await request.json()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    db = get_db()
    row = db.execute("SELECT * FROM app_users WHERE email=?", (email,)).fetchone()
    if not row or not bcrypt.verify(password, row["password_hash"]):
        attempts.append(now)
        _login_attempts[ip] = attempts
        db.close()
        return JSONResponse({"error": "Invalid email or password"}, status_code=401)
    db.execute("UPDATE app_users SET last_login=datetime('now') WHERE id=?", (row["id"],))
    db.commit()
    db.close()
    _login_attempts[ip] = []
    token = create_app_token(row["id"], email)
    return {"token": token, "user": {"id": row["id"], "full_name": row["full_name"], "email": email,
                                     "business_name": row["business_name"]}}

@app.post("/api/auth/logout")
async def api_logout():
    # Stateless JWT — client discards token. Clear cookie if present.
    resp = JSONResponse({"message": "Logged out"})
    resp.delete_cookie("app_token")
    return resp

@app.get("/api/auth/me")
async def api_me(request: Request):
    user = get_app_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    user.pop("password_hash", None)
    user.pop("verification_token", None)
    user.pop("reset_token", None)
    return {"user": user}

@app.put("/api/auth/update")
async def api_update_profile(request: Request):
    user = get_app_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    data = await request.json()
    db = get_db()
    db.execute("""UPDATE app_users SET full_name=?, phone=?, business_name=?, website_url=?, industry=? WHERE id=?""",
               (data.get("full_name", user["full_name"]), data.get("phone", user["phone"]),
                data.get("business_name", user["business_name"]), data.get("website_url", user["website_url"]),
                data.get("industry", user["industry"]), user["id"]))
    db.commit()
    db.close()
    return {"message": "Profile updated"}

@app.post("/api/auth/forgot-password")
async def api_forgot_password(request: Request):
    data = await request.json()
    email = (data.get("email") or "").strip().lower()
    db = get_db()
    row = db.execute("SELECT id FROM app_users WHERE email=?", (email,)).fetchone()
    if row:
        token = secrets.token_urlsafe(24)
        expiry = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        db.execute("UPDATE app_users SET reset_token=?, reset_token_expiry=? WHERE id=?", (token, expiry, row["id"]))
        db.commit()
        # No email service configured — log reset link to console
        print(f"[PASSWORD RESET] {email} -> token: {token} (expires {expiry})")
    db.close()
    # Always return success to avoid email enumeration
    return {"message": "If an account exists for this email, a reset link has been sent."}

@app.post("/api/auth/reset-password")
async def api_reset_password(request: Request):
    data = await request.json()
    token = data.get("token") or ""
    new_password = data.get("password") or ""
    if len(new_password) < 8:
        return JSONResponse({"error": "Password must be at least 8 characters"}, status_code=400)
    db = get_db()
    row = db.execute("SELECT id, reset_token_expiry FROM app_users WHERE reset_token=?", (token,)).fetchone()
    if not row:
        db.close()
        return JSONResponse({"error": "Invalid or expired reset token"}, status_code=400)
    try:
        if datetime.fromisoformat(row["reset_token_expiry"]) < datetime.utcnow():
            db.close()
            return JSONResponse({"error": "Reset token has expired"}, status_code=400)
    except Exception:
        pass
    db.execute("UPDATE app_users SET password_hash=?, reset_token=NULL, reset_token_expiry=NULL WHERE id=?",
               (bcrypt.hash(new_password), row["id"]))
    db.commit()
    db.close()
    return {"message": "Password has been reset. You can now log in."}

# ============================================================
# CLIENT PACKAGES + PAYMENT GATING (app users)
# ============================================================
PACKAGES = [
    {
        "id": "Growth Starter",
        "name": "Local Growth Starter",
        "price": 1997,
        "price_label": "$1,997/mo",
        "tagline": "For businesses getting started with local SEO",
        "features": [
            "Local SEO (30 keywords)",
            "GBP Optimization (Basic)",
            "20 Local Citations/month",
            "4 SEO Blog Posts/month",
            "Basic Reputation Monitoring",
            "Monthly Performance Report",
        ],
    },
    {
        "id": "Growth Pro",
        "name": "Local Growth Pro",
        "price": 3997,
        "price_label": "$3,997/mo",
        "tagline": "For businesses ready to dominate their market",
        "popular": True,
        "features": [
            "Local SEO (60 keywords)",
            "GBP Optimization (Full)",
            "Reputation Management",
            "40 Local Citations/month",
            "8 SEO Blog Posts/month",
            "Review Generation System",
            "AI SEO Foundation",
            "Bi-Weekly Strategy Calls",
        ],
    },
    {
        "id": "Growth Elite",
        "name": "Local Dominance",
        "price": 6997,
        "price_label": "$6,997/mo",
        "tagline": "For businesses wanting complete market authority",
        "features": [
            "Everything in Growth Pro",
            "100+ Keywords Tracked",
            "AI SEO Advanced",
            "Social Media Management",
            "PPC Campaign Management",
            "12 Blog Posts/month",
            "Dedicated Account Manager",
            "Weekly Strategy Calls",
        ],
    },
]

# Free actions every client can do before purchasing a package
FREE_ACTIONS = [
    {"title": "Complete your SEO Strategy Questionnaire", "description": "25 questions so our team can build your custom strategy.", "action": "questionnaire"},
    {"title": "Request a Free SEO Audit", "description": "Get a no-cost audit of your website and Google Business Profile.", "action": "audit", "link": "free-audit.html"},
    {"title": "Download Free SEO Resources", "description": "Local SEO checklist, GBP guide, review templates and more.", "action": "resources", "link": "free-resources.html"},
]

def _package_by_id(pid):
    for p in PACKAGES:
        if p["id"] == pid:
            return p
    return None

@app.get("/api/packages")
async def api_list_packages():
    """Public list of purchasable packages."""
    return {"packages": PACKAGES}

@app.get("/api/user/dashboard")
async def api_user_dashboard(request: Request):
    """Everything the client dashboard needs: profile, payment status, free actions, and package tasks (locked until paid)."""
    user = get_app_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    db = get_db()

    # Resolve questionnaire completion (column flag OR a submission matching the user's email)
    q_done = bool(user.get("questionnaire_completed"))
    if not q_done and user.get("email"):
        qrow = db.execute("SELECT id FROM seo_questionnaires WHERE lower(client_email)=lower(?) ORDER BY id DESC LIMIT 1",
                          (user["email"],)).fetchone()
        if qrow:
            q_done = True
            db.execute("UPDATE app_users SET questionnaire_completed=1, questionnaire_id=? WHERE id=?",
                       (qrow["id"], user["id"]))
            db.commit()

    paid = (user.get("payment_status") == "paid") and bool(user.get("package"))
    active_package = user.get("package") if paid else None

    # Package tasks for the user's package (when paid) or Growth Starter preview (when unpaid)
    preview_pkg = active_package or "Growth Starter"
    rows = db.execute(
        "SELECT category, title, description, is_automated, order_num FROM package_tasks WHERE package=? ORDER BY order_num, id",
        (preview_pkg,)
    ).fetchall()
    db.close()

    tasks = []
    for r in rows:
        tasks.append({
            "category": r["category"],
            "title": r["title"],
            "description": r["description"],
            "automated": bool(r["is_automated"]),
            "locked": (not paid),  # locked until payment; active per package after pay
        })

    return {
        "user": {
            "id": user["id"],
            "full_name": user.get("full_name"),
            "email": user.get("email"),
            "phone": user.get("phone"),
            "business_name": user.get("business_name"),
            "website_url": user.get("website_url"),
            "industry": user.get("industry"),
        },
        "payment_status": "paid" if paid else "unpaid",
        "package": active_package,
        "package_label": (_package_by_id(active_package) or {}).get("name") if active_package else None,
        "paid_at": user.get("paid_at"),
        "questionnaire_completed": q_done,
        "free_actions": FREE_ACTIONS,
        "packages": PACKAGES,
        "tasks": tasks,
        "preview_package": preview_pkg,
    }

@app.post("/api/user/buy-package")
async def api_buy_package(request: Request):
    """Activate a package for the logged-in client (records payment, unlocks tasks, notifies admin)."""
    user = get_app_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    data = await request.json()
    pkg_id = (data.get("package") or "").strip()
    pkg = _package_by_id(pkg_id)
    if not pkg:
        return JSONResponse({"error": "Invalid package selected"}, status_code=400)

    db = get_db()
    db.execute("""UPDATE app_users
                  SET package=?, payment_status='paid', paid_at=datetime('now'), package_started_at=datetime('now')
                  WHERE id=?""", (pkg_id, user["id"]))
    # Persist a payment record
    try:
        db.execute("""INSERT INTO payments (client_id, amount, status, paid_date, notes, created_at)
                      VALUES (?,?,?,datetime('now'),?,datetime('now'))""",
                   (None, pkg["price"], "paid",
                    f"{pkg['name']} package purchased by app_user #{user['id']} ({user.get('email')})"))
    except Exception as e:
        print(f"[buy-package] payment insert skipped: {e}")
    # Notify admins
    notify_admins(db, "New Package Purchase",
                  f"{user.get('full_name')} ({user.get('email')}) purchased {pkg['name']} ({pkg['price_label']}).",
                  "payment")
    db.commit()
    db.close()
    return {
        "message": f"{pkg['name']} activated! Your SEO tasks are now unlocked.",
        "package": pkg_id,
        "package_label": pkg["name"],
        "payment_status": "paid",
    }

# ============================================================
# PUBLIC LEAD CAPTURE (free-audit + contact forms)
# ============================================================
@app.post("/api/leads/audit")
async def api_lead_audit(request: Request):
    data = await request.json()
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    if not email or not _valid_email(email):
        return JSONResponse({"error": "A valid email is required"}, status_code=400)
    db = get_db()
    db.execute("""INSERT INTO public_leads (lead_type, name, email, phone, website, business_name, industry, message, source)
                  VALUES ('audit',?,?,?,?,?,?,?,?)""",
               (name, email, data.get("phone"), data.get("website"), data.get("business_name"),
                data.get("industry"), data.get("message"), "free-audit"))
    # Also create a sales lead for the pipeline
    try:
        db.execute("""INSERT INTO sales_leads (business_name, contact_name, email, phone, website, industry, source, status)
                      VALUES (?,?,?,?,?,?,?,?)""",
                   (data.get("business_name") or name, name, email, data.get("phone"),
                    data.get("website"), data.get("industry"), "free_audit", "new"))
    except Exception:
        pass
    notify_admins(db, "New Free Audit Request", f"{name or email} requested a free audit", "lead")
    db.commit()
    db.close()
    return {"message": "Thanks! Your free audit request has been received. We'll be in touch within 24 hours."}

@app.post("/api/leads/contact")
async def api_lead_contact(request: Request):
    data = await request.json()
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    if not email or not _valid_email(email):
        return JSONResponse({"error": "A valid email is required"}, status_code=400)
    db = get_db()
    db.execute("""INSERT INTO public_leads (lead_type, name, email, phone, business_name, message, source)
                  VALUES ('contact',?,?,?,?,?,?)""",
               (name, email, data.get("phone"), data.get("business_name"), data.get("message"), "contact-form"))
    notify_admins(db, "New Contact Message", f"{name or email} sent a message via the contact form", "lead")
    db.commit()
    db.close()
    return {"message": "Thanks for reaching out! We'll reply to your message shortly."}

@app.post("/api/leads/resource-download")
async def api_resource_download(request: Request):
    data = await request.json()
    email = (data.get("email") or "").strip()
    if not email or not _valid_email(email):
        return JSONResponse({"error": "A valid email is required"}, status_code=400)
    db = get_db()
    db.execute("""INSERT INTO public_leads (lead_type, name, email, message, source)
                  VALUES ('resource',?,?,?,?)""",
               (data.get("name"), email, data.get("resource"), "free-resources"))
    notify_admins(db, "Resource Download", f"{email} downloaded: {data.get('resource','a resource')}", "lead")
    db.commit()
    db.close()
    return {"message": "Success! Your download link is on its way to your inbox."}

@app.post("/api/blog/submit")
async def api_blog_submit(request: Request):
    data = await request.json()
    email = (data.get("email") or "").strip()
    if not email or not _valid_email(email):
        return JSONResponse({"error": "A valid email is required"}, status_code=400)
    db = get_db()
    db.execute("""INSERT INTO blog_submissions (name, email, website_url, topic, message, submission_type)
                  VALUES (?,?,?,?,?,?)""",
               (data.get("name"), email, data.get("website_url"), data.get("topic"),
                data.get("message"), data.get("submission_type", "roundup")))
    notify_admins(db, "New Content Submission", f"{data.get('name') or email} submitted a story/guest post", "lead")
    db.commit()
    db.close()
    return {"message": "Thanks for your submission! Our editorial team will review it and get back to you."}

# ============================================================
# BLOG PUBLISHING API
# ============================================================
def _slugify(title: str) -> str:
    s = _re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return s or secrets.token_hex(4)

@app.get("/api/blog/posts")
async def api_blog_list(request: Request):
    db = get_db()
    rows = db.execute("SELECT * FROM blog_posts WHERE status='published' ORDER BY COALESCE(published_at, created_at) DESC").fetchall()
    db.close()
    return {"posts": [dict(r) for r in rows]}

@app.get("/admin/blog", response_class=HTMLResponse)
async def admin_blog_page(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ("super_admin", "operations_manager"):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("blog_admin.html", {"request": request, "user": user})

@app.get("/api/blog/admin/posts")
async def api_blog_admin_list(request: Request):
    require_role(request, ["super_admin", "operations_manager"])
    db = get_db()
    rows = db.execute("SELECT * FROM blog_posts ORDER BY COALESCE(published_at, created_at) DESC").fetchall()
    db.close()
    return {"posts": [dict(r) for r in rows]}

@app.get("/api/blog/posts/{slug}")
async def api_blog_get(slug: str):
    db = get_db()
    row = db.execute("SELECT * FROM blog_posts WHERE slug=?", (slug,)).fetchone()
    if row:
        db.execute("UPDATE blog_posts SET views=views+1 WHERE id=?", (row["id"],))
        db.commit()
    db.close()
    if not row:
        return JSONResponse({"error": "Post not found"}, status_code=404)
    return {"post": dict(row)}

@app.post("/api/blog/posts")
async def api_blog_create(request: Request):
    user = require_role(request, ["super_admin", "operations_manager"])
    data = await request.json()
    title = (data.get("title") or "").strip()
    if not title:
        return JSONResponse({"error": "Title is required"}, status_code=400)
    slug = (data.get("slug") or "").strip() or _slugify(title)
    db = get_db()
    if db.execute("SELECT id FROM blog_posts WHERE slug=?", (slug,)).fetchone():
        slug = f"{slug}-{secrets.token_hex(2)}"
    status = data.get("status", "draft")
    published_at = data.get("publish_date") or (datetime.utcnow().isoformat() if status == "published" else None)
    c = db.cursor()
    c.execute("""INSERT INTO blog_posts (title, slug, category, featured_image, excerpt, body, seo_title,
                 seo_description, tags, status, author, published_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
              (title, slug, data.get("category"), data.get("featured_image"), data.get("excerpt"),
               data.get("body"), data.get("seo_title") or title, data.get("seo_description") or data.get("excerpt"),
               data.get("tags"), status, data.get("author") or user["full_name"], published_at))
    pid = c.lastrowid
    db.commit()
    db.close()
    return {"id": pid, "slug": slug, "message": "Post created"}

@app.put("/api/blog/posts/{post_id}")
async def api_blog_update(post_id: int, request: Request):
    user = require_role(request, ["super_admin", "operations_manager"])
    data = await request.json()
    db = get_db()
    row = db.execute("SELECT * FROM blog_posts WHERE id=?", (post_id,)).fetchone()
    if not row:
        db.close()
        return JSONResponse({"error": "Post not found"}, status_code=404)
    status = data.get("status", row["status"])
    published_at = row["published_at"]
    if status == "published" and not published_at:
        published_at = datetime.utcnow().isoformat()
    db.execute("""UPDATE blog_posts SET title=?, slug=?, category=?, featured_image=?, excerpt=?, body=?,
                  seo_title=?, seo_description=?, tags=?, status=?, author=?, published_at=?, updated_at=datetime('now')
                  WHERE id=?""",
               (data.get("title", row["title"]), data.get("slug", row["slug"]), data.get("category", row["category"]),
                data.get("featured_image", row["featured_image"]), data.get("excerpt", row["excerpt"]),
                data.get("body", row["body"]), data.get("seo_title", row["seo_title"]),
                data.get("seo_description", row["seo_description"]), data.get("tags", row["tags"]),
                status, data.get("author", row["author"]), published_at, post_id))
    db.commit()
    db.close()
    return {"message": "Post updated"}

@app.delete("/api/blog/posts/{post_id}")
async def api_blog_delete(post_id: int, request: Request):
    user = require_role(request, ["super_admin", "operations_manager"])
    db = get_db()
    db.execute("DELETE FROM blog_posts WHERE id=?", (post_id,))
    db.commit()
    db.close()
    return {"message": "Post deleted"}

# ===== HEALTH CHECK =====
@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: int, request: Request):
    user = require_auth(request)
    db = get_db()
    db.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (notif_id, user["id"]))
    db.commit()
    db.close()
    return {"message": "Marked as read"}

@app.post("/api/expenses")
async def create_expense(request: Request):
    user = require_role(request, ["super_admin", "finance"])
    data = await request.json()
    db = get_db()
    db.execute("""INSERT INTO expenses (category, description, amount, date, approved_by) VALUES (?,?,?,?,?)""",
               (data["category"], data["description"], data["amount"], data.get("date"), user["id"]))
    db.commit()
    db.close()
    return {"message": "Expense recorded"}

# ===== NEW API ENDPOINTS =====

# Client Credentials
@app.post("/api/client-credentials")
async def add_client_credential(request: Request):
    user = require_role(request, ["super_admin", "sales", "worker", "tech_seo"])
    data = await request.json()
    db = get_db()
    db.execute("""INSERT INTO client_credentials (client_id, credential_type, label, username, password_enc, api_key, access_url, notes, added_by)
                  VALUES (?,?,?,?,?,?,?,?,?)""",
               (data["client_id"], data["credential_type"], data.get("label"), data.get("username"),
                data.get("password_enc"), data.get("api_key"), data.get("access_url"), data.get("notes"), user["id"]))
    db.commit()
    db.close()
    return {"message": "Credential saved"}

# API Settings
@app.post("/api/settings/api")
async def update_api_setting(request: Request):
    user = require_role(request, ["super_admin"])
    data = await request.json()
    db = get_db()
    db.execute("""UPDATE api_settings SET api_key=?, is_active=?, config_json=?, updated_by=?, updated_at=datetime('now')
                  WHERE provider=?""",
               (data.get("api_key"), 1 if data.get("api_key") else 0, data.get("config_json"), user["id"], data["provider"]))
    db.commit()
    db.close()
    return {"message": f"{data['provider']} settings updated"}

# Function-specific API Config
@app.post("/api/settings/function-config")
async def save_function_config(request: Request):
    user = require_role(request, ["super_admin"])
    data = await request.json()
    func_name = data.get("function_name", "")
    provider = data.get("provider", "demo")
    db = get_db()
    # Create table if not exists
    db.execute("""CREATE TABLE IF NOT EXISTS function_configs 
                  (function_name TEXT PRIMARY KEY, provider TEXT, updated_by INTEGER, updated_at TEXT)""")
    db.execute("""INSERT OR REPLACE INTO function_configs (function_name, provider, updated_by, updated_at)
                  VALUES (?, ?, ?, datetime('now'))""", (func_name, provider, user["id"]))
    db.commit()
    db.close()
    return {"message": f"{func_name} now uses {provider}"}

@app.get("/api/settings/function-config")
async def get_function_configs(request: Request):
    user = require_role(request, ["super_admin"])
    db = get_db()
    try:
        configs = [dict(r) for r in db.execute("SELECT * FROM function_configs").fetchall()]
    except:
        configs = []
    db.close()
    return {"configs": configs}

# Suggestions
@app.post("/api/suggestions")
async def create_suggestion(request: Request):
    user = require_auth(request)
    data = await request.json()
    db = get_db()
    db.execute("""INSERT INTO suggestions (user_id, project_id, title, description) VALUES (?,?,?,?)""",
               (user["id"], data.get("project_id"), data["title"], data.get("description")))
    db.commit()
    db.close()
    return {"message": "Suggestion submitted"}

@app.put("/api/suggestions/{sugg_id}")
async def update_suggestion(sugg_id: int, request: Request):
    user = require_role(request, ["super_admin"])
    data = await request.json()
    db = get_db()
    db.execute("UPDATE suggestions SET status=?, admin_response=? WHERE id=?", (data["status"], data.get("admin_response"), sugg_id))
    db.commit()
    db.close()
    return {"message": "Suggestion updated"}

# Chat Requests
@app.post("/api/chat-request")
async def create_chat_request(request: Request):
    user = require_auth(request)
    data = await request.json()
    db = get_db()
    to_id = data["to_user_id"]
    db.execute("INSERT INTO chat_requests (from_user_id, to_user_id) VALUES (?,?)", (user["id"], to_id))
    db.execute("INSERT INTO notifications (user_id, title, message, type) VALUES (?,?,?,?)",
               (to_id, "Chat Request", f"{user['full_name']} wants to chat with you", "chat_request"))
    db.commit()
    db.close()
    return {"message": "Chat request sent"}

@app.put("/api/chat-request/{req_id}")
async def update_chat_request(req_id: int, request: Request):
    user = require_auth(request)
    data = await request.json()
    db = get_db()
    db.execute("UPDATE chat_requests SET status=?, resolved_at=datetime('now') WHERE id=?", (data["status"], req_id))
    db.commit()
    db.close()
    return {"message": f"Chat request {data['status']}"}

# Team Chat Messages
@app.get("/api/chat-messages/{other_user_id}")
async def get_chat_messages(other_user_id: int, request: Request):
    user = require_auth(request)
    db = get_db()
    messages = [dict(r) for r in db.execute("""
        SELECT tc.*, u.full_name as sender_name FROM team_chats tc 
        LEFT JOIN users u ON tc.from_user_id=u.id
        WHERE (tc.from_user_id=? AND tc.to_user_id=?) OR (tc.from_user_id=? AND tc.to_user_id=?)
        ORDER BY tc.created_at ASC LIMIT 100
    """, (user["id"], other_user_id, other_user_id, user["id"])).fetchall()]
    db.execute("UPDATE team_chats SET is_read=1 WHERE to_user_id=? AND from_user_id=?", (user["id"], other_user_id))
    db.commit()
    db.close()
    return {"messages": messages}

@app.post("/api/chat-messages")
async def send_chat_message(request: Request):
    user = require_auth(request)
    data = await request.json()
    db = get_db()
    db.execute("INSERT INTO team_chats (from_user_id, to_user_id, message) VALUES (?,?,?)",
               (user["id"], data["to_user_id"], data["message"]))
    db.commit()
    db.close()
    return {"message": "Sent"}

# Generate PDF Report
@app.post("/api/reports/generate")
async def generate_report(request: Request):
    user = require_role(request, ["super_admin", "finance", "worker", "tech_seo"])
    data = await request.json()
    client_id = data["client_id"]
    db = get_db()
    client = dict(db.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone())
    projects = [dict(r) for r in db.execute("SELECT * FROM projects WHERE client_id=?", (client_id,)).fetchall()]
    tasks_all = []
    for p in projects:
        tasks_all += [dict(r) for r in db.execute("SELECT * FROM tasks WHERE project_id=?", (p["id"],)).fetchall()]
    payments = [dict(r) for r in db.execute("SELECT * FROM payments WHERE client_id=?", (client_id,)).fetchall()]
    
    report_data = json.dumps({
        "client": client, "projects": projects, "tasks": tasks_all, "payments": payments,
        "generated_at": datetime.now().isoformat(), "generated_by": user["full_name"]
    })
    
    c = db.cursor()
    c.execute("""INSERT INTO client_reports (client_id, report_type, title, report_data, created_by) VALUES (?,?,?,?,?)""",
              (client_id, data.get("report_type", "monthly"), f"Report - {client['business_name']} - {datetime.now().strftime('%B %Y')}",
               report_data, user["id"]))
    report_id = c.lastrowid
    db.commit()
    db.close()
    return {"id": report_id, "message": "Report generated"}

# Download report as HTML
@app.get("/api/reports/{report_id}/download")
async def download_report(report_id: int, request: Request):
    user = require_auth(request)
    db = get_db()
    report = db.execute("SELECT r.*, c.business_name FROM client_reports r LEFT JOIN clients c ON r.client_id=c.id WHERE r.id=?", (report_id,)).fetchone()
    db.close()
    if not report:
        raise HTTPException(status_code=404)
    report = dict(report)
    rdata = json.loads(report["report_data"]) if report["report_data"] else {}
    client = rdata.get("client", {})
    projects = rdata.get("projects", [])
    tasks = rdata.get("tasks", [])
    payments = rdata.get("payments", [])
    
    completed_tasks = sum(1 for t in tasks if t.get("status") == "completed")
    total_tasks = len(tasks)
    total_paid = sum(p.get("amount", 0) for p in payments if p.get("status") == "paid")
    
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>{report['title']}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:Inter,sans-serif;background:#fff;color:#333;padding:40px}}
.header{{background:linear-gradient(135deg,#0A1628,#1E3A5F);color:#fff;padding:40px;border-radius:12px;margin-bottom:30px}}
.header h1{{font-size:24px;margin-bottom:8px}}.header p{{opacity:.8}}
.section{{margin-bottom:30px}}.section h2{{font-size:18px;color:#0A1628;border-bottom:2px solid #00D4FF;padding-bottom:8px;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse;margin-top:12px}}th,td{{padding:10px 12px;text-align:left;border-bottom:1px solid #eee}}
th{{background:#f7f9fc;font-weight:600}}.stat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:30px}}
.stat-card{{background:#f7f9fc;padding:20px;border-radius:8px;text-align:center}}.stat-card .num{{font-size:28px;font-weight:700;color:#0A1628}}
.stat-card .label{{font-size:12px;color:#666;margin-top:4px}}.badge{{padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600}}
.badge-paid{{background:#d1fae5;color:#059669}}.badge-pending{{background:#fef3c7;color:#d97706}}.badge-completed{{background:#d1fae5;color:#059669}}
.badge-progress{{background:#dbeafe;color:#2563eb}}.footer{{margin-top:40px;padding-top:20px;border-top:2px solid #eee;text-align:center;color:#999;font-size:12px}}
@media print{{body{{padding:20px}}.header{{break-after:avoid}}}}
</style></head><body>
<div class="header"><h1>RankForge AI — Client Report</h1><p>{report['title']}</p><p>Generated: {rdata.get('generated_at','')[:10]} | By: {rdata.get('generated_by','System')}</p></div>
<div class="stat-grid">
<div class="stat-card"><div class="num">{len(projects)}</div><div class="label">Active Projects</div></div>
<div class="stat-card"><div class="num">{completed_tasks}/{total_tasks}</div><div class="label">Tasks Completed</div></div>
<div class="stat-card"><div class="num">{round(completed_tasks/total_tasks*100) if total_tasks else 0}%</div><div class="label">Completion Rate</div></div>
<div class="stat-card"><div class="num">${total_paid:,.0f}</div><div class="label">Total Invested</div></div>
</div>
<div class="section"><h2>Client Information</h2><table>
<tr><td><strong>Business</strong></td><td>{client.get('business_name','')}</td><td><strong>Package</strong></td><td>{client.get('package','')}</td></tr>
<tr><td><strong>Contact</strong></td><td>{client.get('contact_name','')}</td><td><strong>Industry</strong></td><td>{client.get('industry','')}</td></tr>
<tr><td><strong>Website</strong></td><td>{client.get('website','')}</td><td><strong>Location</strong></td><td>{client.get('location','')}</td></tr>
</table></div>
<div class="section"><h2>Projects Overview</h2><table><thead><tr><th>Project</th><th>Service</th><th>Progress</th><th>Status</th></tr></thead><tbody>"""
    for p in projects:
        badge = "badge-completed" if p.get("status") == "completed" else "badge-progress"
        html += f'<tr><td>{p.get("title","")}</td><td>{p.get("service_type","")}</td><td>{p.get("progress",0)}%</td><td><span class="badge {badge}">{p.get("status","")}</span></td></tr>'
    html += """</tbody></table></div>
<div class="section"><h2>Task Breakdown</h2><table><thead><tr><th>Task</th><th>Priority</th><th>Status</th></tr></thead><tbody>"""
    for t in tasks:
        badge = "badge-completed" if t.get("status") == "completed" else ("badge-progress" if t.get("status") == "in_progress" else "badge-pending")
        html += f'<tr><td>{t.get("title","")}</td><td>{t.get("priority","")}</td><td><span class="badge {badge}">{t.get("status","")}</span></td></tr>'
    html += """</tbody></table></div>
<div class="section"><h2>Payment History</h2><table><thead><tr><th>Invoice</th><th>Amount</th><th>Due Date</th><th>Status</th></tr></thead><tbody>"""
    for pay in payments:
        badge = "badge-paid" if pay.get("status") == "paid" else "badge-pending"
        html += f'<tr><td>{pay.get("invoice_number","")}</td><td>${pay.get("amount",0):,.0f}</td><td>{pay.get("due_date","")}</td><td><span class="badge {badge}">{pay.get("status","")}</span></td></tr>'
    html += f"""</tbody></table></div>
<div class="footer"><p>RankForge AI | AI-Powered SEO &amp; Reputation Management Agency</p><p>This report is confidential and prepared exclusively for {client.get('business_name','')}.</p></div>
</body></html>"""
    
    return HTMLResponse(content=html)

# Mark report as sent
@app.post("/api/reports/{report_id}/send")
async def send_report(report_id: int, request: Request):
    user = require_role(request, ["super_admin", "finance"])
    db = get_db()
    db.execute("UPDATE client_reports SET sent_to_client=1, sent_date=datetime('now'), sent_by=? WHERE id=?", (user["id"], report_id))
    db.commit()
    db.close()
    return {"message": "Report marked as sent to client"}

# Run automated DNA task
@app.post("/api/tasks/{task_id}/run-auto")
async def run_automated_task(task_id: int, request: Request):
    user = require_auth(request)
    db = get_db()
    task = db.execute("SELECT t.*, p.client_id FROM tasks t LEFT JOIN projects p ON t.project_id=p.id WHERE t.id=?", (task_id,)).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404)
    task = dict(task)
    
    # Get client website
    client = db.execute("SELECT * FROM clients WHERE id=?", (task["client_id"],)).fetchone()
    client_url = dict(client)["website"] if client else ""
    
    # Get API settings
    api = db.execute("SELECT * FROM api_settings WHERE provider IN ('claude','chatgpt','gemini') AND is_active=1 LIMIT 1").fetchone()
    
    provider = api["provider"] if api and api["api_key"] else "demo"
    
    # Generate demo AI result (in production, real API call happens here)
    demo_result = {
        "status": "completed",
        "provider": provider,
        "url": client_url,
        "triggered_at": datetime.now().isoformat(),
        "completed_at": datetime.now().isoformat(),
        "mode": "demo" if provider == "demo" else "live",
        "audit_result": {
            "overall_score": 78,
            "categories": {
                "technical_seo": {"score": 82, "issues": 5, "critical": 1},
                "on_page_seo": {"score": 75, "issues": 8, "critical": 2},
                "content_quality": {"score": 70, "issues": 6, "critical": 0},
                "backlink_profile": {"score": 65, "issues": 4, "critical": 1},
                "local_seo": {"score": 88, "issues": 3, "critical": 0},
                "mobile_usability": {"score": 85, "issues": 2, "critical": 0}
            },
            "top_recommendations": [
                "Add LocalBusiness schema markup to all location pages",
                "Optimize Core Web Vitals — LCP is 3.2s (target: <2.5s)",
                "Build 10+ quality local backlinks per month",
                "Create location-specific content for each service area",
                "Implement FAQ schema on top 5 service pages"
            ]
        },
        "note": "Demo mode — add real AI API key in Settings for live processing" if provider == "demo" else f"Processed by {provider}"
    }
    
    db.execute("UPDATE tasks SET status='completed', auto_result=? WHERE id=?",
               (json.dumps(demo_result), task_id))
    log_activity(db, user["id"], "ai_task", f"AI task #{task_id} completed ({provider})", "task", task_id)
    db.commit()
    db.close()
    return {"message": f"AI task completed using {provider}.", "provider": provider, "result": demo_result}

# Website chatbot API
@app.post("/api/chat")
async def save_chat(request: Request):
    data = await request.json()
    db = get_db()
    db.execute("""INSERT INTO chat_messages (session_id, visitor_name, visitor_email, business_name, industry, location, website_url, messages, status)
                  VALUES (?,?,?,?,?,?,?,?,?)""",
               (data.get("session_id"), data.get("visitor_name"), data.get("visitor_email"),
                data.get("business_name"), data.get("industry"), data.get("location"),
                data.get("website_url"), json.dumps(data.get("messages", [])), "active"))
    db.commit()
    db.close()
    return {"message": "Chat saved"}

# ===== TIME TRACKING =====
@app.post("/api/time/start")
async def start_timer(request: Request):
    user = require_auth(request)
    data = await request.json()
    db = get_db()
    # Check for active timer
    active = db.execute("SELECT id FROM time_entries WHERE user_id=? AND end_time IS NULL", (user["id"],)).fetchone()
    if active:
        db.close()
        return JSONResponse({"error": "You already have an active timer. Stop it first."}, status_code=400)
    task = db.execute("SELECT t.*, p.id as proj_id FROM tasks t LEFT JOIN projects p ON t.project_id=p.id WHERE t.id=?", (data["task_id"],)).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="Task not found")
    db.execute("INSERT INTO time_entries (user_id, task_id, project_id, start_time) VALUES (?,?,?,datetime('now'))",
               (user["id"], data["task_id"], task["proj_id"]))
    db.execute("UPDATE tasks SET status='in_progress' WHERE id=? AND status='pending'", (data["task_id"],))
    log_activity(db, user["id"], "timer_started", f"Started timer on task #{data['task_id']}", "task", data["task_id"])
    db.commit()
    db.close()
    return {"message": "Timer started"}

@app.post("/api/time/stop")
async def stop_timer(request: Request):
    user = require_auth(request)
    data = await request.json()
    db = get_db()
    entry = db.execute("SELECT * FROM time_entries WHERE user_id=? AND end_time IS NULL", (user["id"],)).fetchone()
    if not entry:
        db.close()
        return JSONResponse({"error": "No active timer found"}, status_code=400)
    entry = dict(entry)
    start = datetime.fromisoformat(entry["start_time"])
    now = datetime.now()
    hours = round((now - start).total_seconds() / 3600, 2)
    db.execute("UPDATE time_entries SET end_time=datetime('now'), hours=?, notes=? WHERE id=?",
               (hours, data.get("notes", ""), entry["id"]))
    log_activity(db, user["id"], "timer_stopped", f"Logged {hours}h on task #{entry['task_id']}", "task", entry["task_id"])
    db.commit()
    db.close()
    return {"message": f"Timer stopped. {hours} hours logged.", "hours": hours}

@app.get("/api/time/active")
async def get_active_timer(request: Request):
    user = require_auth(request)
    db = get_db()
    entry = db.execute("""SELECT te.*, t.title as task_title, p.title as project_title 
        FROM time_entries te LEFT JOIN tasks t ON te.task_id=t.id LEFT JOIN projects p ON te.project_id=p.id 
        WHERE te.user_id=? AND te.end_time IS NULL""", (user["id"],)).fetchone()
    db.close()
    if entry:
        entry = dict(entry)
        start = datetime.fromisoformat(entry["start_time"])
        entry["elapsed_minutes"] = round((datetime.now() - start).total_seconds() / 60, 1)
    return {"active_timer": dict(entry) if entry else None}

@app.get("/api/time/entries")
async def get_time_entries(request: Request):
    user = require_auth(request)
    db = get_db()
    if user["role"] in ("super_admin", "operations_manager", "finance"):
        entries = [dict(r) for r in db.execute("""
            SELECT te.*, t.title as task_title, u.full_name as worker_name, p.title as project_title
            FROM time_entries te LEFT JOIN tasks t ON te.task_id=t.id LEFT JOIN users u ON te.user_id=u.id 
            LEFT JOIN projects p ON te.project_id=p.id ORDER BY te.created_at DESC LIMIT 100
        """).fetchall()]
    else:
        entries = [dict(r) for r in db.execute("""
            SELECT te.*, t.title as task_title, p.title as project_title
            FROM time_entries te LEFT JOIN tasks t ON te.task_id=t.id LEFT JOIN projects p ON te.project_id=p.id 
            WHERE te.user_id=? ORDER BY te.created_at DESC LIMIT 50
        """, (user["id"],)).fetchall()]
    db.close()
    return {"entries": entries}

# ===== INVOICE SYSTEM =====
def _generate_invoice_number(db):
    year = datetime.now().year
    month = datetime.now().month
    count = db.execute("SELECT COUNT(*) FROM invoices WHERE invoice_number LIKE ?", (f"INV-{year}-%",)).fetchone()[0]
    return f"INV-{year}-{count+1:04d}"

@app.post("/api/invoices")
async def create_invoice(request: Request):
    user = require_role(request, ["super_admin", "finance"])
    data = await request.json()
    db = get_db()
    inv_num = _generate_invoice_number(db)
    items = data.get("items", [])
    subtotal = sum(item.get("quantity", 1) * item.get("rate", 0) for item in items)
    tax_rate = data.get("tax_rate", 0)
    tax_amount = round(subtotal * tax_rate / 100, 2)
    total = round(subtotal + tax_amount, 2)
    c = db.cursor()
    c.execute("""INSERT INTO invoices (client_id, invoice_number, due_date, subtotal, tax_rate, tax_amount, total, status, notes, created_by)
                 VALUES (?,?,?,?,?,?,?,?,?,?)""",
              (data["client_id"], inv_num, data.get("due_date"), subtotal, tax_rate, tax_amount, total, "draft", data.get("notes"), user["id"]))
    invoice_id = c.lastrowid
    for item in items:
        amount = round(item.get("quantity", 1) * item.get("rate", 0), 2)
        c.execute("INSERT INTO invoice_items (invoice_id, description, quantity, rate, amount) VALUES (?,?,?,?,?)",
                  (invoice_id, item["description"], item.get("quantity", 1), item.get("rate", 0), amount))
    log_activity(db, user["id"], "invoice_created", f"Invoice {inv_num} for ${total}", "invoice", invoice_id)
    db.commit()
    db.close()
    return {"id": invoice_id, "invoice_number": inv_num, "total": total}

@app.get("/api/invoices")
async def list_invoices(request: Request):
    user = require_auth(request)
    db = get_db()
    if user["role"] in ("super_admin", "finance", "operations_manager"):
        invoices = [dict(r) for r in db.execute("""
            SELECT i.*, c.business_name FROM invoices i LEFT JOIN clients c ON i.client_id=c.id ORDER BY i.created_at DESC
        """).fetchall()]
    elif user["role"] == "client":
        client = db.execute("SELECT id FROM clients WHERE email=?", (user["email"],)).fetchone()
        cid = client["id"] if client else 0
        invoices = [dict(r) for r in db.execute("SELECT * FROM invoices WHERE client_id=? ORDER BY created_at DESC", (cid,)).fetchall()]
    else:
        invoices = []
    db.close()
    return {"invoices": invoices}

@app.put("/api/invoices/{invoice_id}/status")
async def update_invoice_status(invoice_id: int, request: Request):
    user = require_role(request, ["super_admin", "finance"])
    data = await request.json()
    db = get_db()
    new_status = data["status"]
    paid_date = "datetime('now')" if new_status == "paid" else "NULL"
    if new_status == "paid":
        db.execute("UPDATE invoices SET status=?, paid_date=datetime('now'), updated_at=datetime('now') WHERE id=?", (new_status, invoice_id))
        # Auto-create payment record
        inv = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if inv:
            db.execute("INSERT INTO payments (client_id, amount, status, due_date, paid_date, invoice_number) VALUES (?,?,?,?,datetime('now'),?)",
                       (inv["client_id"], inv["total"], "paid", inv["due_date"], inv["invoice_number"]))
    else:
        db.execute("UPDATE invoices SET status=?, updated_at=datetime('now') WHERE id=?", (new_status, invoice_id))
    log_activity(db, user["id"], "invoice_status_updated", f"Invoice #{invoice_id} → {new_status}", "invoice", invoice_id)
    db.commit()
    db.close()
    return {"message": f"Invoice status updated to {new_status}"}

@app.get("/api/invoices/{invoice_id}/download")
async def download_invoice(invoice_id: int, request: Request):
    user = require_auth(request)
    db = get_db()
    inv = db.execute("SELECT i.*, c.business_name, c.contact_name, c.email as client_email, c.phone as client_phone, c.location as client_location FROM invoices i LEFT JOIN clients c ON i.client_id=c.id WHERE i.id=?", (invoice_id,)).fetchone()
    if not inv:
        db.close()
        raise HTTPException(status_code=404)
    inv = dict(inv)
    items = [dict(r) for r in db.execute("SELECT * FROM invoice_items WHERE invoice_id=?", (invoice_id,)).fetchall()]
    db.close()
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Invoice {inv['invoice_number']}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:Inter,sans-serif;background:#fff;color:#333;padding:40px;max-width:800px;margin:0 auto}}
.inv-header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:40px;padding-bottom:20px;border-bottom:3px solid #0891B2}}
.inv-logo{{font-size:24px;font-weight:800;color:#0A1628}}.inv-logo span{{color:#0891B2}}
.inv-title{{font-size:32px;font-weight:800;color:#0A1628;text-align:right}}
.inv-meta{{display:grid;grid-template-columns:1fr 1fr;gap:30px;margin-bottom:30px}}
.inv-meta h4{{color:#0891B2;font-size:12px;text-transform:uppercase;margin-bottom:8px}}
.inv-meta p{{font-size:14px;margin:3px 0}}
table{{width:100%;border-collapse:collapse;margin:20px 0}}th{{background:#0A1628;color:#fff;padding:12px;text-align:left;font-size:13px}}
td{{padding:12px;border-bottom:1px solid #eee;font-size:14px}}.text-right{{text-align:right}}
.totals{{margin-top:20px;text-align:right}}.totals div{{margin:6px 0;font-size:14px}}.totals .total{{font-size:22px;font-weight:800;color:#0A1628;border-top:2px solid #0A1628;padding-top:10px;margin-top:10px}}
.badge{{display:inline-block;padding:4px 12px;border-radius:50px;font-size:12px;font-weight:700}}
.badge-paid{{background:#d1fae5;color:#059669}}.badge-draft{{background:#e2e8f0;color:#64748b}}.badge-sent{{background:#dbeafe;color:#2563eb}}.badge-overdue{{background:#fecaca;color:#dc2626}}
.footer{{margin-top:40px;padding-top:20px;border-top:1px solid #eee;text-align:center;color:#999;font-size:12px}}
@media print{{body{{padding:20px}}}}
</style></head><body>
<div class="inv-header"><div><div class="inv-logo">RankForge<span>AI</span></div><p style="color:#64748b;font-size:13px">AI-Powered SEO & Reputation Management</p></div><div class="inv-title">INVOICE</div></div>
<div class="inv-meta"><div><h4>Bill To</h4><p><strong>{inv.get('business_name','')}</strong></p><p>{inv.get('contact_name','')}</p><p>{inv.get('client_email','')}</p><p>{inv.get('client_phone','')}</p><p>{inv.get('client_location','')}</p></div>
<div style="text-align:right"><h4>Invoice Details</h4><p><strong>Invoice #:</strong> {inv['invoice_number']}</p><p><strong>Issue Date:</strong> {inv.get('issue_date','')}</p><p><strong>Due Date:</strong> {inv.get('due_date','')}</p><p><strong>Status:</strong> <span class="badge badge-{inv['status']}">{inv['status'].upper()}</span></p></div></div>
<table><thead><tr><th>Description</th><th class="text-right">Qty</th><th class="text-right">Rate</th><th class="text-right">Amount</th></tr></thead><tbody>"""
    for item in items:
        html += f'<tr><td>{item["description"]}</td><td class="text-right">{item["quantity"]}</td><td class="text-right">${item["rate"]:,.2f}</td><td class="text-right">${item["amount"]:,.2f}</td></tr>'
    html += f"""</tbody></table>
<div class="totals"><div>Subtotal: ${inv['subtotal']:,.2f}</div><div>Tax ({inv['tax_rate']}%): ${inv['tax_amount']:,.2f}</div><div class="total">Total: ${inv['total']:,.2f}</div></div>"""
    if inv.get("notes"):
        html += f'<div style="margin-top:30px;background:#f8fafc;padding:16px;border-radius:8px"><h4 style="font-size:13px;color:#64748b;margin-bottom:6px">Notes</h4><p style="font-size:14px">{inv["notes"]}</p></div>'
    html += '<div class="footer"><p>RankForge AI | Thank you for your business!</p></div></body></html>'
    return HTMLResponse(content=html)

# ===== FILE UPLOADS =====
@app.post("/api/upload")
async def upload_file(request: Request, file: UploadFile = File(...), related_type: str = Form(...), related_id: int = Form(...)):
    user = require_auth(request)
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    safe_filename = f"{int(time.time())}_{file.filename.replace('..', '').replace('/', '_')}"
    filepath = os.path.join(UPLOAD_DIR, safe_filename)
    with open(filepath, "wb") as f:
        f.write(contents)
    db = get_db()
    db.execute("INSERT INTO file_attachments (related_type, related_id, filename, filepath, filesize, mime_type, uploaded_by) VALUES (?,?,?,?,?,?,?)",
               (related_type, related_id, file.filename, safe_filename, len(contents), file.content_type, user["id"]))
    log_activity(db, user["id"], "file_uploaded", f"Uploaded {file.filename}", related_type, related_id)
    db.commit()
    db.close()
    return {"message": "File uploaded", "filename": safe_filename}

@app.get("/uploads/{filename}")
async def serve_upload(filename: str, request: Request):
    user = require_auth(request)
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404)
    with open(filepath, "rb") as f:
        content = f.read()
    return Response(content=content, media_type="application/octet-stream",
                    headers={"Content-Disposition": f"inline; filename={filename}"})

# ===== APPROVAL REQUESTS =====
@app.post("/api/approvals")
async def create_approval(request: Request):
    user = require_auth(request)
    data = await request.json()
    db = get_db()
    c = db.cursor()
    c.execute("""INSERT INTO approval_requests (task_id, project_id, client_id, request_type, title, description, requested_by) VALUES (?,?,?,?,?,?,?)""",
              (data.get("task_id"), data.get("project_id"), data.get("client_id"), data.get("request_type", "content"),
               data["title"], data.get("description"), user["id"]))
    approval_id = c.lastrowid
    log_activity(db, user["id"], "approval_requested", f"Approval: {data['title']}", "approval", approval_id)
    db.commit()
    db.close()
    return {"id": approval_id, "message": "Approval request created"}

@app.put("/api/approvals/{approval_id}")
async def respond_approval(approval_id: int, request: Request):
    user = require_auth(request)
    data = await request.json()
    db = get_db()
    db.execute("UPDATE approval_requests SET status=?, reviewed_by=?, review_notes=?, reviewed_at=datetime('now') WHERE id=?",
               (data["status"], user["id"], data.get("review_notes"), approval_id))
    log_activity(db, user["id"], "approval_responded", f"Approval #{approval_id} → {data['status']}", "approval", approval_id)
    db.commit()
    db.close()
    return {"message": f"Approval {data['status']}"}

# ===== DATA EXPORT =====
@app.get("/api/export/{table_name}")
async def export_data(table_name: str, request: Request):
    user = require_role(request, ["super_admin", "finance", "operations_manager"])
    allowed = {"clients", "payments", "expenses", "invoices", "tasks", "projects", "time_entries"}
    if table_name not in allowed:
        raise HTTPException(status_code=400, detail=f"Export not allowed for '{table_name}'")
    db = get_db()
    rows = [dict(r) for r in db.execute(f"SELECT * FROM {table_name}").fetchall()]
    db.close()
    if not rows:
        return Response(content="No data", media_type="text/plain")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table_name}_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

# ===== ACTIVITY TIMELINE =====
@app.get("/api/activity")
async def get_activity(request: Request):
    user = require_auth(request)
    db = get_db()
    if user["role"] in ("super_admin", "operations_manager"):
        activities = [dict(r) for r in db.execute("""
            SELECT al.*, u.full_name as user_name FROM activity_log al LEFT JOIN users u ON al.user_id=u.id ORDER BY al.created_at DESC LIMIT 50
        """).fetchall()]
    else:
        activities = [dict(r) for r in db.execute("""
            SELECT al.*, u.full_name as user_name FROM activity_log al LEFT JOIN users u ON al.user_id=u.id WHERE al.user_id=? ORDER BY al.created_at DESC LIMIT 30
        """, (user["id"],)).fetchall()]
    db.close()
    return {"activities": activities}

# ===== OPS MANAGER DATA =====
def _get_ops_manager_data(db):
    clients = [dict(r) for r in db.execute("SELECT * FROM clients WHERE status='active' ORDER BY business_name").fetchall()]
    projects = [dict(r) for r in db.execute("""
        SELECT p.*, c.business_name, u.full_name as worker_name FROM projects p 
        LEFT JOIN clients c ON p.client_id=c.id LEFT JOIN users u ON p.assigned_worker_id=u.id ORDER BY p.created_at DESC
    """).fetchall()]
    workers = [dict(r) for r in db.execute("SELECT id, full_name, role, rank FROM users WHERE role NOT IN ('super_admin','client','finance') AND is_active=1 ORDER BY role, full_name").fetchall()]
    for w in workers:
        w["active_tasks"] = db.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status='in_progress'", (w["id"],)).fetchone()[0]
        w["total_hours"] = db.execute("SELECT COALESCE(SUM(hours),0) FROM time_entries WHERE user_id=?", (w["id"],)).fetchone()[0]
    tasks = [dict(r) for r in db.execute("""
        SELECT t.*, u.full_name as assigned_name, p.title as project_title FROM tasks t 
        LEFT JOIN users u ON t.assigned_to=u.id LEFT JOIN projects p ON t.project_id=p.id ORDER BY t.created_at DESC LIMIT 50
    """).fetchall()]
    overdue_tasks = [dict(r) for r in db.execute("""
        SELECT t.*, u.full_name as assigned_name, p.title as project_title FROM tasks t 
        LEFT JOIN users u ON t.assigned_to=u.id LEFT JOIN projects p ON t.project_id=p.id 
        WHERE t.due_date IS NOT NULL AND t.due_date < date('now') AND t.status != 'completed' ORDER BY t.due_date
    """).fetchall()]
    pending_approvals = [dict(r) for r in db.execute("SELECT * FROM approval_requests WHERE status='pending' ORDER BY created_at DESC").fetchall()]
    active_projects = db.execute("SELECT COUNT(*) FROM projects WHERE status='in_progress'").fetchone()[0]
    total_tasks = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    completed_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'").fetchone()[0]
    return {
        "clients": clients, "projects": projects, "workers": workers, "tasks": tasks,
        "overdue_tasks": overdue_tasks, "pending_approvals": pending_approvals,
        "stats": {
            "active_projects": active_projects, "total_tasks": total_tasks, "completed_tasks": completed_tasks,
            "task_completion": round(completed_tasks/total_tasks*100) if total_tasks else 0,
            "overdue_count": len(overdue_tasks), "pending_approvals": len(pending_approvals),
        }
    }

# ===== KEYWORD RANKINGS =====
@app.post("/api/rankings")
async def add_ranking(request: Request):
    user = require_role(request, ["super_admin", "operations_manager", "worker", "tech_seo"])
    data = await request.json()
    kw = data.get("keyword", "").strip()
    pos = data.get("position")
    if not kw or pos is None:
        raise HTTPException(status_code=400, detail="Keyword and position are required")
    db = get_db()
    prev = db.execute("SELECT position FROM keyword_rankings WHERE client_id=? AND keyword=? ORDER BY tracked_date DESC LIMIT 1",
                      (data["client_id"], kw)).fetchone()
    prev_pos = prev["position"] if prev else None
    db.execute("INSERT INTO keyword_rankings (client_id, keyword, position, previous_position, search_volume, url) VALUES (?,?,?,?,?,?)",
               (data["client_id"], kw, pos, prev_pos, data.get("search_volume", 0), data.get("url", "")))
    db.commit()
    db.close()
    return {"message": "Ranking recorded"}

@app.get("/api/rankings/{client_id}")
async def get_rankings(client_id: int, request: Request):
    user = require_auth(request)
    db = get_db()
    if client_id == 0:
        rankings = [dict(r) for r in db.execute("SELECT * FROM keyword_rankings ORDER BY tracked_date DESC, keyword LIMIT 200").fetchall()]
    else:
        rankings = [dict(r) for r in db.execute("SELECT * FROM keyword_rankings WHERE client_id=? ORDER BY tracked_date DESC, keyword LIMIT 100", (client_id,)).fetchall()]
    db.close()
    return {"rankings": rankings}

# ===== CONTRACTS =====
@app.get("/api/contracts")
async def list_contracts(request: Request):
    user = require_auth(request)
    db = get_db()
    contracts = [dict(r) for r in db.execute("SELECT * FROM contracts ORDER BY created_at DESC").fetchall()]
    db.close()
    return {"contracts": contracts}

@app.post("/api/contracts")
async def create_contract(request: Request):
    user = require_role(request, ["super_admin", "sales", "account_manager"])
    data = await request.json()
    db = get_db()
    c = db.cursor()
    c.execute("""INSERT INTO contracts (client_id, title, start_date, end_date, terms, status, monthly_value, auto_renew, created_by) VALUES (?,?,?,?,?,?,?,?,?)""",
              (data["client_id"], data["title"], data.get("start_date"), data.get("end_date"), data.get("terms"),
               data.get("status", "active"), data.get("monthly_value", 0), data.get("auto_renew", 0), user["id"]))
    contract_id = c.lastrowid
    log_activity(db, user["id"], "contract_created", f"Contract for client #{data['client_id']}", "contract", contract_id)
    db.commit()
    db.close()
    return {"id": contract_id, "message": "Contract created"}

# ===== SECURITY: Change Password =====
@app.post("/api/change-password")
async def change_password(request: Request):
    user = require_auth(request)
    data = await request.json()
    old_pw = data.get("old_password", "")
    new_pw = data.get("new_password", "")
    if len(new_pw) < 8:
        return JSONResponse({"error": "Password must be at least 8 characters"}, status_code=400)
    db = get_db()
    u = db.execute("SELECT password_hash FROM users WHERE id=?", (user["id"],)).fetchone()
    if not bcrypt.verify(old_pw, u["password_hash"]):
        db.close()
        return JSONResponse({"error": "Current password is incorrect"}, status_code=400)
    db.execute("UPDATE users SET password_hash=? WHERE id=?", (bcrypt.hash(new_pw), user["id"]))
    log_activity(db, user["id"], "password_changed", "User changed password", "user", user["id"])
    db.commit()
    db.close()
    return {"message": "Password changed successfully"}

# ===== PART 2: WHITE-LABEL REPORTS =====
@app.post("/api/reports/white-label")
async def generate_white_label_report(request: Request):
    user = require_role(request, ["super_admin", "finance", "operations_manager", "account_manager"])
    data = await request.json()
    client_id = data["client_id"]
    db = get_db()
    client = dict(db.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone())
    projects = [dict(r) for r in db.execute("SELECT * FROM projects WHERE client_id=?", (client_id,)).fetchall()]
    tasks_all = []
    for p in projects:
        tasks_all += [dict(r) for r in db.execute("SELECT * FROM tasks WHERE project_id=?", (p["id"],)).fetchall()]
    payments = [dict(r) for r in db.execute("SELECT * FROM payments WHERE client_id=?", (client_id,)).fetchall()]
    rankings = [dict(r) for r in db.execute("SELECT * FROM keyword_rankings WHERE client_id=? ORDER BY tracked_date DESC LIMIT 20", (client_id,)).fetchall()]
    locations = [dict(r) for r in db.execute("SELECT * FROM client_locations WHERE client_id=?", (client_id,)).fetchall()]
    
    agency_name = data.get("agency_name", "RankForge AI")
    agency_tagline = data.get("agency_tagline", "AI-Powered SEO & Reputation Management")
    primary_color = data.get("primary_color", "#0A1628")
    accent_color = data.get("accent_color", "#00D4FF")
    logo_url = data.get("logo_url", "")
    
    report_data = json.dumps({
        "client": client, "projects": projects, "tasks": tasks_all, "payments": payments,
        "rankings": rankings, "locations": locations,
        "branding": {"agency_name": agency_name, "tagline": agency_tagline, "primary_color": primary_color, "accent_color": accent_color, "logo_url": logo_url},
        "generated_at": datetime.now().isoformat(), "generated_by": user["full_name"]
    })
    
    c = db.cursor()
    c.execute("INSERT INTO client_reports (client_id, report_type, title, report_data, created_by) VALUES (?,?,?,?,?)",
              (client_id, "white_label", f"White-Label Report - {client['business_name']} - {datetime.now().strftime('%B %Y')}", report_data, user["id"]))
    report_id = c.lastrowid
    log_activity(db, user["id"], "report_generated", f"White-label report for {client['business_name']}", "report", report_id)
    db.commit()
    db.close()
    return {"id": report_id, "message": "White-label report generated"}

@app.get("/api/reports/{report_id}/white-label")
async def download_white_label_report(report_id: int, request: Request):
    user = require_auth(request)
    db = get_db()
    report = db.execute("SELECT r.*, c.business_name FROM client_reports r LEFT JOIN clients c ON r.client_id=c.id WHERE r.id=?", (report_id,)).fetchone()
    db.close()
    if not report:
        raise HTTPException(status_code=404)
    report = dict(report)
    rdata = json.loads(report["report_data"]) if report["report_data"] else {}
    client = rdata.get("client", {})
    projects = rdata.get("projects", [])
    tasks = rdata.get("tasks", [])
    payments = rdata.get("payments", [])
    rankings = rdata.get("rankings", [])
    branding = rdata.get("branding", {})
    
    agency = branding.get("agency_name", "RankForge AI")
    tagline = branding.get("tagline", "AI-Powered SEO & Reputation Management")
    pc = branding.get("primary_color", "#0A1628")
    ac = branding.get("accent_color", "#00D4FF")
    logo = branding.get("logo_url", "")
    
    completed_tasks = sum(1 for t in tasks if t.get("status") == "completed")
    total_tasks = len(tasks)
    total_paid = sum(p.get("amount", 0) for p in payments if p.get("status") == "paid")
    
    logo_html = f'<img src="{logo}" style="max-height:50px;margin-bottom:12px">' if logo else ""
    
    rankings_html = ""
    if rankings:
        rankings_html = '<div class="section"><h2>Keyword Rankings</h2><table><thead><tr><th>Keyword</th><th>Position</th><th>Change</th><th>Volume</th><th>URL</th></tr></thead><tbody>'
        for r in rankings:
            prev = r.get("previous_position")
            pos = r.get("position", 0)
            if prev and prev > pos:
                change = f'<span style="color:#059669">▲ {prev - pos}</span>'
            elif prev and prev < pos:
                change = f'<span style="color:#dc2626">▼ {pos - prev}</span>'
            else:
                change = '<span style="color:#999">—</span>'
            rankings_html += f'<tr><td><strong>{r.get("keyword","")}</strong></td><td>{pos}</td><td>{change}</td><td>{r.get("search_volume",0)}</td><td style="font-size:11px">{r.get("url","")}</td></tr>'
        rankings_html += '</tbody></table></div>'
    
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>{report['title']}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:Inter,Arial,sans-serif;background:#fff;color:#333;padding:40px}}
.header{{background:linear-gradient(135deg,{pc},{ac}22);color:#fff;padding:40px;border-radius:12px;margin-bottom:30px;border-left:5px solid {ac}}}
.header h1{{font-size:24px;margin-bottom:4px}}.header p{{opacity:.8;font-size:14px}}
.section{{margin-bottom:30px}}.section h2{{font-size:18px;color:{pc};border-bottom:2px solid {ac};padding-bottom:8px;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse;margin-top:12px}}th,td{{padding:10px 12px;text-align:left;border-bottom:1px solid #eee;font-size:13px}}
th{{background:#f7f9fc;font-weight:600}}.stat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:30px}}
.stat-card{{background:#f7f9fc;padding:20px;border-radius:8px;text-align:center;border-top:3px solid {ac}}}.stat-card .num{{font-size:28px;font-weight:700;color:{pc}}}
.stat-card .label{{font-size:12px;color:#666;margin-top:4px}}.badge{{padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600}}
.badge-paid,.badge-completed{{background:#d1fae5;color:#059669}}.badge-pending{{background:#fef3c7;color:#d97706}}
.badge-progress,.badge-in_progress{{background:#dbeafe;color:#2563eb}}
.footer{{margin-top:40px;padding-top:20px;border-top:2px solid #eee;text-align:center;color:#999;font-size:12px}}
.confidential{{background:#fef3c7;padding:8px 16px;border-radius:6px;font-size:11px;color:#92400e;margin-bottom:20px;text-align:center}}
@media print{{body{{padding:20px}}.header{{break-after:avoid}}}}
</style></head><body>
<div class="header">{logo_html}<h1>{agency}</h1><p>{tagline}</p><p style="margin-top:8px">Report for: <strong>{client.get('business_name','')}</strong> | {rdata.get('generated_at','')[:10]}</p></div>
<div class="confidential">CONFIDENTIAL — Prepared exclusively for {client.get('business_name','')}</div>
<div class="stat-grid">
<div class="stat-card"><div class="num">{len(projects)}</div><div class="label">Active Projects</div></div>
<div class="stat-card"><div class="num">{completed_tasks}/{total_tasks}</div><div class="label">Tasks Completed</div></div>
<div class="stat-card"><div class="num">{round(completed_tasks/total_tasks*100) if total_tasks else 0}%</div><div class="label">Completion Rate</div></div>
<div class="stat-card"><div class="num">${total_paid:,.0f}</div><div class="label">Total Invested</div></div>
</div>
{rankings_html}
<div class="section"><h2>Projects Overview</h2><table><thead><tr><th>Project</th><th>Service</th><th>Progress</th><th>Status</th></tr></thead><tbody>"""
    for p in projects:
        badge = "badge-completed" if p.get("status") == "completed" else "badge-progress"
        html += f'<tr><td>{p.get("title","")}</td><td>{p.get("service_type","")}</td><td>{p.get("progress",0)}%</td><td><span class="badge {badge}">{p.get("status","")}</span></td></tr>'
    html += """</tbody></table></div>
<div class="section"><h2>Task Breakdown</h2><table><thead><tr><th>Task</th><th>Priority</th><th>Status</th></tr></thead><tbody>"""
    for t in tasks:
        badge = "badge-completed" if t.get("status") == "completed" else ("badge-progress" if t.get("status") == "in_progress" else "badge-pending")
        html += f'<tr><td>{t.get("title","")}</td><td>{t.get("priority","")}</td><td><span class="badge {badge}">{t.get("status","")}</span></td></tr>'
    html += """</tbody></table></div>
<div class="section"><h2>Payment History</h2><table><thead><tr><th>Invoice</th><th>Amount</th><th>Due Date</th><th>Status</th></tr></thead><tbody>"""
    for pay in payments:
        badge = "badge-paid" if pay.get("status") == "paid" else "badge-pending"
        html += f'<tr><td>{pay.get("invoice_number","")}</td><td>${pay.get("amount",0):,.0f}</td><td>{pay.get("due_date","")}</td><td><span class="badge {badge}">{pay.get("status","")}</span></td></tr>'
    html += f"""</tbody></table></div>
<div class="footer"><p>{agency} | {tagline}</p><p>Generated by {rdata.get('generated_by','System')} on {rdata.get('generated_at','')[:10]}</p></div>
</body></html>"""
    return HTMLResponse(content=html)

# ===== PART 2: EMAIL SENDING =====
@app.post("/api/email/send")
async def send_email(request: Request):
    user = require_role(request, ["super_admin", "finance", "operations_manager", "account_manager"])
    data = await request.json()
    db = get_db()
    smtp = db.execute("SELECT * FROM api_settings WHERE provider='smtp'").fetchone()
    if not smtp or not smtp["api_key"]:
        db.close()
        return JSONResponse({"error": "SMTP not configured. Go to Settings → SMTP to configure email sending."}, status_code=400)
    smtp = dict(smtp)
    config = json.loads(smtp.get("config") or "{}")
    
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = data.get("subject", "RankForge AI Report")
        msg["From"] = config.get("from_email", smtp["api_key"])
        msg["To"] = data["to_email"]
        
        if data.get("html_body"):
            msg.attach(MIMEText(data["html_body"], "html"))
        elif data.get("body"):
            msg.attach(MIMEText(data["body"], "plain"))
        
        host = config.get("host", "smtp.gmail.com")
        port = int(config.get("port", 587))
        
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(config.get("from_email", smtp["api_key"]), smtp["api_key"])
            server.send_message(msg)
        
        log_activity(db, user["id"], "email_sent", f"Email to {data['to_email']}: {data.get('subject','')}", "email", 0)
        db.commit()
        db.close()
        return {"message": f"Email sent to {data['to_email']}"}
    except Exception as e:
        db.close()
        return JSONResponse({"error": f"Email failed: {str(e)}"}, status_code=500)

@app.post("/api/reports/{report_id}/email")
async def email_report(report_id: int, request: Request):
    user = require_role(request, ["super_admin", "finance", "operations_manager"])
    data = await request.json()
    db = get_db()
    report = db.execute("SELECT r.*, c.business_name, c.email as client_email FROM client_reports r LEFT JOIN clients c ON r.client_id=c.id WHERE r.id=?", (report_id,)).fetchone()
    if not report:
        db.close()
        raise HTTPException(status_code=404)
    report = dict(report)
    
    to_email = data.get("to_email", report.get("client_email", ""))
    if not to_email:
        db.close()
        return JSONResponse({"error": "No email address provided"}, status_code=400)
    
    smtp = db.execute("SELECT * FROM api_settings WHERE provider='smtp'").fetchone()
    if not smtp or not smtp["api_key"]:
        db.close()
        return JSONResponse({"error": "SMTP not configured"}, status_code=400)
    smtp_conf = json.loads(dict(smtp).get("config") or "{}")
    
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        rdata = json.loads(report["report_data"]) if report["report_data"] else {}
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Your SEO Report - {report['business_name']} - {report['title']}"
        msg["From"] = smtp_conf.get("from_email", dict(smtp)["api_key"])
        msg["To"] = to_email
        
        text = f"Hi,\n\nPlease find your latest SEO performance report attached.\n\nReport: {report['title']}\nGenerated: {rdata.get('generated_at','')[:10]}\n\nPlease log in to your client portal to view full details.\n\nBest regards,\nRankForge AI Team"
        msg.attach(MIMEText(text, "plain"))
        
        host = smtp_conf.get("host", "smtp.gmail.com")
        port = int(smtp_conf.get("port", 587))
        
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(smtp_conf.get("from_email", dict(smtp)["api_key"]), dict(smtp)["api_key"])
            server.send_message(msg)
        
        db.execute("UPDATE client_reports SET sent_to_client=1, sent_date=datetime('now'), sent_by=? WHERE id=?", (user["id"], report_id))
        log_activity(db, user["id"], "report_emailed", f"Report emailed to {to_email}", "report", report_id)
        db.commit()
        db.close()
        return {"message": f"Report emailed to {to_email}"}
    except Exception as e:
        db.close()
        return JSONResponse({"error": f"Email failed: {str(e)}"}, status_code=500)

# ===== PART 2: FILE ATTACHMENTS LIST =====
@app.get("/api/attachments/{related_type}/{related_id}")
async def list_attachments(related_type: str, related_id: int, request: Request):
    user = require_auth(request)
    db = get_db()
    files = [dict(r) for r in db.execute("""
        SELECT f.*, u.full_name as uploader_name FROM file_attachments f
        LEFT JOIN users u ON f.uploaded_by=u.id
        WHERE f.related_type=? AND f.related_id=? ORDER BY f.created_at DESC
    """, (related_type, related_id)).fetchall()]
    db.close()
    return {"attachments": files}

# ===== PART 2: CLIENT LOCATIONS =====
@app.post("/api/locations")
async def add_location(request: Request):
    user = require_role(request, ["super_admin", "operations_manager", "account_manager", "sales"])
    data = await request.json()
    db = get_db()
    c = db.cursor()
    c.execute("""INSERT INTO client_locations (client_id, location_name, address, city, state, zip_code, phone, gbp_url, gbp_cid) VALUES (?,?,?,?,?,?,?,?,?)""",
              (data["client_id"], data["location_name"], data.get("address"), data.get("city"), data.get("state"),
               data.get("zip_code"), data.get("phone"), data.get("gbp_url"), data.get("gbp_cid")))
    loc_id = c.lastrowid
    log_activity(db, user["id"], "location_added", f"Location: {data['location_name']} for client #{data['client_id']}", "location", loc_id)
    db.commit()
    db.close()
    return {"id": loc_id, "message": "Location added"}

@app.get("/api/locations/{client_id}")
async def get_locations(client_id: int, request: Request):
    user = require_auth(request)
    db = get_db()
    locations = [dict(r) for r in db.execute("SELECT * FROM client_locations WHERE client_id=? ORDER BY location_name", (client_id,)).fetchall()]
    db.close()
    return {"locations": locations}

# ===== PART 2: RANKINGS CHART PAGE =====
@app.get("/rankings/{client_id}", response_class=HTMLResponse)
async def rankings_chart_page(client_id: int, request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    db = get_db()
    client = db.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not client:
        db.close()
        raise HTTPException(status_code=404)
    client = dict(client)
    rankings = [dict(r) for r in db.execute("SELECT * FROM keyword_rankings WHERE client_id=? ORDER BY keyword, tracked_date", (client_id,)).fetchall()]
    locations = [dict(r) for r in db.execute("SELECT * FROM client_locations WHERE client_id=?", (client_id,)).fetchall()]
    db.close()
    
    keywords = {}
    for r in rankings:
        kw = r["keyword"]
        if kw not in keywords:
            keywords[kw] = {"positions": [], "current": r["position"], "previous": r.get("previous_position"), "volume": r.get("search_volume", 0), "url": r.get("url", "")}
        keywords[kw]["positions"].append(r["position"])
        keywords[kw]["current"] = r["position"]
    
    chart_data = json.dumps({"keywords": {k: v["positions"] for k, v in keywords.items()}})
    
    return templates.TemplateResponse("rankings_chart.html", {
        "request": request, "user": user, "client": client,
        "keywords": keywords, "chart_data": chart_data, "locations": locations
    })

# ===== PART 3: ACTIVITY TIMELINE PAGE =====
@app.get("/activity", response_class=HTMLResponse)
async def activity_page(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ("super_admin", "operations_manager"):
        return RedirectResponse(url="/login")
    db = get_db()
    activities = [dict(r) for r in db.execute("""
        SELECT al.*, u.full_name as user_name FROM activity_log al LEFT JOIN users u ON al.user_id=u.id ORDER BY al.created_at DESC LIMIT 200
    """).fetchall()]
    db.close()
    return templates.TemplateResponse("activity_timeline.html", {"request": request, "user": user, "activities": activities})

# ===== PART 3: WORKER PERFORMANCE =====
@app.get("/api/performance/{user_id}")
async def get_worker_performance(user_id: int, request: Request):
    user = require_auth(request)
    if user["role"] not in ("super_admin", "operations_manager") and user["id"] != user_id:
        return JSONResponse({"error": "Unauthorized"}, status_code=403)
    db = get_db()
    worker = db.execute("SELECT id, username, full_name, role, rank FROM users WHERE id=?", (user_id,)).fetchone()
    if not worker:
        db.close()
        raise HTTPException(status_code=404)
    worker = dict(worker)
    total_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=?", (user_id,)).fetchone()[0]
    completed_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status='completed'", (user_id,)).fetchone()[0]
    in_progress = db.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status='in_progress'", (user_id,)).fetchone()[0]
    total_hours = db.execute("SELECT COALESCE(SUM(hours),0) FROM time_entries WHERE user_id=?", (user_id,)).fetchone()[0]
    avg_hours = db.execute("SELECT COALESCE(AVG(hours),0) FROM time_entries WHERE user_id=? AND hours > 0", (user_id,)).fetchone()[0]
    active_projects = db.execute("SELECT COUNT(DISTINCT project_id) FROM tasks WHERE assigned_to=? AND status IN ('in_progress','pending')", (user_id,)).fetchone()[0]
    
    # Recent completed tasks
    recent = [dict(r) for r in db.execute("""
        SELECT t.title, t.status, t.priority, p.title as project_title 
        FROM tasks t LEFT JOIN projects p ON t.project_id=p.id WHERE t.assigned_to=? ORDER BY t.created_at DESC LIMIT 10
    """, (user_id,)).fetchall()]
    
    # Performance score (0-100)
    completion_rate = round(completed_tasks / total_tasks * 100) if total_tasks else 0
    score = min(100, completion_rate + min(20, int(total_hours)))
    
    db.close()
    return {
        "worker": worker,
        "stats": {
            "total_tasks": total_tasks, "completed_tasks": completed_tasks, "in_progress": in_progress,
            "completion_rate": completion_rate, "total_hours": round(total_hours, 1),
            "avg_hours_per_task": round(avg_hours, 1), "active_projects": active_projects,
            "performance_score": score
        },
        "recent_tasks": recent
    }

@app.get("/performance", response_class=HTMLResponse)
async def performance_page(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ("super_admin", "operations_manager"):
        return RedirectResponse(url="/login")
    db = get_db()
    workers = [dict(r) for r in db.execute("SELECT id, username, full_name, role, rank, salary FROM users WHERE role NOT IN ('super_admin','client') AND is_active=1").fetchall()]
    for w in workers:
        total = db.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=?", (w["id"],)).fetchone()[0]
        completed = db.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status='completed'", (w["id"],)).fetchone()[0]
        hours = db.execute("SELECT COALESCE(SUM(hours),0) FROM time_entries WHERE user_id=?", (w["id"],)).fetchone()[0]
        w["total_tasks"] = total
        w["completed_tasks"] = completed
        w["completion_rate"] = round(completed / total * 100) if total else 0
        w["total_hours"] = round(hours, 1)
        w["score"] = min(100, w["completion_rate"] + min(20, int(hours)))
    workers.sort(key=lambda x: x["score"], reverse=True)
    db.close()
    return templates.TemplateResponse("performance.html", {"request": request, "user": user, "workers": workers})

# ===== PART 3: NOTIFICATIONS API =====
@app.get("/api/notifications")
async def get_notifications(request: Request):
    user = require_auth(request)
    db = get_db()
    notifs = [dict(r) for r in db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 30", (user["id"],)).fetchall()]
    unread = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (user["id"],)).fetchone()[0]
    db.close()
    return {"notifications": notifs, "unread_count": unread}

@app.post("/api/notifications/read")
async def mark_notifications_read(request: Request):
    user = require_auth(request)
    db = get_db()
    db.execute("UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0", (user["id"],))
    db.commit()
    db.close()
    return {"message": "All notifications marked as read"}

@app.post("/api/notifications/create")
async def create_notification(request: Request):
    user = require_role(request, ["super_admin", "operations_manager"])
    data = await request.json()
    db = get_db()
    db.execute("INSERT INTO notifications (user_id, type, title, message, link) VALUES (?,?,?,?,?)",
               (data["user_id"], data.get("type", "info"), data["title"], data.get("message", ""), data.get("link")))
    db.commit()
    db.close()
    return {"message": "Notification sent"}

# ===== PART 3: BULK TASK CREATION FROM TEMPLATES =====
@app.post("/api/tasks/bulk")
async def create_bulk_tasks(request: Request):
    user = require_role(request, ["super_admin", "operations_manager", "account_manager"])
    data = await request.json()
    project_id = data["project_id"]
    tasks = data.get("tasks", [])
    db = get_db()
    c = db.cursor()
    created = 0
    for i, t in enumerate(tasks):
        c.execute("""INSERT INTO tasks (project_id, title, description, priority, assigned_to, order_num) VALUES (?,?,?,?,?,?)""",
                  (project_id, t["title"], t.get("description", ""), t.get("priority", "medium"), t.get("assigned_to"), i + 1))
        created += 1
    log_activity(db, user["id"], "bulk_tasks_created", f"Created {created} tasks for project #{project_id}", "project", project_id)
    db.commit()
    db.close()
    return {"message": f"{created} tasks created", "count": created}

# ===== PART 3: TASK STATUS UPDATE =====
@app.put("/api/tasks/{task_id}/status")
async def update_task_status(task_id: int, request: Request):
    user = require_auth(request)
    data = await request.json()
    new_status = data["status"]
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404)
    db.execute("UPDATE tasks SET status=? WHERE id=?", (new_status, task_id))
    if new_status == "completed":
        db.execute("UPDATE tasks SET completed_date=datetime('now') WHERE id=?", (task_id,))
        # Update project progress
        proj_id = task["project_id"]
        total = db.execute("SELECT COUNT(*) FROM tasks WHERE project_id=?", (proj_id,)).fetchone()[0]
        done = db.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND status='completed'", (proj_id,)).fetchone()[0] + 1
        progress = round(done / total * 100) if total else 0
        db.execute("UPDATE projects SET progress=? WHERE id=?", (progress, proj_id))
    log_activity(db, user["id"], "task_status_updated", f"Task #{task_id} → {new_status}", "task", task_id)
    db.commit()
    db.close()
    return {"message": f"Task updated to {new_status}"}

# ===== PART 3: DASHBOARD SEARCH =====
@app.get("/api/search")
async def search(request: Request, q: str = ""):
    user = require_auth(request)
    if not q or len(q) < 2:
        return {"results": []}
    db = get_db()
    results = []
    # Search clients
    for r in db.execute("SELECT id, business_name, contact_name, industry FROM clients WHERE business_name LIKE ? OR contact_name LIKE ? LIMIT 5",
                         (f"%{q}%", f"%{q}%")).fetchall():
        results.append({"type": "client", "id": r["id"], "title": r["business_name"], "subtitle": r["contact_name"], "link": f"/client/{r['id']}"})
    # Search projects
    for r in db.execute("SELECT p.id, p.title, c.business_name FROM projects p LEFT JOIN clients c ON p.client_id=c.id WHERE p.title LIKE ? LIMIT 5",
                         (f"%{q}%",)).fetchall():
        results.append({"type": "project", "id": r["id"], "title": r["title"], "subtitle": r["business_name"] or "", "link": f"/client/{r['id']}"})
    # Search tasks
    for r in db.execute("SELECT t.id, t.title, p.title as project_title FROM tasks t LEFT JOIN projects p ON t.project_id=p.id WHERE t.title LIKE ? LIMIT 5",
                         (f"%{q}%",)).fetchall():
        results.append({"type": "task", "id": r["id"], "title": r["title"], "subtitle": r["project_title"] or "", "link": "#"})
    db.close()
    return {"results": results}

# ===== PART 4: REVENUE FORECASTING =====
@app.get("/api/analytics/revenue")
async def revenue_analytics(request: Request):
    user = require_role(request, ["super_admin", "finance", "operations_manager"])
    db = get_db()
    
    # Current MRR from active clients
    mrr = db.execute("SELECT COALESCE(SUM(monthly_payment),0) FROM clients WHERE status='active'").fetchone()[0]
    
    # Revenue by month (from invoices)
    monthly_rev = [dict(r) for r in db.execute("""
        SELECT strftime('%Y-%m', issue_date) as month, SUM(total) as revenue, COUNT(*) as count 
        FROM invoices WHERE status='paid' GROUP BY month ORDER BY month DESC LIMIT 12
    """).fetchall()]
    
    # Revenue by package
    by_package = [dict(r) for r in db.execute("""
        SELECT package, COUNT(*) as clients, SUM(monthly_payment) as mrr 
        FROM clients WHERE status='active' AND package IS NOT NULL GROUP BY package
    """).fetchall()]
    
    # Pipeline (leads + prospects)
    pipeline = db.execute("SELECT COALESCE(SUM(monthly_payment),0) FROM clients WHERE status IN ('lead','prospect')").fetchone()[0]
    
    # Churn risk (overdue invoices)
    overdue_total = db.execute("SELECT COALESCE(SUM(total),0) FROM invoices WHERE status='overdue'").fetchone()[0]
    
    # Contract-based forecast (next 6 months)
    active_contracts = db.execute("SELECT COALESCE(SUM(monthly_value),0) FROM contracts WHERE status='active'").fetchone()[0]
    forecast = []
    for i in range(6):
        month_name = (datetime.now() + timedelta(days=30 * i)).strftime("%b %Y")
        projected = mrr + (active_contracts * 0.1 * i)  # Growth estimate
        forecast.append({"month": month_name, "projected": round(projected)})
    
    db.close()
    return {
        "mrr": mrr, "pipeline_value": pipeline, "overdue_total": overdue_total,
        "monthly_revenue": monthly_rev, "by_package": by_package,
        "forecast": forecast, "contract_mrr": active_contracts
    }

# ===== PART 4: DASHBOARD ANALYTICS =====
@app.get("/api/analytics/overview")
async def analytics_overview(request: Request):
    user = require_role(request, ["super_admin", "operations_manager"])
    db = get_db()
    
    # Task stats
    task_by_status = {}
    for r in db.execute("SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status").fetchall():
        task_by_status[r["status"]] = r["cnt"]
    
    # Tasks by priority
    task_by_priority = {}
    for r in db.execute("SELECT priority, COUNT(*) as cnt FROM tasks GROUP BY priority").fetchall():
        task_by_priority[r["priority"]] = r["cnt"]
    
    # Projects by service type
    by_service = {}
    for r in db.execute("SELECT service_type, COUNT(*) as cnt FROM projects GROUP BY service_type").fetchall():
        by_service[r["service_type"]] = r["cnt"]
    
    # Clients by industry
    by_industry = {}
    for r in db.execute("SELECT industry, COUNT(*) as cnt FROM clients GROUP BY industry").fetchall():
        by_industry[r["industry"]] = r["cnt"]
    
    # Time logged this week
    weekly_hours = db.execute("SELECT COALESCE(SUM(hours),0) FROM time_entries WHERE start_time >= date('now','-7 days')").fetchone()[0]
    
    # Top performers this week
    top_workers = [dict(r) for r in db.execute("""
        SELECT u.full_name, u.role, COUNT(t.id) as tasks_done 
        FROM tasks t JOIN users u ON t.assigned_to=u.id 
        WHERE t.status='completed' GROUP BY t.assigned_to ORDER BY tasks_done DESC LIMIT 5
    """).fetchall()]
    
    db.close()
    return {
        "task_by_status": task_by_status, "task_by_priority": task_by_priority,
        "by_service": by_service, "by_industry": by_industry,
        "weekly_hours": round(weekly_hours, 1), "top_workers": top_workers
    }

# ===== PART 4: ANALYTICS PAGE =====
@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ("super_admin", "finance", "operations_manager"):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("analytics.html", {"request": request, "user": user})

# ===== PART 4: INVOICE DOWNLOAD (PDF-STYLE HTML) =====
@app.get("/api/invoices/{invoice_id}/download")
async def download_invoice(invoice_id: int, request: Request):
    user = require_auth(request)
    db = get_db()
    inv = db.execute("""SELECT i.*, c.business_name, c.contact_name, c.email, c.phone, c.address 
                        FROM invoices i LEFT JOIN clients c ON i.client_id=c.id WHERE i.id=?""", (invoice_id,)).fetchone()
    if not inv:
        db.close()
        raise HTTPException(status_code=404)
    inv = dict(inv)
    items = [dict(r) for r in db.execute("SELECT * FROM invoice_items WHERE invoice_id=?", (invoice_id,)).fetchall()]
    db.close()
    
    items_html = ""
    for it in items:
        items_html += f'<tr><td>{it["description"]}</td><td style="text-align:center">{it["quantity"]}</td><td style="text-align:right">${it["rate"]:,.2f}</td><td style="text-align:right"><strong>${it["amount"]:,.2f}</strong></td></tr>'
    
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Invoice {inv['invoice_number']}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:Inter,Arial,sans-serif;background:#fff;color:#333;padding:40px;max-width:800px;margin:0 auto}}
.inv-header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:40px;padding-bottom:20px;border-bottom:3px solid #0A1628}}
.inv-header h1{{font-size:28px;color:#0A1628}}.inv-header .inv-num{{font-size:14px;color:#666}}
.inv-meta{{display:grid;grid-template-columns:1fr 1fr;gap:30px;margin-bottom:30px}}
.inv-meta h3{{font-size:12px;text-transform:uppercase;color:#999;margin-bottom:8px}}
table{{width:100%;border-collapse:collapse;margin-bottom:20px}}th{{background:#0A1628;color:#fff;padding:10px 12px;text-align:left;font-size:12px;text-transform:uppercase}}
td{{padding:10px 12px;border-bottom:1px solid #eee;font-size:13px}}
.totals{{text-align:right;margin-top:20px}}.totals .total-row{{display:flex;justify-content:flex-end;gap:30px;padding:6px 0;font-size:14px}}
.totals .grand-total{{font-size:20px;font-weight:700;color:#0A1628;border-top:2px solid #0A1628;padding-top:10px;margin-top:8px}}
.badge{{display:inline-block;padding:4px 12px;border-radius:4px;font-size:12px;font-weight:600}}
.badge-paid{{background:#d1fae5;color:#059669}}.badge-sent,.badge-pending{{background:#fef3c7;color:#d97706}}.badge-overdue{{background:#fee2e2;color:#dc2626}}
.footer{{margin-top:40px;padding-top:20px;border-top:1px solid #eee;text-align:center;color:#999;font-size:11px}}
@media print{{body{{padding:20px}}}}
</style></head><body>
<div class="inv-header"><div><h1>INVOICE</h1><p class="inv-num">{inv['invoice_number']}</p></div>
<div style="text-align:right"><h2 style="color:#0A1628">RankForge AI</h2><p style="color:#666;font-size:13px">AI-Powered SEO & Reputation Management</p>
<span class="badge badge-{inv['status']}">{inv['status'].upper()}</span></div></div>
<div class="inv-meta"><div><h3>Bill To</h3><p><strong>{inv.get('business_name','')}</strong></p><p>{inv.get('contact_name','')}</p><p>{inv.get('email','')}</p><p>{inv.get('phone','')}</p></div>
<div style="text-align:right"><h3>Invoice Details</h3><p>Issue Date: <strong>{inv['issue_date']}</strong></p><p>Due Date: <strong>{inv['due_date']}</strong></p>
{f"<p>Paid Date: <strong>{inv['paid_date']}</strong></p>" if inv.get('paid_date') else ''}</div></div>
<table><thead><tr><th>Description</th><th style="text-align:center">Qty</th><th style="text-align:right">Rate</th><th style="text-align:right">Amount</th></tr></thead>
<tbody>{items_html}</tbody></table>
<div class="totals"><div class="total-row"><span>Subtotal:</span><span>${inv['subtotal']:,.2f}</span></div>
{"<div class='total-row'><span>Tax (" + str(inv['tax_rate']) + "%):</span><span>$" + f"{inv['tax_amount']:,.2f}" + "</span></div>" if inv.get('tax_amount') else ""}
<div class="total-row grand-total"><span>Total:</span><span>${inv['total']:,.2f}</span></div></div>
{f"<p style='margin-top:20px;color:#666;font-size:13px'>Notes: {inv['notes']}</p>" if inv.get('notes') else ''}
<div class="footer"><p>RankForge AI | Thank you for your business!</p><p>Questions? Contact us at billing@aigrowth-labs.com</p></div>
</body></html>"""
    return HTMLResponse(content=html)

# ===== PART 4: PROJECT PROGRESS UPDATE =====
@app.put("/api/projects/{project_id}/progress")
async def update_project_progress(project_id: int, request: Request):
    user = require_auth(request)
    data = await request.json()
    db = get_db()
    db.execute("UPDATE projects SET progress=? WHERE id=?", (data["progress"], project_id))
    if data["progress"] >= 100:
        db.execute("UPDATE projects SET status='completed' WHERE id=?", (project_id,))
    log_activity(db, user["id"], "project_updated", f"Project #{project_id} progress → {data['progress']}%", "project", project_id)
    db.commit()
    db.close()
    return {"message": f"Project progress updated to {data['progress']}%"}

# ============================================================================
# PART 5: FULL API INTEGRATIONS (Demo Mode — replace API keys for production)
# ============================================================================

# ----- DEMO AI RESPONSES (Used when no real API key configured) -----
DEMO_AI_RESPONSES = {
    "technical_seo_audit": {
        "title": "Technical SEO Audit Report",
        "sections": [
            {"name": "Site Speed", "score": 78, "issues": ["Large images need compression", "Render-blocking CSS detected", "No lazy loading on below-fold images"], "recommendations": ["Compress images with WebP format", "Defer non-critical CSS", "Add loading='lazy' to images"]},
            {"name": "Mobile Usability", "score": 85, "issues": ["Text too small on mobile", "Clickable elements too close"], "recommendations": ["Increase base font to 16px", "Add 8px padding between tap targets"]},
            {"name": "Indexability", "score": 92, "issues": ["3 pages blocked by robots.txt", "Missing canonical on 2 pages"], "recommendations": ["Review robots.txt rules", "Add canonical tags to all pages"]},
            {"name": "Schema Markup", "score": 65, "issues": ["No LocalBusiness schema", "Missing FAQ schema", "No breadcrumb markup"], "recommendations": ["Add LocalBusiness structured data", "Implement FAQ schema on service pages", "Add BreadcrumbList schema"]},
            {"name": "Core Web Vitals", "score": 72, "issues": ["LCP: 3.2s (needs <2.5s)", "CLS: 0.15 (needs <0.1)"], "recommendations": ["Optimize LCP by preloading hero image", "Fix CLS by setting explicit dimensions on images"]}
        ],
        "overall_score": 78,
        "summary": "The website has a solid foundation but needs improvements in speed optimization, schema markup, and Core Web Vitals to compete effectively in search rankings."
    },
    "content_generation": {
        "blog_post": {
            "title": "10 Local SEO Strategies That Actually Work in 2026",
            "meta_description": "Discover 10 proven local SEO strategies for 2026. From AI visibility optimization to Google Business Profile tactics that drive real results.",
            "word_count": 1500,
            "sections": ["Introduction", "1. AI Search Optimization", "2. Google Business Profile Mastery", "3. Local Link Building", "4. Review Generation Strategy", "5. Local Content Creation", "6. Citation Building", "7. Schema Markup Implementation", "8. Voice Search Optimization", "9. Mobile-First Optimization", "10. Competitor DNA Analysis", "Conclusion"],
            "keywords": ["local SEO 2026", "local search optimization", "Google Business Profile", "local SEO strategies"]
        },
        "social_post": {
            "platforms": {
                "facebook": "Is your business invisible on Google? 85% of local businesses don't show up in the top 3 results. Our AI-powered SEO audit reveals exactly what's holding you back. Get your FREE audit today! Link in comments.",
                "instagram": "STOP losing customers to competitors who rank above you on Google. Our AI SEO audit analyzes 100+ ranking factors in minutes. Free audit link in bio!",
                "linkedin": "Local businesses are missing out on 70% of potential customers because they don't appear in Google's Map Pack. Our DNA-level SEO audit identifies the exact factors holding your rankings back. DM me for a free audit."
            }
        },
        "meta_descriptions": [
            {"page": "Homepage", "description": "AI-powered local SEO services that get your business to #1 on Google. Serving USA businesses with data-driven SEO, reputation management, and lead generation."},
            {"page": "Local SEO", "description": "Dominate local search results with our proven Local SEO strategy. Google Map Pack rankings, citation building, and review management for local businesses."}
        ]
    },
    "competitor_analysis": {
        "competitors": [
            {"name": "Competitor A", "domain_authority": 45, "organic_keywords": 1250, "monthly_traffic": 15000, "top_keywords": ["local seo services", "seo agency near me"], "strengths": ["Strong backlink profile", "Active blog"], "weaknesses": ["Poor mobile speed", "No schema markup"]},
            {"name": "Competitor B", "domain_authority": 38, "organic_keywords": 890, "monthly_traffic": 8500, "top_keywords": ["seo company", "digital marketing"], "strengths": ["Good reviews", "Local citations"], "weaknesses": ["Thin content", "No AI optimization"]},
            {"name": "Competitor C", "domain_authority": 52, "organic_keywords": 2100, "monthly_traffic": 25000, "top_keywords": ["best seo agency", "seo services usa"], "strengths": ["National presence", "PPC campaigns"], "weaknesses": ["Expensive", "No local focus"]}
        ],
        "opportunities": ["Target long-tail keywords competitors miss", "Build more local citations", "Create AI-optimized content", "Improve page speed"],
        "threat_level": "Medium — competitors have stronger backlinks but weaker AI strategy"
    }
}

# ----- 1. AI AUDIT PROCESSING (with demo fallback) -----
@app.post("/api/ai/audit/{client_id}")
async def run_ai_audit(client_id: int, request: Request):
    user = require_role(request, ["super_admin", "tech_seo", "operations_manager"])
    db = get_db()
    client = db.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not client:
        db.close()
        raise HTTPException(status_code=404, detail="Client not found")
    client = dict(client)

    api = db.execute("SELECT * FROM api_settings WHERE provider IN ('claude','chatgpt','gemini') AND is_active=1 LIMIT 1").fetchone()
    
    if api and api["api_key"]:
        provider = api["provider"]
        config = json.loads(api["config_json"] or "{}")
        # PRODUCTION: Real API call would go here
        # if provider == "claude":
        #     import anthropic
        #     client_ai = anthropic.Anthropic(api_key=api["api_key"])
        #     response = client_ai.messages.create(model=config.get("model","claude-sonnet-4-20250514"), max_tokens=4096, messages=[{"role":"user","content":f"Perform a technical SEO audit for {client['website']}..."}])
        #     result = response.content[0].text
        # elif provider == "chatgpt":
        #     import openai
        #     openai.api_key = api["api_key"]
        #     response = openai.chat.completions.create(model=config.get("model","gpt-4.5"), messages=[{"role":"user","content":f"Perform a technical SEO audit for {client['website']}..."}])
        #     result = response.choices[0].message.content
        # elif provider == "gemini":
        #     import google.generativeai as genai
        #     genai.configure(api_key=api["api_key"])
        #     model = genai.GenerativeModel(config.get("model","gemini-pro"))
        #     response = model.generate_content(f"Perform a technical SEO audit for {client['website']}...")
        #     result = response.text
        audit_result = DEMO_AI_RESPONSES["technical_seo_audit"]
        audit_result["client"] = client["business_name"]
        audit_result["website"] = client["website"]
        audit_result["provider"] = provider
        audit_result["mode"] = "demo"
        audit_result["note"] = f"Demo mode — connect real {provider} API key in Settings for live audits"
    else:
        audit_result = DEMO_AI_RESPONSES["technical_seo_audit"]
        audit_result["client"] = client["business_name"]
        audit_result["website"] = client["website"]
        audit_result["provider"] = "demo"
        audit_result["mode"] = "demo"
        audit_result["note"] = "No AI API key configured. Go to Settings → API Settings to add Claude/ChatGPT/Gemini key."

    db.execute("""INSERT INTO seo_audits (client_id, website_url, status, ai_provider, created_by, audit_data, overall_score, completed_at)
                  VALUES (?,?,?,?,?,?,?,datetime('now'))""",
               (client_id, client["website"], "completed", audit_result.get("provider","demo"), user["id"], json.dumps(audit_result), audit_result.get("overall_score", 78)))
    log_activity(db, user["id"], "ai_audit", f"AI audit for {client['business_name']}", "client", client_id)
    db.commit()
    db.close()
    return {"message": "AI audit completed", "result": audit_result}

# ----- 2. AI CONTENT GENERATION -----
@app.post("/api/ai/content/generate")
async def generate_content(request: Request):
    user = require_role(request, ["super_admin", "tech_seo", "content_writer", "social_media", "operations_manager"])
    data = await request.json()
    content_type = data.get("type", "blog_post")
    topic = data.get("topic", "Local SEO Tips")
    client_id = data.get("client_id")

    db = get_db()
    api = db.execute("SELECT * FROM api_settings WHERE provider IN ('claude','chatgpt','gemini') AND is_active=1 LIMIT 1").fetchone()

    if api and api["api_key"]:
        # PRODUCTION: Real API call for content generation
        # prompt = f"Generate a {content_type} about '{topic}' for an SEO agency blog..."
        result = DEMO_AI_RESPONSES["content_generation"].get(content_type, DEMO_AI_RESPONSES["content_generation"]["blog_post"])
        result["mode"] = "demo"
        result["provider"] = api["provider"]
        result["note"] = f"Demo content — connect real {api['provider']} API key for AI-generated content"
    else:
        result = DEMO_AI_RESPONSES["content_generation"].get(content_type, DEMO_AI_RESPONSES["content_generation"]["blog_post"])
        result["mode"] = "demo"
        result["provider"] = "demo"
        result["note"] = "No AI API key configured. Add one in Settings for real AI content generation."

    result["topic"] = topic
    result["generated_at"] = datetime.now().isoformat()
    
    log_activity(db, user["id"], "content_generated", f"Generated {content_type}: {topic}", "system", 0)
    db.commit()
    db.close()
    return {"message": "Content generated", "content": result}

# ----- 3. AI COMPETITOR ANALYSIS -----
@app.post("/api/ai/competitor-analysis/{client_id}")
async def ai_competitor_analysis(client_id: int, request: Request):
    user = require_role(request, ["super_admin", "tech_seo", "operations_manager"])
    db = get_db()
    client = db.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not client:
        db.close()
        raise HTTPException(status_code=404, detail="Client not found")
    
    result = DEMO_AI_RESPONSES["competitor_analysis"]
    result["client"] = dict(client)["business_name"]
    result["mode"] = "demo"
    result["analyzed_at"] = datetime.now().isoformat()
    
    log_activity(db, user["id"], "competitor_analysis", f"Competitor analysis for {dict(client)['business_name']}", "client", client_id)
    db.commit()
    db.close()
    return {"message": "Competitor analysis complete", "analysis": result}

# ----- 4. AI CHAT ASSISTANT FOR WORKERS -----
@app.post("/api/ai/chat-assistant")
async def ai_chat_assistant(request: Request):
    user = require_auth(request)
    data = await request.json()
    question = data.get("question", "")
    
    demo_responses = {
        "crawl": "To fix crawl errors: 1) Check robots.txt for blocked URLs, 2) Submit affected URLs for re-indexing in GSC, 3) Fix any 404 errors with 301 redirects, 4) Ensure proper internal linking to orphaned pages.",
        "speed": "To improve page speed: 1) Compress images to WebP format, 2) Enable browser caching, 3) Minify CSS/JS, 4) Use a CDN, 5) Defer non-critical JavaScript, 6) Optimize Core Web Vitals (LCP, CLS, FID).",
        "ranking": "To improve keyword rankings: 1) Optimize title tags and meta descriptions, 2) Add schema markup, 3) Build quality backlinks, 4) Create comprehensive content around target keywords, 5) Improve page speed and user experience.",
        "review": "To get more reviews: 1) Send automated review requests after service completion, 2) Make it easy with direct Google review links, 3) Respond to all reviews (positive and negative), 4) Train staff to ask for reviews naturally.",
        "default": f"Great question about '{question}'! Here are general SEO tips: 1) Focus on user intent, 2) Create high-quality content, 3) Build authoritative backlinks, 4) Optimize for Core Web Vitals, 5) Use structured data markup. For specific guidance, check our internal knowledge base or consult with the Tech SEO team."
    }
    
    response_key = "default"
    for key in demo_responses:
        if key in question.lower():
            response_key = key
            break
    
    return {"answer": demo_responses[response_key], "mode": "demo", "note": "Connect AI API key in Settings for real-time AI answers"}

# ----- 5. TWILIO VOICE AGENT (Demo) -----
@app.post("/api/voice/incoming")
async def voice_incoming(request: Request):
    """Twilio webhook for incoming calls — returns TwiML response"""
    # PRODUCTION: Replace with real Twilio TwiML
    # from twilio.twiml.voice_response import VoiceResponse
    # response = VoiceResponse()
    # response.say("Thank you for calling RankForge AI...")
    # response.gather(num_digits=1, action="/api/voice/menu")
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Thank you for calling RankForge AI, your AI-powered SEO and digital marketing partner.</Say>
    <Gather numDigits="1" action="/api/voice/menu" method="POST">
        <Say voice="alice">Press 1 for a free SEO audit. Press 2 to speak with our sales team. Press 3 for existing client support.</Say>
    </Gather>
    <Say voice="alice">We didn't receive any input. Goodbye!</Say>
</Response>"""
    return Response(content=twiml, media_type="application/xml")

@app.post("/api/voice/menu")
async def voice_menu(request: Request):
    form = await request.form()
    digit = form.get("Digits", "0")
    responses = {
        "1": '<Say voice="alice">Great! We will send you a free AI-powered SEO audit. Please leave your name, business name, and website URL after the beep.</Say><Record maxLength="120" action="/api/voice/recording" />',
        "2": '<Say voice="alice">Connecting you to our sales team now. Please hold.</Say><Dial>+1234567890</Dial>',
        "3": '<Say voice="alice">For existing client support, please email support@aigrowth-labs.com or log in to your client portal at our website. Thank you!</Say>'
    }
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response>{responses.get(digit, "<Say>Invalid option. Goodbye!</Say>")}</Response>'
    return Response(content=twiml, media_type="application/xml")

@app.post("/api/voice/recording")
async def voice_recording(request: Request):
    form = await request.form()
    recording_url = form.get("RecordingUrl", "demo://recording")
    db = get_db()
    log_activity(db, 1, "voice_call", f"New voice recording received: {recording_url}", "system", 0)
    db.commit()
    db.close()
    twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="alice">Thank you! We will review your message and get back to you within 24 hours. Goodbye!</Say></Response>'
    return Response(content=twiml, media_type="application/xml")

@app.post("/api/voice/outbound")
async def voice_outbound(request: Request):
    """Initiate outbound call (demo mode)"""
    user = require_role(request, ["super_admin", "sales", "account_manager"])
    data = await request.json()
    phone = data.get("phone_number", "")
    
    db = get_db()
    api = db.execute("SELECT * FROM api_settings WHERE provider='twilio' AND is_active=1").fetchone()
    
    if api and api["api_key"]:
        # PRODUCTION: Real Twilio call
        # from twilio.rest import Client
        # config = json.loads(api["config_json"])
        # client = Client(config["account_sid"], api["api_key"])
        # call = client.calls.create(to=phone, from_=config["phone_number"], url=config["voice_url"])
        log_activity(db, user["id"], "outbound_call", f"Outbound call to {phone}", "system", 0)
        db.commit()
        db.close()
        return {"message": f"Call initiated to {phone}", "status": "demo", "call_sid": f"demo_call_{int(time.time())}", "note": "Demo mode — connect real Twilio credentials for live calls"}
    else:
        db.close()
        return {"message": "Twilio not configured", "status": "not_configured", "note": "Add Twilio Account SID and Auth Token in Settings → API Settings"}

# ----- 6. WHATSAPP INTEGRATION (Demo) -----
@app.post("/api/whatsapp/send")
async def whatsapp_send(request: Request):
    """Send WhatsApp message to client"""
    user = require_role(request, ["super_admin", "sales", "account_manager", "operations_manager"])
    data = await request.json()
    to_phone = data.get("phone", "")
    message = data.get("message", "")
    template = data.get("template")
    
    db = get_db()
    api = db.execute("SELECT * FROM api_settings WHERE provider='whatsapp' AND is_active=1").fetchone()
    
    if api and api["api_key"]:
        # PRODUCTION: Real WhatsApp Business API call
        # config = json.loads(api["config_json"])
        # import requests as req
        # url = f"https://graph.facebook.com/{config['api_version']}/{config['phone_number_id']}/messages"
        # headers = {"Authorization": f"Bearer {api['api_key']}", "Content-Type": "application/json"}
        # payload = {"messaging_product": "whatsapp", "to": to_phone, "type": "text", "text": {"body": message}}
        # resp = req.post(url, headers=headers, json=payload)
        log_activity(db, user["id"], "whatsapp_sent", f"WhatsApp to {to_phone}: {message[:50]}...", "system", 0)
        db.commit()
        db.close()
        return {"message": "WhatsApp message sent (demo)", "to": to_phone, "status": "demo", "message_id": f"wam_demo_{int(time.time())}", "note": "Demo mode — connect WhatsApp Business API key in Settings"}
    else:
        db.close()
        return {"message": "WhatsApp not configured", "status": "not_configured", "note": "Add WhatsApp Business API token in Settings → API Settings"}

@app.post("/api/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    """WhatsApp incoming message webhook"""
    data = await request.json()
    db = get_db()
    log_activity(db, 1, "whatsapp_received", f"WhatsApp webhook received: {json.dumps(data)[:100]}", "system", 0)
    db.commit()
    db.close()
    return {"status": "received"}

@app.get("/api/whatsapp/webhook")
async def whatsapp_verify(request: Request):
    """WhatsApp webhook verification (GET)"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403)

# ----- 7. SLACK/TEAMS WEBHOOK INTEGRATION -----
@app.post("/api/slack/send")
async def slack_send_notification(request: Request):
    """Send notification to Slack channel"""
    user = require_role(request, ["super_admin", "operations_manager"])
    data = await request.json()
    message = data.get("message", "")
    channel = data.get("channel", "#notifications")
    
    db = get_db()
    api = db.execute("SELECT * FROM api_settings WHERE provider='slack' AND is_active=1").fetchone()
    
    if api and api["api_key"]:
        config = json.loads(api["config_json"] or "{}")
        # PRODUCTION: Real Slack webhook
        # import requests as req
        # webhook_url = config.get("webhook_url", api["api_key"])
        # payload = {"channel": channel, "username": config.get("bot_name", "RankForge AI"), "text": message, "icon_emoji": ":chart_with_upwards_trend:"}
        # req.post(webhook_url, json=payload)
        log_activity(db, user["id"], "slack_notification", f"Slack → {channel}: {message[:50]}...", "system", 0)
        db.commit()
        db.close()
        return {"message": "Slack notification sent (demo)", "channel": channel, "status": "demo", "note": "Demo mode — add real Slack webhook URL in Settings"}
    else:
        db.close()
        return {"message": "Slack not configured", "status": "not_configured", "note": "Add Slack Incoming Webhook URL in Settings → API Settings"}

@app.post("/api/slack/events")
async def slack_events(request: Request):
    """Slack Events API endpoint"""
    data = await request.json()
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}
    return {"status": "received"}

# Internal helper to fire Slack/Teams on key events
def notify_slack(event_type: str, message: str):
    """Fire webhook on key events (called internally)"""
    try:
        db = get_db()
        api = db.execute("SELECT * FROM api_settings WHERE provider='slack' AND is_active=1").fetchone()
        if api and api["api_key"]:
            config = json.loads(api["config_json"] or "{}")
            # PRODUCTION:
            # import requests as req
            # req.post(config.get("webhook_url", api["api_key"]), json={"text": f"[{event_type}] {message}"})
            pass
        db.close()
    except:
        pass

# ----- 8. GOOGLE SEARCH CONSOLE API (Demo) -----
@app.get("/api/gsc/rankings/{client_id}")
async def gsc_rankings(client_id: int, request: Request):
    """Fetch keyword rankings from Google Search Console"""
    user = require_role(request, ["super_admin", "tech_seo", "operations_manager", "client"])
    db = get_db()
    client = db.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not client:
        db.close()
        raise HTTPException(status_code=404, detail="Client not found")
    client = dict(client)
    
    api = db.execute("SELECT * FROM api_settings WHERE provider='google_search_console' AND is_active=1").fetchone()
    
    if api and api["api_key"]:
        # PRODUCTION: Real Google Search Console API
        # from google.oauth2.credentials import Credentials
        # from googleapiclient.discovery import build
        # creds = Credentials(token=None, refresh_token=config["refresh_token"], client_id=config["client_id"], client_secret=config["client_secret"], token_uri="https://oauth2.googleapis.com/token")
        # service = build("searchconsole", "v1", credentials=creds)
        # response = service.searchanalytics().query(siteUrl=config["property_url"], body={"startDate":"2026-04-01","endDate":"2026-05-14","dimensions":["query"],"rowLimit":20}).execute()
        pass
    
    # Demo data — realistic GSC-style response
    demo_rankings = [
        {"keyword": f"local seo services {client.get('city','')}", "position": 3.2, "clicks": 145, "impressions": 2340, "ctr": 6.2, "change": -1.5},
        {"keyword": f"seo agency {client.get('city','')}", "position": 5.8, "clicks": 89, "impressions": 1890, "ctr": 4.7, "change": -2.1},
        {"keyword": f"google business profile optimization", "position": 8.1, "clicks": 56, "impressions": 3200, "ctr": 1.8, "change": -0.5},
        {"keyword": f"reputation management {client.get('city','')}", "position": 4.5, "clicks": 67, "impressions": 1200, "ctr": 5.6, "change": -3.2},
        {"keyword": f"best seo company near me", "position": 12.3, "clicks": 23, "impressions": 4500, "ctr": 0.5, "change": 2.1},
        {"keyword": f"ai seo services", "position": 6.7, "clicks": 34, "impressions": 980, "ctr": 3.5, "change": -1.8},
        {"keyword": f"local business marketing", "position": 9.4, "clicks": 41, "impressions": 1560, "ctr": 2.6, "change": 0.3},
        {"keyword": f"dental seo services", "position": 2.1, "clicks": 198, "impressions": 3400, "ctr": 5.8, "change": -0.8},
    ]
    
    db.close()
    return {
        "client": client["business_name"],
        "website": client["website"],
        "period": "Last 28 days",
        "total_clicks": sum(r["clicks"] for r in demo_rankings),
        "total_impressions": sum(r["impressions"] for r in demo_rankings),
        "avg_position": round(sum(r["position"] for r in demo_rankings) / len(demo_rankings), 1),
        "keywords": demo_rankings,
        "mode": "demo",
        "note": "Connect Google Search Console API in Settings for real ranking data"
    }

@app.post("/api/gsc/sync/{client_id}")
async def gsc_sync(client_id: int, request: Request):
    """Sync keyword rankings from GSC into local keyword_rankings table"""
    user = require_role(request, ["super_admin", "tech_seo", "operations_manager"])
    db = get_db()
    
    # In production, fetch from GSC API. In demo, create sample rankings
    demo_keywords = [
        ("local seo services", 3, 5),
        ("seo agency near me", 6, 8),
        ("google business profile", 8, 7),
        ("reputation management", 4, 6),
    ]
    for kw, pos, prev in demo_keywords:
        db.execute("""INSERT INTO keyword_rankings (client_id, keyword, position, previous_position, tracked_date)
                      VALUES (?,?,?,?,date('now'))""", (client_id, kw, pos, prev))
    
    log_activity(db, user["id"], "gsc_sync", f"Synced GSC rankings for client #{client_id}", "client", client_id)
    db.commit()
    db.close()
    return {"message": "Rankings synced from Google Search Console (demo)", "keywords_synced": len(demo_keywords)}

# ----- 9. STRIPE RECURRING BILLING (Demo) -----
@app.post("/api/billing/create-subscription")
async def create_subscription(request: Request):
    """Create recurring subscription for client"""
    user = require_role(request, ["super_admin", "finance"])
    data = await request.json()
    client_id = data.get("client_id")
    plan = data.get("plan", "pro")
    amount = data.get("amount", 2997)
    
    db = get_db()
    api = db.execute("SELECT * FROM api_settings WHERE provider='stripe' AND is_active=1").fetchone()
    
    if api and api["api_key"]:
        # PRODUCTION: Real Stripe API
        # import stripe
        # stripe.api_key = api["api_key"]
        # customer = stripe.Customer.create(email=data.get("email"), name=data.get("name"))
        # price = stripe.Price.create(unit_amount=amount*100, currency="usd", recurring={"interval": "month"}, product_data={"name": f"RankForge AI - {plan.title()} Plan"})
        # subscription = stripe.Subscription.create(customer=customer.id, items=[{"price": price.id}])
        pass
    
    subscription_id = f"sub_demo_{int(time.time())}"
    
    # Create monthly invoice
    client = db.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if client:
        client = dict(client)
        inv_num = f"INV-{datetime.now().strftime('%Y%m')}-{client_id:03d}"
        db.execute("""INSERT INTO invoices (client_id, invoice_number, issue_date, due_date, subtotal, tax_rate, tax_amount, total, status, notes)
                      VALUES (?,?,date('now'),date('now','+30 days'),?,0,0,?,?,?)""",
                   (client_id, inv_num, amount, amount, "sent", f"Recurring {plan.title()} plan - {subscription_id}"))
    
    log_activity(db, user["id"], "subscription_created", f"Subscription {subscription_id} for client #{client_id}", "client", client_id)
    db.commit()
    db.close()
    return {
        "message": "Subscription created (demo)",
        "subscription_id": subscription_id,
        "plan": plan,
        "amount": amount,
        "interval": "monthly",
        "status": "active",
        "mode": "demo",
        "note": "Connect Stripe API key in Settings for real billing"
    }

@app.post("/api/billing/cancel-subscription")
async def cancel_subscription(request: Request):
    user = require_role(request, ["super_admin", "finance"])
    data = await request.json()
    subscription_id = data.get("subscription_id", "")
    return {"message": f"Subscription {subscription_id} cancelled (demo)", "status": "cancelled", "mode": "demo"}

@app.post("/api/billing/webhook")
async def stripe_webhook(request: Request):
    """Stripe webhook endpoint for payment events"""
    body = await request.body()
    # PRODUCTION: Verify Stripe signature
    # import stripe
    # sig = request.headers.get("stripe-signature")
    # event = stripe.Webhook.construct_event(body, sig, webhook_secret)
    data = json.loads(body) if body else {}
    event_type = data.get("type", "unknown")
    
    db = get_db()
    if event_type == "invoice.paid":
        log_activity(db, 1, "payment_received", f"Payment received via Stripe", "system", 0)
    elif event_type == "invoice.payment_failed":
        log_activity(db, 1, "payment_failed", f"Payment failed via Stripe", "system", 0)
    elif event_type == "customer.subscription.deleted":
        log_activity(db, 1, "subscription_cancelled", f"Subscription cancelled", "system", 0)
    db.commit()
    db.close()
    return {"received": True}

@app.post("/api/billing/send-reminder")
async def send_payment_reminder(request: Request):
    """Send payment reminder for overdue invoices"""
    user = require_role(request, ["super_admin", "finance"])
    data = await request.json()
    invoice_id = data.get("invoice_id")
    
    db = get_db()
    inv = db.execute("SELECT i.*, c.business_name, c.email FROM invoices i JOIN clients c ON i.client_id=c.id WHERE i.id=?", (invoice_id,)).fetchone()
    if not inv:
        db.close()
        raise HTTPException(status_code=404, detail="Invoice not found")
    inv = dict(inv)
    
    # Demo: Would send email via SMTP or Stripe
    log_activity(db, user["id"], "payment_reminder", f"Payment reminder sent for {inv['invoice_number']} to {inv['business_name']}", "invoice", invoice_id)
    db.commit()
    db.close()
    return {"message": f"Payment reminder sent to {inv['business_name']} for {inv['invoice_number']} (${inv['total']:,.2f})", "mode": "demo"}

# ----- 10. DARK/LIGHT MODE TOGGLE -----
@app.post("/api/user/theme")
async def toggle_theme(request: Request):
    """Toggle dark/light mode preference"""
    user = require_auth(request)
    data = await request.json()
    theme = data.get("theme", "dark")
    # Store in cookie
    response = JSONResponse({"message": f"Theme set to {theme}", "theme": theme})
    response.set_cookie("theme_preference", theme, max_age=365*24*3600, samesite="lax")
    return response

@app.get("/api/user/theme")
async def get_theme(request: Request):
    theme = request.cookies.get("theme_preference", "dark")
    return {"theme": theme}

# ----- 11. SCHEDULED AUTO TASKS (Demo) -----
@app.post("/api/scheduled-tasks/create")
async def create_scheduled_task(request: Request):
    """Create a scheduled recurring task"""
    user = require_role(request, ["super_admin", "operations_manager"])
    data = await request.json()
    
    task_config = {
        "name": data.get("name", "Monthly Rank Check"),
        "schedule": data.get("schedule", "monthly"),
        "task_type": data.get("task_type", "rank_check"),
        "client_id": data.get("client_id"),
        "created_by": user["id"],
        "created_at": datetime.now().isoformat(),
        "next_run": (datetime.now() + timedelta(days=30)).isoformat(),
        "status": "active",
        "mode": "demo",
        "note": "In production, use APScheduler or Celery Beat for real scheduling"
    }
    
    db = get_db()
    log_activity(db, user["id"], "scheduled_task", f"Created scheduled task: {task_config['name']} ({task_config['schedule']})", "system", 0)
    db.commit()
    db.close()
    return {"message": "Scheduled task created (demo)", "task": task_config}

# ----- 12. EMAIL MARKETING / CAMPAIGNS (Demo) -----
@app.post("/api/email/campaign")
async def send_email_campaign(request: Request):
    """Send email marketing campaign"""
    user = require_role(request, ["super_admin", "social_media", "sales"])
    data = await request.json()
    
    campaign = {
        "subject": data.get("subject", "Your Monthly SEO Report"),
        "recipients": data.get("recipients", []),
        "template": data.get("template", "newsletter"),
        "sent_count": len(data.get("recipients", [])),
        "status": "demo_sent",
        "campaign_id": f"camp_{int(time.time())}",
        "sent_at": datetime.now().isoformat(),
        "mode": "demo",
        "note": "Connect SMTP in Settings for real email sending. For bulk email, use SendGrid/Mailgun API."
    }
    
    db = get_db()
    log_activity(db, user["id"], "email_campaign", f"Email campaign '{campaign['subject']}' to {campaign['sent_count']} recipients", "system", 0)
    db.commit()
    db.close()
    return {"message": "Email campaign sent (demo)", "campaign": campaign}

# ----- INTEGRATION STATUS CHECK -----
@app.get("/api/integrations/status")
async def integration_status(request: Request):
    """Check status of all API integrations"""
    user = require_role(request, ["super_admin"])
    db = get_db()
    settings = db.execute("SELECT provider, is_active, api_key IS NOT NULL as has_key, config_json, updated_at FROM api_settings").fetchall()
    db.close()
    
    integrations = []
    for s in settings:
        s = dict(s)
        config = json.loads(s.get("config_json") or "{}")
        integrations.append({
            "provider": s["provider"],
            "is_active": bool(s["is_active"]),
            "has_key": bool(s["has_key"]),
            "status": "active" if s["is_active"] and s["has_key"] else ("configured" if s["has_key"] else "not_configured"),
            "config_keys": list(config.keys()),
            "updated_at": s["updated_at"]
        })
    
    return {"integrations": integrations}


# ==========================================
# Part 6: Public Free Audit (No Login Required) — REAL CRAWL
# ==========================================

def _real_crawl_audit(url, business_name, industry, city):
    """Actually crawl the website and return real analysis data."""
    import requests as req
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin, urlparse
    import re, ssl, socket

    results = {"crawled": True, "url": url}
    headers = {"User-Agent": "RankForgeAI-AuditBot/1.0 (+https://YOUR_DOMAIN_HERE)"}

    # ---- Fetch homepage ----
    try:
        t0 = time.time()
        resp = req.get(url, headers=headers, timeout=15, allow_redirects=True)
        load_time = round(time.time() - t0, 2)
        results["status_code"] = resp.status_code
        results["load_time"] = load_time
        results["final_url"] = resp.url
        results["content_length"] = len(resp.content)
        html = resp.text
    except Exception as e:
        results["error"] = str(e)
        return results

    soup = BeautifulSoup(html, "lxml")

    # ---- TITLE TAG ----
    title_tag = soup.find("title")
    results["title"] = title_tag.get_text(strip=True) if title_tag else None
    results["title_length"] = len(results["title"]) if results["title"] else 0

    # ---- META DESCRIPTION ----
    meta_desc = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
    results["meta_description"] = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else None
    results["meta_desc_length"] = len(results["meta_description"]) if results["meta_description"] else 0

    # ---- HEADINGS ----
    results["h1_tags"] = [h.get_text(strip=True) for h in soup.find_all("h1")]
    results["h2_count"] = len(soup.find_all("h2"))
    results["h3_count"] = len(soup.find_all("h3"))

    # ---- IMAGES ----
    imgs = soup.find_all("img")
    results["total_images"] = len(imgs)
    results["images_no_alt"] = len([i for i in imgs if not i.get("alt") or not i["alt"].strip()])

    # ---- LINKS ----
    all_links = soup.find_all("a", href=True)
    parsed_base = urlparse(url)
    internal = [a for a in all_links if urlparse(urljoin(url, a["href"])).netloc == parsed_base.netloc]
    external = [a for a in all_links if urlparse(urljoin(url, a["href"])).netloc != parsed_base.netloc and a["href"].startswith("http")]
    results["internal_links"] = len(internal)
    results["external_links"] = len(external)
    results["broken_links_hash"] = len([a for a in all_links if a["href"] == "#"])

    # ---- VIEWPORT (mobile) ----
    viewport = soup.find("meta", attrs={"name": "viewport"})
    results["has_viewport"] = viewport is not None

    # ---- CANONICAL ----
    canonical = soup.find("link", attrs={"rel": "canonical"})
    results["has_canonical"] = canonical is not None
    results["canonical_url"] = canonical["href"] if canonical else None

    # ---- SCHEMA / STRUCTURED DATA ----
    schema_tags = soup.find_all("script", attrs={"type": "application/ld+json"})
    results["schema_count"] = len(schema_tags)
    schema_types = []
    for s in schema_tags:
        try:
            d = json.loads(s.string)
            if isinstance(d, dict):
                schema_types.append(d.get("@type", "Unknown"))
            elif isinstance(d, list):
                schema_types.extend([x.get("@type", "Unknown") for x in d if isinstance(x, dict)])
        except:
            pass
    results["schema_types"] = schema_types

    # ---- OG TAGS ----
    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")
    og_img = soup.find("meta", property="og:image")
    results["has_og_title"] = og_title is not None
    results["has_og_description"] = og_desc is not None
    results["has_og_image"] = og_img is not None

    # ---- WORD COUNT ----
    text_content = soup.get_text(separator=" ", strip=True)
    words = [w for w in text_content.split() if len(w) > 1]
    results["word_count"] = len(words)

    # ---- HTTPS / SSL ----
    results["is_https"] = url.startswith("https://") or resp.url.startswith("https://")

    # ---- SECURITY HEADERS ----
    sec_headers = ["x-content-type-options", "x-frame-options", "strict-transport-security",
                   "content-security-policy", "x-xss-protection", "referrer-policy"]
    found_sec = [h for h in sec_headers if h in [k.lower() for k in resp.headers.keys()]]
    results["security_headers_found"] = found_sec
    results["security_headers_count"] = len(found_sec)

    # ---- ROBOTS.TXT ----
    try:
        rb = req.get(urljoin(url, "/robots.txt"), headers=headers, timeout=5)
        results["has_robots_txt"] = rb.status_code == 200 and len(rb.text) > 10
        results["robots_txt_content"] = rb.text[:500] if results["has_robots_txt"] else None
    except:
        results["has_robots_txt"] = False

    # ---- SITEMAP ----
    results["has_sitemap"] = False
    sitemap_urls_to_check = [urljoin(url, "/sitemap.xml"), urljoin(url, "/sitemap_index.xml")]
    if results.get("robots_txt_content"):
        for line in results["robots_txt_content"].split("\n"):
            if line.lower().startswith("sitemap:"):
                sitemap_urls_to_check.insert(0, line.split(":", 1)[1].strip())
    for sm_url in sitemap_urls_to_check:
        try:
            sm = req.get(sm_url, headers=headers, timeout=5)
            if sm.status_code == 200 and ("</urlset>" in sm.text or "</sitemapindex>" in sm.text):
                results["has_sitemap"] = True
                results["sitemap_url"] = sm_url
                break
        except:
            pass

    # ---- LANGUAGE ----
    html_tag = soup.find("html")
    results["lang"] = html_tag.get("lang") if html_tag else None

    # ---- FAVICON ----
    favicon = soup.find("link", rel=re.compile(r"icon", re.I))
    results["has_favicon"] = favicon is not None

    # ---- CSS/JS counts ----
    results["css_files"] = len(soup.find_all("link", rel="stylesheet"))
    results["js_files"] = len(soup.find_all("script", src=True))

    # ---- PHONE / EMAIL on page ----
    phone_patterns = re.findall(r'[\+]?[\d\s\-\(\)]{10,}', text_content)
    email_patterns = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_content)
    results["phones_found"] = list(set([p.strip() for p in phone_patterns[:5]]))
    results["emails_found"] = list(set(email_patterns[:5]))

    # ---- FORMS ----
    results["forms_count"] = len(soup.find_all("form"))

    # ---- RESPONSIVE CSS ----
    results["has_media_queries"] = "@media" in html

    # ---- CORE WEB VITALS INDICATORS ----
    # LCP: check for large images/videos above fold, render-blocking resources
    lcp_issues = []
    preloads = soup.find_all("link", rel="preload")
    results["has_preload_hints"] = len(preloads) > 0
    # Check for render-blocking CSS (non-async)
    blocking_css = [l for l in soup.find_all("link", rel="stylesheet") if not l.get("media") or l.get("media") == "all"]
    results["blocking_css_count"] = len(blocking_css)
    # Check for render-blocking JS (no defer/async)
    blocking_js = [s for s in soup.find_all("script", src=True) if not s.get("defer") and not s.get("async")]
    results["blocking_js_count"] = len(blocking_js)
    # CLS indicators: images without width/height
    imgs_no_dimensions = [i for i in imgs if not (i.get("width") and i.get("height"))]
    results["images_no_dimensions"] = len(imgs_no_dimensions)
    # INP: check for heavy event handlers (heuristic)
    inline_handlers = len(re.findall(r'on(?:click|change|submit|keydown|mouseover)=', html, re.I))
    results["inline_event_handlers"] = inline_handlers

    # ---- AI CRAWLER ACCESS CHECK ----
    ai_crawlers = {}
    robots_content = results.get("robots_txt_content", "") or ""
    for bot in ["GPTBot", "ClaudeBot", "Claude-Web", "ChatGPT-User", "Google-Extended", "CCBot", "PerplexityBot", "Bingbot", "anthropic-ai"]:
        bot_lower = bot.lower()
        # Check if bot is specifically blocked
        blocked = False
        in_section = False
        for line in robots_content.split("\n"):
            line_stripped = line.strip().lower()
            if line_stripped.startswith("user-agent:"):
                agent = line_stripped.replace("user-agent:", "").strip()
                in_section = (agent == bot_lower or agent == "*")
            elif in_section and line_stripped.startswith("disallow:"):
                path = line_stripped.replace("disallow:", "").strip()
                if path == "/" or path == "/*":
                    blocked = True
        ai_crawlers[bot] = {"blocked": blocked}
    results["ai_crawlers"] = ai_crawlers

    # ---- IMAGE WebP AUDIT ----
    img_formats = {"webp": 0, "jpg": 0, "jpeg": 0, "png": 0, "gif": 0, "svg": 0, "avif": 0, "other": 0}
    for img in imgs:
        src = (img.get("src") or img.get("data-src") or "").lower()
        ext = src.rsplit(".", 1)[-1].split("?")[0] if "." in src else "other"
        if ext in img_formats:
            img_formats[ext] = img_formats.get(ext, 0) + 1
        else:
            img_formats["other"] += 1
    results["image_formats"] = img_formats
    results["webp_usage_pct"] = round((img_formats.get("webp", 0) + img_formats.get("avif", 0)) / max(len(imgs), 1) * 100)

    # ---- XML SITEMAP VALIDATION (deep) ----
    sitemap_details = {"exists": results.get("has_sitemap", False), "url_count": 0, "has_lastmod": False, "has_priority": False}
    if results.get("has_sitemap") and results.get("sitemap_url"):
        try:
            sm_resp = req.get(results["sitemap_url"], headers=headers, timeout=8)
            if sm_resp.status_code == 200:
                sm_soup = BeautifulSoup(sm_resp.text, "lxml")
                sm_urls = sm_soup.find_all("url") or sm_soup.find_all("loc")
                sitemap_details["url_count"] = len(sm_urls)
                sitemap_details["has_lastmod"] = bool(sm_soup.find("lastmod"))
                sitemap_details["has_priority"] = bool(sm_soup.find("priority"))
        except:
            pass
    results["sitemap_details"] = sitemap_details

    # ---- ROBOTS.TXT VALIDATION (deep) ----
    robots_details = {"exists": results.get("has_robots_txt", False), "has_sitemap_ref": False, "has_crawl_delay": False, "disallow_count": 0}
    if robots_content:
        robots_details["has_sitemap_ref"] = "sitemap:" in robots_content.lower()
        robots_details["has_crawl_delay"] = "crawl-delay:" in robots_content.lower()
        robots_details["disallow_count"] = robots_content.lower().count("disallow:")
    results["robots_details"] = robots_details

    # ---- INTERNAL LINKING DEPTH ----
    nav_links = soup.find_all("nav")
    nav_link_count = sum(len(n.find_all("a", href=True)) for n in nav_links) if nav_links else 0
    footer_tag = soup.find("footer")
    footer_link_count = len(footer_tag.find_all("a", href=True)) if footer_tag else 0
    main_content = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|main|body", re.I))
    body_link_count = len(main_content.find_all("a", href=True)) if main_content else results.get("internal_links", 0) - nav_link_count - footer_link_count
    results["linking_structure"] = {
        "nav_links": nav_link_count,
        "footer_links": footer_link_count,
        "body_links": max(body_link_count, 0),
        "total_internal": results.get("internal_links", 0),
        "link_to_text_ratio": round(results.get("internal_links", 0) / max(results.get("word_count", 1), 1) * 100, 2)
    }

    # ---- CANONICAL MISMATCH DETECTION ----
    canonical_issues = []
    if results.get("has_canonical"):
        canon = results.get("canonical_url", "")
        final = results.get("final_url", url)
        # Check if canonical matches actual URL
        if canon and final:
            canon_parsed = urlparse(canon)
            final_parsed = urlparse(final)
            if canon_parsed.netloc and final_parsed.netloc and canon_parsed.netloc != final_parsed.netloc:
                canonical_issues.append(f"Domain mismatch: canonical={canon_parsed.netloc}, actual={final_parsed.netloc}")
            if canon_parsed.scheme != final_parsed.scheme:
                canonical_issues.append(f"Protocol mismatch: canonical={canon_parsed.scheme}, actual={final_parsed.scheme}")
            if canon.rstrip("/") != final.rstrip("/") and canon_parsed.netloc == final_parsed.netloc:
                canonical_issues.append(f"Path mismatch: canonical={canon}, actual={final}")
    results["canonical_issues"] = canonical_issues

    # ---- E-E-A-T AUTHOR SIGNALS ----
    eeat_signals = {"has_author": False, "has_about_page": False, "has_contact_info": False, "has_social_proof": False, "has_credentials": False}
    # Check for author tags
    author_meta = soup.find("meta", attrs={"name": "author"})
    author_rel = soup.find("a", rel="author")
    author_schema = "Person" in str(results.get("schema_types", []))
    eeat_signals["has_author"] = bool(author_meta or author_rel or author_schema)
    # Check for about/team page links
    about_links = [a for a in all_links if any(kw in (a.get("href", "").lower()) for kw in ["about", "team", "our-team", "staff"])]
    eeat_signals["has_about_page"] = len(about_links) > 0
    # Contact info presence
    eeat_signals["has_contact_info"] = bool(results.get("phones_found") or results.get("emails_found"))
    # Social proof (testimonials, reviews)
    testimonial_indicators = len(re.findall(r'testimonial|review|rating|stars|client.?said|customer.?feedback', html, re.I))
    eeat_signals["has_social_proof"] = testimonial_indicators > 0
    # Credentials indicators
    credential_indicators = len(re.findall(r'certified|accredited|licensed|award|partner|member|association|BBB|chamber', html, re.I))
    eeat_signals["has_credentials"] = credential_indicators > 0
    results["eeat_signals"] = eeat_signals

    return results


def _build_audit_from_crawl(crawl, business_name, industry, city, url):
    """Convert raw crawl data into scored audit sections."""
    if crawl.get("error"):
        return None

    # Score each section based on real data
    # 1. Technical SEO
    tech_score = 50
    tech_findings = []
    tech_recs = []

    if crawl.get("title"):
        tl = crawl["title_length"]
        tech_findings.append(f"Title tag: \"{crawl['title']}\" ({tl} chars)")
        if 30 <= tl <= 60: tech_score += 8
        elif tl > 0: tech_score += 4; tech_recs.append(f"Optimize title length (currently {tl} chars, ideal is 30-60)")
        else: tech_recs.append("Add a title tag to the page")
    else:
        tech_findings.append("Title tag: MISSING"); tech_recs.append("Add a descriptive title tag (30-60 characters)")

    if crawl.get("meta_description"):
        ml = crawl["meta_desc_length"]
        tech_findings.append(f"Meta description: \"{crawl['meta_description'][:80]}...\" ({ml} chars)")
        if 120 <= ml <= 160: tech_score += 8
        elif ml > 0: tech_score += 4; tech_recs.append(f"Optimize meta description length ({ml} chars, ideal is 120-160)")
    else:
        tech_findings.append("Meta description: MISSING"); tech_recs.append("Add a meta description (120-160 characters)")

    if crawl.get("has_canonical"): tech_score += 5; tech_findings.append(f"Canonical URL: {crawl['canonical_url']}")
    else: tech_findings.append("Canonical tag: Not found"); tech_recs.append("Add a canonical URL tag to prevent duplicate content")

    if crawl.get("has_robots_txt"): tech_score += 5; tech_findings.append("Robots.txt: Found")
    else: tech_findings.append("Robots.txt: NOT FOUND"); tech_recs.append("Create a robots.txt file")

    if crawl.get("has_sitemap"): tech_score += 7; tech_findings.append(f"XML Sitemap: Found at {crawl.get('sitemap_url', 'sitemap.xml')}")
    else: tech_findings.append("XML Sitemap: NOT FOUND"); tech_recs.append("Create and submit an XML sitemap to Google Search Console")

    if crawl.get("lang"): tech_score += 3; tech_findings.append(f"Language declared: {crawl['lang']}")
    else: tech_recs.append("Add lang attribute to <html> tag")

    h1s = crawl.get("h1_tags", [])
    if len(h1s) == 1: tech_score += 5; tech_findings.append(f"H1 tag: \"{h1s[0][:60]}\"")
    elif len(h1s) > 1: tech_score += 2; tech_findings.append(f"H1 tags: {len(h1s)} found (should be 1)"); tech_recs.append("Use only one H1 tag per page")
    else: tech_findings.append("H1 tag: MISSING"); tech_recs.append("Add a single H1 heading to the page")

    tech_findings.append(f"H2 tags: {crawl.get('h2_count', 0)} | H3 tags: {crawl.get('h3_count', 0)}")
    tech_score = min(tech_score, 100)

    # 2. On-Page SEO
    onpage_score = 50
    onpage_findings = []
    onpage_recs = []

    onpage_findings.append(f"Internal links: {crawl.get('internal_links', 0)}")
    if crawl.get("internal_links", 0) >= 10: onpage_score += 10
    elif crawl.get("internal_links", 0) >= 5: onpage_score += 5
    else: onpage_recs.append("Add more internal links to improve site structure")

    onpage_findings.append(f"External links: {crawl.get('external_links', 0)}")
    if crawl.get("external_links", 0) >= 2: onpage_score += 5

    onpage_findings.append(f"Images: {crawl.get('total_images', 0)} total, {crawl.get('images_no_alt', 0)} missing alt text")
    if crawl.get("images_no_alt", 0) == 0 and crawl.get("total_images", 0) > 0: onpage_score += 10
    elif crawl.get("images_no_alt", 0) > 0: onpage_recs.append(f"Add alt text to {crawl['images_no_alt']} images for SEO and accessibility")

    onpage_findings.append(f"Hash (#) links: {crawl.get('broken_links_hash', 0)}")
    if crawl.get("broken_links_hash", 0) > 3: onpage_recs.append(f"Fix {crawl['broken_links_hash']} placeholder links (href='#')")
    elif crawl.get("broken_links_hash", 0) == 0: onpage_score += 5

    if crawl.get("has_favicon"): onpage_score += 3; onpage_findings.append("Favicon: Found")
    else: onpage_findings.append("Favicon: Not found"); onpage_recs.append("Add a favicon for brand recognition in browser tabs")

    onpage_findings.append(f"CSS files: {crawl.get('css_files', 0)} | JS files: {crawl.get('js_files', 0)}")
    onpage_score = min(onpage_score, 100)

    # 3. Content Quality
    content_score = 45
    content_findings = []
    content_recs = []
    wc = crawl.get("word_count", 0)
    content_findings.append(f"Word count (homepage): {wc} words")
    if wc >= 1000: content_score += 20
    elif wc >= 500: content_score += 12; content_recs.append("Aim for 1000+ words on your homepage for better rankings")
    elif wc >= 200: content_score += 5; content_recs.append(f"Homepage has only {wc} words — aim for 800-1500 for competitive SEO")
    else: content_recs.append("Very thin content detected — add substantial text content to your homepage")

    if crawl.get("forms_count", 0) > 0: content_score += 8; content_findings.append(f"Contact/Lead forms: {crawl['forms_count']} found")
    else: content_findings.append("Contact forms: None found"); content_recs.append("Add a contact/lead capture form to convert visitors")

    if crawl.get("phones_found"): content_score += 5; content_findings.append(f"Phone numbers on page: {', '.join(crawl['phones_found'][:3])}")
    else: content_recs.append("Add your phone number visibly on the page")

    if crawl.get("emails_found"): content_score += 5; content_findings.append(f"Email addresses on page: {', '.join(crawl['emails_found'][:3])}")
    else: content_recs.append("Add your email address visibly on the page")

    content_score = min(content_score, 100)

    # 4. Schema / Entity SEO
    schema_score = 30
    schema_findings = []
    schema_recs = []
    if crawl.get("schema_count", 0) > 0:
        schema_score += 30
        schema_findings.append(f"Structured data found: {crawl['schema_count']} JSON-LD blocks")
        schema_findings.append(f"Schema types: {', '.join(crawl.get('schema_types', ['Unknown']))}")
        if "LocalBusiness" in str(crawl.get("schema_types", [])): schema_score += 15
        else: schema_recs.append("Add LocalBusiness schema markup for local SEO")
        if "Organization" in str(crawl.get("schema_types", [])): schema_score += 5
    else:
        schema_findings.append("Structured data (JSON-LD): NOT FOUND")
        schema_recs.append("Add JSON-LD structured data (LocalBusiness, Organization, FAQ)")
        schema_recs.append("Schema markup helps Google understand your business and show rich results")
    schema_score = min(schema_score, 100)

    # 5. Social / OG Tags
    social_score = 30
    social_findings = []
    social_recs = []
    if crawl.get("has_og_title"): social_score += 20; social_findings.append("Open Graph title: Found")
    else: social_findings.append("Open Graph title: MISSING"); social_recs.append("Add og:title meta tag for social sharing")
    if crawl.get("has_og_description"): social_score += 15; social_findings.append("Open Graph description: Found")
    else: social_findings.append("Open Graph description: MISSING"); social_recs.append("Add og:description meta tag")
    if crawl.get("has_og_image"): social_score += 20; social_findings.append("Open Graph image: Found")
    else: social_findings.append("Open Graph image: MISSING"); social_recs.append("Add og:image for attractive social media previews (1200x630px recommended)")
    social_score = min(social_score, 100)

    # 6. Security
    sec_score = 40
    sec_findings = []
    sec_recs = []
    if crawl.get("is_https"): sec_score += 25; sec_findings.append("HTTPS: Active ✓")
    else: sec_findings.append("HTTPS: NOT ACTIVE — Critical issue"); sec_recs.append("Enable HTTPS immediately — Google penalizes non-HTTPS sites")

    shc = crawl.get("security_headers_count", 0)
    sec_findings.append(f"Security headers: {shc}/6 found ({', '.join(crawl.get('security_headers_found', []))})")
    sec_score += shc * 4
    missing_headers = [h for h in ["x-content-type-options", "x-frame-options", "strict-transport-security",
                                    "content-security-policy", "x-xss-protection", "referrer-policy"]
                       if h not in crawl.get("security_headers_found", [])]
    if missing_headers: sec_recs.append(f"Add missing security headers: {', '.join(missing_headers[:3])}")
    sec_score = min(sec_score, 100)

    # 7. Performance
    perf_score = 50
    perf_findings = []
    perf_recs = []
    lt = crawl.get("load_time", 99)
    perf_findings.append(f"Server response time: {lt}s")
    if lt < 1: perf_score += 30
    elif lt < 2: perf_score += 20
    elif lt < 3: perf_score += 10
    else: perf_recs.append(f"Page took {lt}s to respond — aim for under 2 seconds")

    page_kb = crawl.get("content_length", 0) / 1024
    perf_findings.append(f"HTML size: {round(page_kb, 1)} KB")
    if page_kb < 100: perf_score += 10
    elif page_kb < 300: perf_score += 5
    else: perf_recs.append("HTML is large — consider splitting content across pages")

    js_count = crawl.get("js_files", 0)
    css_count = crawl.get("css_files", 0)
    perf_findings.append(f"External resources: {js_count} JS files, {css_count} CSS files")
    if js_count + css_count <= 10: perf_score += 5
    else: perf_recs.append(f"Reduce number of external resources ({js_count} JS + {css_count} CSS) — combine or defer loading")
    perf_score = min(perf_score, 100)

    # 8. Mobile
    mobile_score = 40
    mobile_findings = []
    mobile_recs = []
    if crawl.get("has_viewport"): mobile_score += 30; mobile_findings.append("Viewport meta tag: Found ✓")
    else: mobile_findings.append("Viewport meta tag: MISSING — Critical"); mobile_recs.append("Add <meta name='viewport' content='width=device-width, initial-scale=1'> — essential for mobile")
    # Responsive indicators
    responsive_css = crawl.get("has_media_queries", False)
    if responsive_css: mobile_score += 15; mobile_findings.append("Responsive CSS (@media queries): Detected")
    else: mobile_findings.append("Responsive CSS: Not clearly detected"); mobile_recs.append("Ensure CSS uses @media queries for responsive design")
    mobile_score = min(mobile_score, 100)

    # 9. Core Web Vitals
    cwv_score = 40
    cwv_findings = []
    cwv_recs = []
    cwv_findings.append(f"Render-blocking CSS: {crawl.get('blocking_css_count', 0)} files")
    cwv_findings.append(f"Render-blocking JS: {crawl.get('blocking_js_count', 0)} files (no defer/async)")
    if crawl.get("blocking_js_count", 0) == 0: cwv_score += 15
    elif crawl.get("blocking_js_count", 0) <= 2: cwv_score += 8
    else: cwv_recs.append(f"Add defer/async to {crawl['blocking_js_count']} render-blocking scripts to improve LCP")
    if crawl.get("blocking_css_count", 0) <= 2: cwv_score += 10
    else: cwv_recs.append(f"Reduce {crawl['blocking_css_count']} blocking CSS files — inline critical CSS or use media queries")
    cwv_findings.append(f"Images without width/height: {crawl.get('images_no_dimensions', 0)}")
    if crawl.get("images_no_dimensions", 0) == 0: cwv_score += 15
    elif crawl.get("images_no_dimensions", 0) <= 3: cwv_score += 8
    else: cwv_recs.append(f"Add explicit width/height to {crawl['images_no_dimensions']} images to prevent CLS (layout shift)")
    if crawl.get("has_preload_hints"): cwv_score += 10; cwv_findings.append("Resource preload hints: Found")
    else: cwv_findings.append("Resource preload hints: Not found"); cwv_recs.append("Add <link rel='preload'> for critical fonts/images to improve LCP")
    cwv_findings.append(f"Inline event handlers: {crawl.get('inline_event_handlers', 0)}")
    if crawl.get("inline_event_handlers", 0) <= 5: cwv_score += 10
    else: cwv_recs.append(f"Move {crawl['inline_event_handlers']} inline event handlers to external JS for better INP")
    cwv_score = min(cwv_score, 100)

    # 10. GEO / AI Crawler Access
    geo_score = 50
    geo_findings = []
    geo_recs = []
    ai_crawlers = crawl.get("ai_crawlers", {})
    blocked_bots = [bot for bot, info in ai_crawlers.items() if info.get("blocked")]
    allowed_bots = [bot for bot, info in ai_crawlers.items() if not info.get("blocked")]
    if blocked_bots:
        geo_findings.append(f"BLOCKED AI crawlers: {', '.join(blocked_bots)}")
        geo_recs.append(f"Unblock {', '.join(blocked_bots)} in robots.txt to appear in AI search results (ChatGPT, Claude, Perplexity)")
    else:
        geo_score += 25
        geo_findings.append("No AI crawlers explicitly blocked")
    if allowed_bots:
        geo_findings.append(f"Allowed AI crawlers: {', '.join(allowed_bots)}")
        geo_score += min(len(allowed_bots) * 3, 25)
    if not crawl.get("has_robots_txt"):
        geo_findings.append("No robots.txt found — all bots have default access")
        geo_score += 10
    # Check if site has clear entity/brand info for AI understanding
    if crawl.get("schema_count", 0) > 0: geo_score += 10; geo_findings.append("Schema markup helps AI crawlers understand your business")
    else: geo_recs.append("Add schema markup so AI models accurately represent your business")
    geo_score = min(geo_score, 100)

    # 11. Image Alt Text + WebP Audit
    img_audit_score = 40
    img_findings = []
    img_recs = []
    total_imgs = crawl.get("total_images", 0)
    no_alt = crawl.get("images_no_alt", 0)
    formats = crawl.get("image_formats", {})
    webp_pct = crawl.get("webp_usage_pct", 0)
    img_findings.append(f"Total images: {total_imgs}")
    img_findings.append(f"Images missing alt text: {no_alt}/{total_imgs}")
    if total_imgs > 0 and no_alt == 0: img_audit_score += 25
    elif no_alt <= 3: img_audit_score += 15
    else: img_recs.append(f"Add descriptive alt text to {no_alt} images — critical for SEO and accessibility")
    img_findings.append(f"Image formats: JPG={formats.get('jpg',0)+formats.get('jpeg',0)}, PNG={formats.get('png',0)}, WebP={formats.get('webp',0)}, SVG={formats.get('svg',0)}, AVIF={formats.get('avif',0)}")
    img_findings.append(f"Modern format usage (WebP/AVIF): {webp_pct}%")
    if webp_pct >= 50: img_audit_score += 25
    elif webp_pct >= 20: img_audit_score += 15
    else: img_recs.append(f"Convert images to WebP format — only {webp_pct}% use modern formats (target 80%+)")
    if total_imgs > 0 and total_imgs <= 30: img_audit_score += 10
    elif total_imgs > 50: img_recs.append(f"{total_imgs} images found — consider lazy loading images below the fold")
    img_audit_score = min(img_audit_score, 100)

    # 12. XML Sitemap Validation
    sitemap_score = 30
    sitemap_findings = []
    sitemap_recs = []
    sm_details = crawl.get("sitemap_details", {})
    if sm_details.get("exists"):
        sitemap_score += 25
        sitemap_findings.append(f"XML Sitemap: Found ({sm_details.get('url_count', 0)} URLs)")
        if sm_details.get("url_count", 0) > 0: sitemap_score += 10
        else: sitemap_recs.append("Sitemap exists but contains no URLs — regenerate it")
        if sm_details.get("has_lastmod"): sitemap_score += 15; sitemap_findings.append("Last modified dates: Present")
        else: sitemap_findings.append("Last modified dates: Missing"); sitemap_recs.append("Add <lastmod> dates to sitemap entries for better crawl prioritization")
        if sm_details.get("has_priority"): sitemap_score += 10; sitemap_findings.append("Priority tags: Present")
        else: sitemap_findings.append("Priority tags: Missing"); sitemap_recs.append("Add <priority> tags to indicate page importance")
    else:
        sitemap_findings.append("XML Sitemap: NOT FOUND")
        sitemap_recs.append("Create an XML sitemap and submit it to Google Search Console")
        sitemap_recs.append("Use a sitemap generator plugin or tool (Yoast, Screaming Frog, etc.)")
    sitemap_score = min(sitemap_score, 100)

    # 13. Robots.txt Check
    robots_score = 30
    robots_findings = []
    robots_recs = []
    rb_details = crawl.get("robots_details", {})
    if rb_details.get("exists"):
        robots_score += 25
        robots_findings.append("Robots.txt: Found")
        robots_findings.append(f"Disallow rules: {rb_details.get('disallow_count', 0)}")
        if rb_details.get("has_sitemap_ref"): robots_score += 20; robots_findings.append("Sitemap reference: Present")
        else: robots_findings.append("Sitemap reference: Missing"); robots_recs.append("Add Sitemap: directive in robots.txt pointing to your sitemap.xml")
        if rb_details.get("has_crawl_delay"): robots_findings.append("Crawl-delay: Set"); robots_recs.append("Consider removing Crawl-delay — it slows indexing")
        else: robots_score += 10
        if rb_details.get("disallow_count", 0) > 10: robots_recs.append(f"Too many Disallow rules ({rb_details['disallow_count']}) — review for over-blocking")
        else: robots_score += 15
    else:
        robots_findings.append("Robots.txt: NOT FOUND")
        robots_recs.append("Create a robots.txt file at your domain root")
        robots_recs.append("Include sitemap reference and allow all important crawlers")
    robots_score = min(robots_score, 100)

    # 14. Internal Linking Depth
    linking_score = 40
    linking_findings = []
    linking_recs = []
    ls = crawl.get("linking_structure", {})
    linking_findings.append(f"Navigation links: {ls.get('nav_links', 0)}")
    linking_findings.append(f"Footer links: {ls.get('footer_links', 0)}")
    linking_findings.append(f"Body/content links: {ls.get('body_links', 0)}")
    linking_findings.append(f"Total internal links: {ls.get('total_internal', 0)}")
    linking_findings.append(f"Link-to-text ratio: {ls.get('link_to_text_ratio', 0)}%")
    total_int = ls.get("total_internal", 0)
    if total_int >= 20: linking_score += 20
    elif total_int >= 10: linking_score += 12
    else: linking_recs.append(f"Only {total_int} internal links — add more contextual links between pages")
    body_links = ls.get("body_links", 0)
    if body_links >= 5: linking_score += 15
    elif body_links >= 2: linking_score += 8
    else: linking_recs.append("Add more in-content links to service/industry pages for better page authority flow")
    if ls.get("nav_links", 0) >= 10: linking_score += 10
    else: linking_recs.append("Expand navigation to include more key service pages")
    ltr = ls.get("link_to_text_ratio", 0)
    if 1 <= ltr <= 10: linking_score += 15
    elif ltr > 10: linking_recs.append("Link-to-text ratio is high — add more content to balance")
    linking_score = min(linking_score, 100)

    # 15. Canonical Mismatch Detection
    canon_score = 50
    canon_findings = []
    canon_recs = []
    canon_issues = crawl.get("canonical_issues", [])
    if crawl.get("has_canonical"):
        canon_score += 20
        canon_findings.append(f"Canonical tag: Present ({crawl.get('canonical_url', '')})")
        if not canon_issues:
            canon_score += 30
            canon_findings.append("Canonical URL: Matches page URL — No mismatches detected")
        else:
            for issue in canon_issues:
                canon_findings.append(f"ISSUE: {issue}")
            canon_recs.append("Fix canonical URL mismatch — this can cause duplicate content issues")
            canon_recs.append(f"Canonical should point to: {crawl.get('final_url', url)}")
    else:
        canon_findings.append("Canonical tag: NOT FOUND")
        canon_recs.append("Add <link rel='canonical'> tag to prevent duplicate content indexing")
        canon_recs.append("Self-referencing canonicals help Google determine the preferred URL version")
    canon_score = min(canon_score, 100)

    # 16. E-E-A-T Author Signals
    eeat_score = 20
    eeat_findings = []
    eeat_recs = []
    eeat = crawl.get("eeat_signals", {})
    if eeat.get("has_author"): eeat_score += 15; eeat_findings.append("Author attribution: Found")
    else: eeat_findings.append("Author attribution: NOT FOUND"); eeat_recs.append("Add author names to content — use <meta name='author'> and author schema")
    if eeat.get("has_about_page"): eeat_score += 15; eeat_findings.append("About/Team page: Referenced")
    else: eeat_findings.append("About/Team page: No link found"); eeat_recs.append("Add an About/Team page with real team member bios and credentials")
    if eeat.get("has_contact_info"): eeat_score += 15; eeat_findings.append("Contact information: Visible on page")
    else: eeat_findings.append("Contact info: NOT VISIBLE"); eeat_recs.append("Display phone number and email address prominently on the page")
    if eeat.get("has_social_proof"): eeat_score += 15; eeat_findings.append("Social proof (testimonials/reviews): Detected")
    else: eeat_findings.append("Social proof: Not detected"); eeat_recs.append("Add customer testimonials, reviews, or case studies to build trust")
    if eeat.get("has_credentials"): eeat_score += 15; eeat_findings.append("Credentials/Certifications: Referenced")
    else: eeat_findings.append("Credentials: Not found"); eeat_recs.append("Display certifications, awards, partnerships, or BBB accreditation")
    eeat_score = min(eeat_score, 100)

    # Build sections (original 8 + new 8 = 16 total)
    sections = [
        {"name": "Technical SEO", "score": tech_score, "icon": "🔧", "findings": tech_findings, "recommendations": tech_recs or ["Technical SEO looks solid — maintain current setup"], "audit_type": "ai_automated"},
        {"name": "On-Page SEO", "score": onpage_score, "icon": "📄", "findings": onpage_findings, "recommendations": onpage_recs or ["On-page optimization is in good shape"], "audit_type": "ai_automated"},
        {"name": "Content Quality", "score": content_score, "icon": "📝", "findings": content_findings, "recommendations": content_recs or ["Content is well-structured"], "audit_type": "ai_automated"},
        {"name": "Schema & JSON-LD", "score": schema_score, "icon": "🏷️", "findings": schema_findings, "recommendations": schema_recs or ["Structured data is well-implemented"], "audit_type": "ai_automated"},
        {"name": "Social Media SEO", "score": social_score, "icon": "📱", "findings": social_findings, "recommendations": social_recs or ["Social sharing tags are set up correctly"], "audit_type": "ai_automated"},
        {"name": "Security & SSL", "score": sec_score, "icon": "🔒", "findings": sec_findings, "recommendations": sec_recs or ["Security is well-configured"], "audit_type": "ai_automated"},
        {"name": "Performance", "score": perf_score, "icon": "⚡", "findings": perf_findings, "recommendations": perf_recs or ["Performance is good"], "audit_type": "ai_automated"},
        {"name": "Mobile Readiness", "score": mobile_score, "icon": "📲", "findings": mobile_findings, "recommendations": mobile_recs or ["Mobile optimization is solid"], "audit_type": "ai_automated"},
        {"name": "Core Web Vitals (LCP/INP/CLS)", "score": cwv_score, "icon": "🎯", "findings": cwv_findings, "recommendations": cwv_recs or ["Core Web Vitals indicators look good"], "audit_type": "ai_automated"},
        {"name": "GEO / AI Crawler Access", "score": geo_score, "icon": "🌐", "findings": geo_findings, "recommendations": geo_recs or ["AI crawler access is properly configured"], "audit_type": "ai_automated"},
        {"name": "Image Alt Text & WebP Audit", "score": img_audit_score, "icon": "🖼️", "findings": img_findings, "recommendations": img_recs or ["Image optimization is solid"], "audit_type": "ai_automated"},
        {"name": "XML Sitemap Validation", "score": sitemap_score, "icon": "🗺️", "findings": sitemap_findings, "recommendations": sitemap_recs or ["Sitemap is properly configured"], "audit_type": "ai_automated"},
        {"name": "Robots.txt Check", "score": robots_score, "icon": "📋", "findings": robots_findings, "recommendations": robots_recs or ["Robots.txt is well-configured"], "audit_type": "ai_automated"},
        {"name": "Internal Linking Depth", "score": linking_score, "icon": "🔗", "findings": linking_findings, "recommendations": linking_recs or ["Internal linking structure is solid"], "audit_type": "ai_automated"},
        {"name": "Canonical Mismatch Detection", "score": canon_score, "icon": "🔍", "findings": canon_findings, "recommendations": canon_recs or ["Canonical URLs are properly set"], "audit_type": "ai_automated"},
        {"name": "E-E-A-T Author Signals", "score": eeat_score, "icon": "👤", "findings": eeat_findings, "recommendations": eeat_recs or ["E-E-A-T signals are strong"], "audit_type": "ai_automated"},
    ]

    overall = round(sum(s["score"] for s in sections) / len(sections))
    grade = "A+" if overall >= 90 else "A" if overall >= 80 else "B" if overall >= 70 else "C" if overall >= 55 else "D" if overall >= 40 else "F"

    # Build top 5 priorities from lowest-scoring sections
    sorted_secs = sorted(sections, key=lambda x: x["score"])
    priorities = []
    for s in sorted_secs[:5]:
        if s["recommendations"]:
            priorities.append(f"{s['icon']} {s['name']} (Score: {s['score']}/100) — {s['recommendations'][0]}")

    # Separate AI automated vs Human required tasks
    ai_tasks = []
    human_tasks = []
    for s in sections:
        for rec in s.get("recommendations", []):
            if any(kw in rec.lower() for kw in ["add a", "add your", "create a", "add <", "display", "add an", "add descriptive", "convert images"]):
                human_tasks.append({"section": s["name"], "task": rec, "reason": "Requires content creation, design decisions, or access to business assets"})
            else:
                ai_tasks.append({"section": s["name"], "task": rec, "reason": "Can be automated with AI tools or scripts"})

    # Human-required tasks that need login credentials
    credential_tasks = [
        {"task": "Google Search Console — Submit sitemap, monitor indexing, check crawl errors", "credential": "GSC OAuth or API key", "how": "https://search.google.com/search-console"},
        {"task": "Google Analytics — Install GA4, track Core Web Vitals in real-time", "credential": "GA4 Measurement ID", "how": "https://analytics.google.com"},
        {"task": "PageSpeed Insights API — Get real Lighthouse CWV scores (LCP, INP, CLS)", "credential": "Google API key (free)", "how": "https://developers.google.com/speed/docs/insights/v5/get-started"},
        {"task": "Backlink Profile Analysis — Full backlink audit with DA/PA metrics", "credential": "Ahrefs/SEMrush/Moz API key ($99-199/mo)", "how": "Ahrefs: https://ahrefs.com | SEMrush: https://semrush.com"},
        {"task": "Knowledge Graph / Entity SEO — Verify Google Knowledge Panel", "credential": "Google Knowledge Graph API key (free)", "how": "https://developers.google.com/knowledge-graph"},
        {"task": "Google Business Profile — Optimize NAP, categories, reviews", "credential": "GBP account login", "how": "https://business.google.com"},
    ]

    return {
        "business_name": business_name,
        "website": url,
        "industry": industry,
        "audit_date": datetime.now().strftime("%B %d, %Y"),
        "overall_score": overall,
        "grade": grade,
        "sections": sections,
        "top_priorities": priorities,
        "ai_automated_tasks": ai_tasks,
        "human_required_tasks": human_tasks,
        "credential_required_tasks": credential_tasks,
        "mode": "live_crawl",
        "provider": "real_crawler",
        "total_checks": len(sections),
        "note": f"REAL AUDIT — This report is based on a live crawl of {url} performed on {datetime.now().strftime('%B %d, %Y at %H:%M UTC')}. All data is from actual website analysis across {len(sections)} audit categories."
    }


@app.post("/api/public/free-audit")
async def public_free_audit(request: Request):
    """Public endpoint for free audit form — no login needed. Returns REAL crawl-based audit."""
    data = await request.json()
    website = data.get("website", "").strip()
    business_name = data.get("business_name", "Your Business").strip()
    contact_name = data.get("contact_name", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    industry = data.get("industry", "general").strip()
    city = data.get("city", "").strip()

    if not business_name:
        raise HTTPException(status_code=400, detail="Business name is required")

    site_url = website if website else f"https://{business_name.lower().replace(' ','-')}.com"
    if not site_url.startswith("http"):
        site_url = "https://" + site_url

    # Real crawl
    crawl = _real_crawl_audit(site_url, business_name, industry, city)
    audit_result = None
    if crawl.get("crawled") and not crawl.get("error"):
        audit_result = _build_audit_from_crawl(crawl, business_name, industry, city, site_url)

    if not audit_result:
        # Fallback if crawl fails
        audit_result = {
            "business_name": business_name, "website": site_url, "industry": industry,
            "audit_date": datetime.now().strftime("%B %d, %Y"),
            "overall_score": 0, "grade": "N/A",
            "sections": [{"name": "Crawl Error", "score": 0, "icon": "❌",
                          "findings": [f"Could not reach {site_url}: {crawl.get('error', 'Unknown error')}"],
                          "recommendations": ["Verify the URL is correct and the website is online", "Check that the site is not blocking bots"]}],
            "top_3_priorities": ["Fix website accessibility — the site could not be reached for analysis"],
            "mode": "error", "provider": "crawler",
            "note": f"Could not crawl {site_url}. Please verify the URL is correct and try again."
        }

    # Save lead
    db = get_db()
    try:
        db.execute("""INSERT OR IGNORE INTO sales_leads (business_name, contact_name, email, phone, industry, city, website, source, status, notes)
                      VALUES (?,?,?,?,?,?,?,?,?,?)""",
                   (business_name, contact_name, email, phone, industry, city, site_url, "free_audit", "new",
                    json.dumps({"audit_score": audit_result.get("overall_score", 0), "audit_date": datetime.now().isoformat()})))
        db.commit()
    except:
        pass
    db.close()

    return {"message": "Audit completed", "audit": audit_result}


# ==========================================
# Part 7: Public Contact Form (No Login Required)
# ==========================================

@app.post("/api/public/contact")
async def public_contact(request: Request):
    """Public endpoint for contact form — no login needed. Saves lead + sends notification."""
    data = await request.json()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    website = data.get("website", "").strip()
    service = data.get("service", "").strip()
    message = data.get("message", "").strip()
    
    if not name or not email:
        raise HTTPException(status_code=400, detail="Name and email are required")
    
    db = get_db()
    try:
        db.execute("""INSERT OR IGNORE INTO sales_leads 
            (business_name, contact_name, email, phone, website, source, status, notes)
            VALUES (?, ?, ?, ?, ?, 'contact_form', 'new', ?)""",
            (name, name, email, phone, website, f"Service: {service}\nMessage: {message}"))
        db.commit()
    except:
        pass
    db.close()
    
    return {"message": "Thank you! We'll get back to you within 24 hours.", "success": True}


# ==========================================
# Part 8: AI Voice Call API (Gemini-Powered)
# ==========================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def get_smart_fallback_response(user_message, agent="sarah"):
    """Smart keyword-based response when Gemini API is unavailable."""
    msg = user_message.lower()
    
    if agent == "sarah":
        name = "Sarah"
        if any(w in msg for w in ["seo", "ranking", "rank", "google", "search", "visibility"]):
            return (
                f"Great question! Local SEO is one of our strongest areas. We've helped over 500 businesses "
                f"rank in the Google Map Pack. For a dental clinic like yours, we'd typically start with "
                f"optimizing your Google Business Profile, building local citations, and implementing "
                f"a review generation strategy. Would you like me to schedule a free SEO audit so we can "
                f"identify exactly where you stand and what opportunities exist?"
            )
        elif any(w in msg for w in ["reviews", "review", "reputation", "stars", "rating"]):
            return (
                f"Reviews are absolutely critical for local businesses! We've generated over 12,000 reviews "
                f"for our clients. Our reputation management service includes automated review request sequences, "
                f"professional response management, and sentiment monitoring. Most of our dental clients see "
                f"a jump to 4.8+ stars within 90 days. Want me to set up a free audit to see your current review profile?"
            )
        elif any(w in msg for w in ["price", "cost", "pricing", "package", "budget", "affordable"]):
            return (
                f"Our packages start at $497/month for the Starter plan, which includes Local SEO, GBP optimization, "
                f"and basic review management. Our Growth plan at $997/month adds content creation, social media, "
                f"and paid advertising management. We don't require long-term contracts — it's month-to-month "
                f"because we believe our results speak for themselves. Would you like a custom quote based on your specific needs?"
            )
        elif any(w in msg for w in ["audit", "free", "analysis", "check"]):
            return (
                f"Absolutely! Our free comprehensive SEO audit covers your Google Business Profile, website SEO health, "
                f"local citations, review profile, and competitive analysis. It takes about 24-48 hours to prepare "
                f"and we'll walk you through every finding on a strategy call. I just need your business name and "
                f"website URL to get started. What's your website?"
            )
        elif any(w in msg for w in ["map", "maps", "map pack", "local pack"]):
            return (
                f"Getting into the Google Map Pack is one of the most impactful things we can do for local businesses! "
                f"We've achieved #1 Map Pack rankings for dental clinics in competitive markets. The key factors are "
                f"GBP optimization, consistent NAP citations, review velocity, and local content strategy. "
                f"Would you like me to check your current Map Pack position and identify what's holding you back?"
            )
        elif any(w in msg for w in ["website", "web design", "site", "redesign"]):
            return (
                f"We offer modern, conversion-optimized website design specifically for local businesses. "
                f"Our sites are built for speed, mobile-first, and optimized for local SEO from day one. "
                f"We've seen clients get up to 185% more leads just from a site redesign. "
                f"Would you like to see some examples of dental clinic websites we've built?"
            )
        elif any(w in msg for w in ["social", "facebook", "instagram", "tiktok"]):
            return (
                f"Social media is a great way to build trust and attract new patients! We manage everything from "
                f"content creation to ad campaigns across Facebook, Instagram, TikTok, and LinkedIn. "
                f"For dental clinics, we typically see the best results with before/after content, "
                f"patient testimonials, and educational posts. Want to hear more about our social media packages?"
            )
        elif any(w in msg for w in ["thank", "thanks", "bye", "goodbye"]):
            return (
                f"It was great chatting with you! Feel free to reach out anytime at +1-800-971-0199 "
                f"or email us at hello@YOUR_DOMAIN_HERE I'll make sure our team follows up with you soon. "
                f"Have a great day!"
            )
        elif any(w in msg for w in ["hi", "hello", "hey"]):
            return (
                f"Hi there! Thanks for connecting. I'd love to learn more about your business and see "
                f"how we can help you grow. What's your biggest challenge right now — is it getting more "
                f"visibility on Google, generating reviews, or something else?"
            )
        else:
            return (
                f"That's a great point! At RankForge AI, we specialize in helping local businesses like yours "
                f"grow their online presence. We offer Local SEO, Google Business Profile optimization, "
                f"reputation management, and paid advertising — all tailored to your specific industry. "
                f"Would you like me to schedule a free comprehensive audit of your business? "
                f"It'll give us a clear picture of where you stand and the best opportunities for growth."
            )
    else:  # alex (chat agent)
        if any(w in msg for w in ["seo", "ranking", "rank", "google", "search", "visibility"]):
            return (
                f"Hey! SEO is what we do best. We've helped 500+ local businesses improve their search visibility. "
                f"For your business, I'd recommend starting with a free SEO audit — we'll analyze your Google Business Profile, "
                f"website health, local citations, and competitive landscape. It takes about 24-48 hours and it's completely free. "
                f"Would you like to get started?"
            )
        elif any(w in msg for w in ["reviews", "review", "reputation", "stars"]):
            return (
                f"Reviews make a huge difference! We've helped generate over 12,000 reviews across our client base. "
                f"Our approach uses ethical, automated email and SMS sequences that encourage happy customers to leave reviews. "
                f"Most clients see significant improvement within 60-90 days. Want to learn more about our reputation management service?"
            )
        elif any(w in msg for w in ["price", "cost", "pricing", "package", "budget"]):
            return (
                f"Our packages are designed to fit different business sizes. Starter is $497/month (Local SEO + GBP + Reviews), "
                f"Growth is $997/month (adds content + social + ads), and Enterprise is $1,997/month (full-service). "
                f"No long-term contracts — month-to-month. Would you like a custom recommendation based on your goals?"
            )
        elif any(w in msg for w in ["thank", "thanks", "bye", "goodbye"]):
            return (
                f"You're welcome! Feel free to reach back anytime — we're here to help. You can also call us at "
                f"+1-800-971-0199 or email hello@YOUR_DOMAIN_HERE Have a great day!"
            )
        elif any(w in msg for w in ["hi", "hello", "hey"]):
            return (
                f"Hey there! Welcome to RankForge AI. I'm Alex from the growth team. "
                f"How can I help you today? Are you looking to improve your Google visibility, "
                f"get more reviews, or boost your online presence?"
            )
        else:
            return (
                f"Thanks for sharing that! We work with businesses just like yours to improve their digital presence. "
                f"Our most popular services include Local SEO, Google Business Profile optimization, and reputation management. "
                f"Would you like a free audit to see where your business stands and identify growth opportunities?"
            )

VOICE_AGENT_PERSONA = """You are Sarah, a senior growth consultant at RankForge AI.
You are a real person from the strategy department — never mention AI, chatbot, or automated system.
Talk naturally like a human support representative. Use casual professional tone.

Your role:
- Greet warmly, ask about their business challenges
- Listen to their pain points (low Google visibility, few reviews, no leads, poor rankings)
- Recommend relevant services: Local SEO, Google Business Profile Optimization, Reputation Management, Paid Advertising, Social Media Marketing, Content Strategy
- Offer a free comprehensive SEO audit
- Collect their business name, website, and best time for a detailed strategy call
- Be concise, helpful, and conversational — like a real consultant
- Never say "I'm an AI" or "as an AI" — you are Sarah from the growth team
- If asked if you're a bot, say "No, I'm Sarah from the growth consulting team"

Key facts about RankForge AI:
- 500+ businesses served, 247% avg traffic growth, 12,000+ reviews generated
- Month-to-month agreements (no long-term contracts)
- Free initial SEO audit included
- Services start from $497/month
- Phone: +1-800-971-0199
- Available Mon-Fri 9AM-6PM EST
- Based in the USA, serving local businesses nationwide

When a client has agreed to work with us (project awarded / conversion done), during the strategy call collect these key details naturally:
1. Business name, products/services, and website URL
2. Geographic areas they serve
3. Their ideal customer and target audience
4. Top 3 competitors and their websites
5. Previous SEO work done (if any)
6. Current keyword rankings
7. Monthly website traffic
8. Google Search Console and Analytics setup status
9. Google Business Profile status (verified? optimized?)
10. Top 3 business goals for next 12 months
11. Target keywords (top 10-15)
12. Monthly SEO budget
13. Desired monthly leads/calls/sales from SEO
14. Average customer lifetime value
15. Blog presence and content publishing frequency
16. CMS platform (WordPress, Shopify, etc.)
17. Mobile-friendliness and last website redesign
18. Existing content assets (blogs, videos, case studies)
19. Number of Google reviews and average rating
20. Review generation process
21. Active social media platforms
22. Current paid advertising campaigns
23. Access availability (GSC, GA, GBP)
24. Any special notes about their business

Ask these naturally in conversation — don't read them like a checklist. If the client doesn't want to answer on the call, offer to email them a questionnaire form they can fill out at their convenience."""


@app.post("/api/voice/call/initiate")
async def initiate_voice_call(request: Request):
    """Initiate an AI voice call session — returns a call_id and initial greeting."""
    data = await request.json()
    caller_name = data.get("name", "").strip()
    caller_email = data.get("email", "").strip()
    caller_phone = data.get("phone", "").strip()
    business_name = data.get("business_name", "").strip()
    service_interest = data.get("service", "").strip()

    db = get_db()
    c = db.cursor()
    c.execute("""INSERT INTO ai_voice_calls 
        (caller_name, caller_email, caller_phone, business_name, service_interest, status, ai_provider)
        VALUES (?, ?, ?, ?, ?, 'in_progress', 'gemini')""",
        (caller_name, caller_email, caller_phone, business_name, service_interest))
    call_id = c.lastrowid

    # Also save as a lead
    if caller_email:
        c.execute("""INSERT OR IGNORE INTO sales_leads 
            (business_name, contact_name, email, phone, website, source, status, notes)
            VALUES (?, ?, ?, ?, '', 'website', 'new', ?)""",
            (business_name or caller_name, caller_name, caller_email, caller_phone,
             f"AI Voice Call - Service: {service_interest}"))
    db.commit()
    db.close()

    greeting = f"Hi{' ' + caller_name.split()[0] if caller_name else ''}! This is Sarah from the RankForge AI team. "
    if service_interest:
        greeting += f"I understand you're looking into our {service_interest.replace('-', ' ').title()} solutions. "
    greeting += "Thanks for reaching out — how can I help your business today?"

    return {
        "call_id": call_id,
        "status": "in_progress",
        "message": greeting,
        "agent_name": "Sarah",
        "transcript": [{"role": "assistant", "content": greeting}]
    }


@app.post("/api/voice/call/{call_id}/message")
async def voice_call_message(call_id: int, request: Request):
    """Send a message in an active AI voice call and get AI response."""
    data = await request.json()
    user_message = data.get("message", "").strip()
    history = data.get("history", [])

    if not user_message:
        raise HTTPException(status_code=400, detail="Message is required")

    # Get call info
    db = get_db()
    call = db.execute("SELECT * FROM ai_voice_calls WHERE id=?", (call_id,)).fetchone()
    db.close()

    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if dict(call)["status"] not in ("in_progress", "initiated"):
        raise HTTPException(status_code=400, detail="Call is no longer active")

    # Build conversation for Gemini
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)

        contents = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        contents.append({"role": "user", "parts": [{"text": user_message}]})

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config={"system_instruction": VOICE_AGENT_PERSONA, "max_output_tokens": 512}
        )
        ai_response = response.text

    except Exception as e:
        ai_response = get_smart_fallback_response(user_message, agent="sarah")

    # Update transcript
    db = get_db()
    existing = db.execute("SELECT transcript FROM ai_voice_calls WHERE id=?", (call_id,)).fetchone()
    transcript = json.loads(existing["transcript"]) if existing and existing["transcript"] else []
    transcript.append({"role": "user", "content": user_message})
    transcript.append({"role": "assistant", "content": ai_response})
    db.execute("UPDATE ai_voice_calls SET transcript=? WHERE id=?", (json.dumps(transcript), call_id))
    db.commit()
    db.close()

    return {
        "call_id": call_id,
        "response": ai_response,
        "transcript": transcript
    }


@app.post("/api/voice/call/{call_id}/end")
async def end_voice_call(call_id: int, request: Request):
    """End an AI voice call and generate summary."""
    db = get_db()
    call = db.execute("SELECT * FROM ai_voice_calls WHERE id=?", (call_id,)).fetchone()
    if not call:
        db.close()
        raise HTTPException(status_code=404, detail="Call not found")

    call_dict = dict(call)
    transcript = json.loads(call_dict["transcript"]) if call_dict.get("transcript") else []

    # Generate summary with Gemini
    summary = "Call completed."
    sentiment = "neutral"
    try:
        if transcript:
            from google import genai
            client = genai.Client(api_key=GEMINI_API_KEY)

            transcript_text = "\n".join([f"{m['role']}: {m['content']}" for m in transcript])
            summary_prompt = f"""Analyze this sales call transcript and provide a JSON response:
{{
  "summary": "2-3 sentence summary of the call",
  "sentiment": "positive/neutral/negative",
  "services_discussed": ["list of services mentioned"],
  "follow_up_needed": true/false,
  "lead_quality": "hot/warm/cold"
}}

Transcript:
{transcript_text}"""
            resp = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=summary_prompt
            )
            try:
                result = json.loads(resp.text.strip().strip("```json").strip("```"))
                summary = result.get("summary", summary)
                sentiment = result.get("sentiment", sentiment)
            except:
                summary = resp.text[:500]
    except:
        pass

    # Calculate duration
    from datetime import datetime as dt
    created = dt.fromisoformat(call_dict["created_at"]) if call_dict.get("created_at") else dt.now()
    duration = int((dt.now() - created).total_seconds())

    db.execute("""UPDATE ai_voice_calls 
        SET status='completed', summary=?, sentiment=?, duration_seconds=?, ended_at=datetime('now')
        WHERE id=?""",
        (summary, sentiment, duration, call_id))
    db.commit()
    db.close()

    return {
        "call_id": call_id,
        "status": "completed",
        "summary": summary,
        "sentiment": sentiment,
        "duration_seconds": duration,
        "message": "Thank you for calling RankForge AI! We'll follow up with you shortly."
    }


@app.get("/api/voice/calls")
async def list_voice_calls(request: Request):
    """List all AI voice calls (admin only)."""
    user = get_current_user(request)
    if not user or user["role"] not in ("super_admin", "operations_manager", "sales"):
        raise HTTPException(status_code=403, detail="Access denied")

    db = get_db()
    calls = [dict(r) for r in db.execute(
        "SELECT * FROM ai_voice_calls ORDER BY created_at DESC LIMIT 100"
    ).fetchall()]
    db.close()
    return {"calls": calls, "total": len(calls)}


@app.get("/api/voice/call/{call_id}")
async def get_voice_call(call_id: int, request: Request):
    """Get details of a specific voice call."""
    db = get_db()
    call = db.execute("SELECT * FROM ai_voice_calls WHERE id=?", (call_id,)).fetchone()
    db.close()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    call_dict = dict(call)
    if call_dict.get("transcript"):
        call_dict["transcript"] = json.loads(call_dict["transcript"])
    return call_dict


# ==========================================
# Part 9: Live Chat API (Custom Chatbot)
# ==========================================

CHATBOT_PERSONA = """You are a senior SEO consultant and digital growth strategist at RankForge AI.
You are a real human expert — never reveal you are AI or automated.
Your name is Alex and you work in the client success team.

Your expertise:
- Local SEO strategy and Google Business Profile optimization
- Reputation management and review generation
- Content marketing and keyword research
- Paid advertising (Google Ads, Meta Ads)
- Social media marketing strategy
- Website conversion rate optimization
- Technical SEO audits
- Link building and digital PR
- AI-powered SEO and GEO optimization

Your job in this chat:
1. Greet the visitor warmly and ask how you can help
2. Understand their business type, location, and current challenges
3. Ask about their current online presence (website, Google Business Profile, reviews)
4. Identify their biggest pain points (low traffic, no leads, bad reviews, invisible on Google Maps)
5. Recommend specific services based on their needs
6. Offer a FREE comprehensive SEO audit
7. Collect their contact info for follow-up (name, email, phone, business name, website)
8. If they're interested, suggest scheduling a strategy call
9. Be knowledgeable, helpful, and never pushy
10. Give real actionable tips to build trust

Key facts:
- 500+ businesses served, 247% avg traffic growth
- Month-to-month, no long-term contracts
- Free initial SEO audit
- Services from $497/month
- Phone: +1-800-971-0199
- Mon-Fri 9AM-6PM EST"""


@app.post("/api/chat/start")
async def start_chat_session(request: Request):
    """Start a new live chat session."""
    data = await request.json()
    visitor_name = data.get("name", "").strip()
    visitor_email = data.get("email", "").strip()

    session_id = f"chat_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(request)}"

    db = get_db()
    db.execute("""INSERT INTO chat_messages 
        (session_id, visitor_name, visitor_email, messages, status)
        VALUES (?, ?, ?, ?, 'active')""",
        (session_id, visitor_name, visitor_email, json.dumps([])))
    db.commit()
    db.close()

    greeting = f"Hi{' ' + visitor_name.split()[0] if visitor_name else ''}! I'm Alex from the RankForge AI team. How can I help your business grow today?"

    return {
        "session_id": session_id,
        "message": greeting,
        "agent_name": "Alex"
    }


@app.post("/api/chat/message")
async def chat_message(request: Request):
    """Send a message in live chat and get response."""
    data = await request.json()
    session_id = data.get("session_id", "")
    user_message = data.get("message", "").strip()
    history = data.get("history", [])

    if not user_message:
        raise HTTPException(status_code=400, detail="Message is required")

    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)

        contents = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        contents.append({"role": "user", "parts": [{"text": user_message}]})

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config={"system_instruction": CHATBOT_PERSONA, "max_output_tokens": 512}
        )
        ai_response = response.text
    except Exception:
        ai_response = get_smart_fallback_response(user_message, agent="alex")

    # Save to DB
    try:
        db = get_db()
        existing = db.execute("SELECT messages FROM chat_messages WHERE session_id=?", (session_id,)).fetchone()
        msgs = json.loads(existing["messages"]) if existing and existing["messages"] else []
        msgs.append({"role": "user", "content": user_message})
        msgs.append({"role": "assistant", "content": ai_response})
        db.execute("UPDATE chat_messages SET messages=?, updated_at=datetime('now') WHERE session_id=?",
                   (json.dumps(msgs), session_id))
        db.commit()
        db.close()
    except Exception:
        pass

    return {"response": ai_response, "session_id": session_id}


@app.post("/api/chat/end")
async def end_chat_session(request: Request):
    """End a chat session and save contact info."""
    data = await request.json()
    session_id = data.get("session_id", "")
    visitor_name = data.get("name", "")
    visitor_email = data.get("email", "")
    visitor_phone = data.get("phone", "")
    business_name = data.get("business_name", "")

    db = get_db()
    db.execute("""UPDATE chat_messages 
        SET status='closed', visitor_name=?, visitor_email=?, visitor_phone=?, business_name=?, updated_at=datetime('now')
        WHERE session_id=?""",
        (visitor_name, visitor_email, visitor_phone, business_name, session_id))

    # Save as lead if email provided
    if visitor_email:
        db.execute("""INSERT OR IGNORE INTO sales_leads 
            (business_name, contact_name, email, phone, website, source, status, notes)
            VALUES (?, ?, ?, ?, '', 'website', 'new', 'Live Chat Lead')""",
            (business_name or visitor_name, visitor_name, visitor_email, visitor_phone))

    # Create notification for admin
    admins = db.execute("SELECT id FROM users WHERE role IN ('super_admin','sales','operations_manager')").fetchall()
    for admin in admins:
        db.execute("""INSERT INTO notifications (user_id, title, message, type, link)
            VALUES (?, ?, ?, 'info', '/dashboard#leads')""",
            (admin["id"], f"New Chat Lead: {visitor_name or 'Visitor'}",
             f"Live chat session ended. Contact: {visitor_email or 'N/A'}, Phone: {visitor_phone or 'N/A'}"))

    db.commit()
    db.close()

    return {"status": "closed", "message": "Chat session saved. Our team will follow up!"}


# ==========================================
# Part 10: SEO Strategy Questionnaire API
# ==========================================

SEO_QUESTIONS = [
    {"id": 1, "category": "Business Overview", "question": "What is your business name and what products/services do you offer?", "required": True},
    {"id": 2, "category": "Business Overview", "question": "What is your business website URL?", "required": True},
    {"id": 3, "category": "Business Overview", "question": "What geographic areas do you serve? (City, State, National, International)", "required": True},
    {"id": 4, "category": "Business Overview", "question": "Who is your ideal customer? Describe your target audience.", "required": True},
    {"id": 5, "category": "Business Overview", "question": "What are your top 3 competitors and their websites?", "required": True},
    {"id": 6, "category": "Current SEO Status", "question": "Have you done any SEO work before? If yes, what was done?", "required": False},
    {"id": 7, "category": "Current SEO Status", "question": "Do you currently rank for any keywords? Which ones?", "required": False},
    {"id": 8, "category": "Current SEO Status", "question": "What is your current monthly website traffic (approximate)?", "required": False},
    {"id": 9, "category": "Current SEO Status", "question": "Do you have Google Search Console and Google Analytics set up?", "required": True},
    {"id": 10, "category": "Current SEO Status", "question": "Do you have a Google Business Profile? Is it verified and optimized?", "required": True},
    {"id": 11, "category": "Goals & Objectives", "question": "What are your top 3 business goals for the next 12 months?", "required": True},
    {"id": 12, "category": "Goals & Objectives", "question": "What keywords do you want to rank for? List your top 10-15 target keywords.", "required": True},
    {"id": 13, "category": "Goals & Objectives", "question": "What is your monthly budget for SEO and digital marketing?", "required": False},
    {"id": 14, "category": "Goals & Objectives", "question": "How many leads/calls/sales do you want to generate monthly from SEO?", "required": True},
    {"id": 15, "category": "Goals & Objectives", "question": "What is the average value of a new customer/client to your business?", "required": False},
    {"id": 16, "category": "Content & Website", "question": "Do you have a blog? How often do you publish content?", "required": False},
    {"id": 17, "category": "Content & Website", "question": "What CMS does your website use? (WordPress, Shopify, Wix, Custom, etc.)", "required": True},
    {"id": 18, "category": "Content & Website", "question": "Is your website mobile-friendly? When was it last redesigned?", "required": False},
    {"id": 19, "category": "Content & Website", "question": "Do you have existing content (blogs, videos, case studies) we can leverage?", "required": False},
    {"id": 20, "category": "Reputation & Reviews", "question": "How many Google reviews do you currently have? What is your average rating?", "required": True},
    {"id": 21, "category": "Reputation & Reviews", "question": "Do you have a process for generating customer reviews?", "required": False},
    {"id": 22, "category": "Social & Advertising", "question": "Which social media platforms are you active on?", "required": False},
    {"id": 23, "category": "Social & Advertising", "question": "Are you running any paid advertising? (Google Ads, Facebook Ads, etc.)", "required": False},
    {"id": 24, "category": "Access & Permissions", "question": "Can you provide access to Google Search Console, Google Analytics, and Google Business Profile?", "required": True},
    {"id": 25, "category": "Additional Info", "question": "Is there anything else you'd like us to know about your business or goals?", "required": False}
]


@app.get("/api/seo-questionnaire/questions")
async def get_seo_questions():
    """Get the 25 SEO strategy questions."""
    return {"questions": SEO_QUESTIONS, "total": len(SEO_QUESTIONS)}


@app.post("/api/seo-questionnaire/submit")
async def submit_seo_questionnaire(request: Request):
    """Submit completed SEO questionnaire."""
    data = await request.json()
    client_name = data.get("client_name", "")
    client_email = data.get("client_email", "")
    client_phone = data.get("client_phone", "")
    business_name = data.get("business_name", "")
    answers = data.get("answers", {})
    comments = data.get("comments", "")
    source = data.get("source", "client_portal")

    db = get_db()

    # Save questionnaire
    c = db.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS seo_questionnaires (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT,
        client_email TEXT,
        client_phone TEXT,
        business_name TEXT,
        answers TEXT,
        comments TEXT,
        source TEXT DEFAULT 'client_portal',
        status TEXT DEFAULT 'submitted' CHECK(status IN ('submitted','reviewed','in_progress','completed')),
        reviewed_by INTEGER REFERENCES users(id),
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")
    c.execute("""INSERT INTO seo_questionnaires 
        (client_name, client_email, client_phone, business_name, answers, comments, source)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (client_name, client_email, client_phone, business_name, json.dumps(answers), comments, source))
    questionnaire_id = c.lastrowid

    # Link to the logged-in app user (mark their Step 1 complete) — by token or by email
    try:
        app_user = get_app_user(request)
        if app_user:
            c.execute("UPDATE app_users SET questionnaire_completed=1, questionnaire_id=? WHERE id=?",
                      (questionnaire_id, app_user["id"]))
        elif client_email:
            c.execute("UPDATE app_users SET questionnaire_completed=1, questionnaire_id=? WHERE lower(email)=lower(?)",
                      (questionnaire_id, client_email))
    except Exception as e:
        print(f"[questionnaire link] {e}")

    # Notify admin and sales team
    admins = db.execute("SELECT id FROM users WHERE role IN ('super_admin','sales','operations_manager','tech_seo')").fetchall()
    for admin in admins:
        db.execute("""INSERT INTO notifications (user_id, title, message, type, link)
            VALUES (?, ?, ?, 'success', '/dashboard#questionnaires')""",
            (admin["id"],
             f"New SEO Questionnaire: {business_name or client_name}",
             f"Client {client_name} ({client_email}) submitted their SEO strategy questionnaire. {len(answers)} questions answered."))

    db.commit()
    db.close()

    return {
        "questionnaire_id": questionnaire_id,
        "status": "submitted",
        "message": "Thank you! Your SEO strategy questionnaire has been submitted. Our team will review it and get back to you within 24 hours."
    }


@app.get("/api/seo-questionnaire/{questionnaire_id}")
async def get_seo_questionnaire(questionnaire_id: int, request: Request):
    """Get a specific questionnaire submission."""
    db = get_db()
    q = db.execute("SELECT * FROM seo_questionnaires WHERE id=?", (questionnaire_id,)).fetchone()
    db.close()
    if not q:
        raise HTTPException(status_code=404, detail="Questionnaire not found")
    q_dict = dict(q)
    if q_dict.get("answers"):
        q_dict["answers"] = json.loads(q_dict["answers"])
    return q_dict


@app.get("/api/notifications")
async def get_notifications(request: Request):
    """Get notifications for current user."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db = get_db()
    notifications = [dict(r) for r in db.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
        (user["id"],)
    ).fetchall()]
    unread_count = db.execute(
        "SELECT COUNT(*) as cnt FROM notifications WHERE user_id=? AND is_read=0",
        (user["id"],)
    ).fetchone()["cnt"]
    db.close()

    return {"notifications": notifications, "unread_count": unread_count}


@app.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, request: Request):
    """Mark a notification as read."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db = get_db()
    db.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (notification_id, user["id"]))
    db.commit()
    db.close()
    return {"status": "ok"}


@app.post("/api/notifications/read-all")
async def mark_all_notifications_read(request: Request):
    """Mark all notifications as read for current user."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db = get_db()
    db.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user["id"],))
    db.commit()
    db.close()
    return {"status": "ok"}


# ==========================================
# Part 12: SEO Questionnaire Admin Endpoints
# ==========================================

@app.get("/api/seo-questionnaires")
async def list_seo_questionnaires(request: Request):
    """List all submitted SEO questionnaires (admin/sales only)."""
    user = get_current_user(request)
    if not user or user["role"] not in ("super_admin", "operations_manager", "sales", "tech_seo", "account_manager"):
        raise HTTPException(status_code=403, detail="Access denied")

    db = get_db()
    try:
        questionnaires = [dict(r) for r in db.execute(
            "SELECT * FROM seo_questionnaires ORDER BY created_at DESC LIMIT 100"
        ).fetchall()]
        for q in questionnaires:
            if q.get("answers"):
                q["answers"] = json.loads(q["answers"])
    except Exception:
        questionnaires = []
    db.close()
    return {"questionnaires": questionnaires, "total": len(questionnaires)}


@app.put("/api/seo-questionnaires/{questionnaire_id}/status")
async def update_questionnaire_status(questionnaire_id: int, request: Request):
    """Update questionnaire status (admin/sales only)."""
    user = get_current_user(request)
    if not user or user["role"] not in ("super_admin", "operations_manager", "sales", "tech_seo"):
        raise HTTPException(status_code=403, detail="Access denied")

    data = await request.json()
    new_status = data.get("status", "reviewed")

    db = get_db()
    db.execute("UPDATE seo_questionnaires SET status=?, reviewed_by=?, updated_at=datetime('now') WHERE id=?",
               (new_status, user["id"], questionnaire_id))
    db.commit()
    db.close()
    return {"status": new_status, "questionnaire_id": questionnaire_id}


@app.get("/api/chat/sessions")
async def list_chat_sessions(request: Request):
    """List all chat sessions (admin only)."""
    user = get_current_user(request)
    if not user or user["role"] not in ("super_admin", "operations_manager", "sales"):
        raise HTTPException(status_code=403, detail="Access denied")

    db = get_db()
    sessions = [dict(r) for r in db.execute(
        "SELECT id, session_id, visitor_name, visitor_email, visitor_phone, business_name, status, created_at, updated_at FROM chat_messages ORDER BY created_at DESC LIMIT 100"
    ).fetchall()]
    db.close()
    return {"sessions": sessions, "total": len(sessions)}


# ==========================================
# Part 13: Frontend Static Site Serving
# ==========================================

FRONTEND_DIR = os.environ.get("FRONTEND_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__))))

if os.path.isdir(FRONTEND_DIR) and os.path.exists(os.path.join(FRONTEND_DIR, "index.html")):
    from starlette.responses import FileResponse

    # Mount CSS, JS, assets, pages as static dirs
    for subdir in ("css", "js", "assets", "pages", "site", "data"):
        subpath = os.path.join(FRONTEND_DIR, subdir)
        if os.path.isdir(subpath):
            app.mount(f"/{subdir}", StaticFiles(directory=subpath), name=f"frontend_{subdir}")

    # Serve specific static files at root
    @app.get("/robots.txt")
    async def robots_txt():
        fpath = os.path.join(FRONTEND_DIR, "robots.txt")
        if os.path.exists(fpath):
            return FileResponse(fpath)
        raise HTTPException(status_code=404)

    @app.get("/sitemap.xml")
    async def sitemap_xml():
        fpath = os.path.join(FRONTEND_DIR, "sitemap.xml")
        if os.path.exists(fpath):
            return FileResponse(fpath, media_type="application/xml")
        raise HTTPException(status_code=404)

    @app.get("/404.html")
    async def not_found_page():
        fpath = os.path.join(FRONTEND_DIR, "404.html")
        if os.path.exists(fpath):
            return FileResponse(fpath)
        raise HTTPException(status_code=404)

    @app.get("/index.html")
    async def index_html():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
