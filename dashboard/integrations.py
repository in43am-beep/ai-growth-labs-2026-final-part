"""RankForge AI — production integrations.

Every integration here is **env-gated** and degrades gracefully when its
credentials are absent, so the site never breaks if a key is missing:

* Email (SMTP)        -> SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / SMTP_FROM
                         (falls back to the api_settings DB row, then to console log)
* Stripe payments     -> STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET
* Google OAuth        -> GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
* Twilio calls        -> TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_PHONE_NUMBER
* Background scheduler -> ENABLE_SCHEDULER (default on); APScheduler

Public URLs used for redirects/links:
* PUBLIC_BASE_URL   -> the backend's own public URL (Railway)
* FRONTEND_BASE_URL -> where the static site is served (Netlify)
"""
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# DB accessor — importable whether the app runs as `main` (cwd=dashboard/)
# or as `dashboard.main` (cwd=project root).
try:
    from database import get_db
except ModuleNotFoundError:  # pragma: no cover
    from dashboard.database import get_db


def _env(name, default=""):
    return os.environ.get(name, default) or default


def public_base_url():
    return _env("PUBLIC_BASE_URL", "https://rankforge-ai-production.up.railway.app").rstrip("/")


def frontend_base_url():
    return _env("FRONTEND_BASE_URL", "https://rankforge-ai.netlify.app").rstrip("/")


# ============================================================
# BEYOND SEO "BRAIN" (file-based SEO operating system)
# ============================================================
# The skill lives under dashboard/skills/beyond-seo/. We load its compact
# core rules + reporting standards once and inject them into every AI call
# so the chat/call agent and auto-reports think like a senior SEO strategist
# (no fluff, evidence-based, labels missing data) instead of generic filler.
_BRAIN_CACHE = None
_BRAIN_DIR = os.path.join(os.path.dirname(__file__), "skills", "beyond-seo")
# Core rule files, in the order they should be presented to the model.
_BRAIN_CORE_FILES = [
    "core/seo-principles.md",
    "core/no-fluff-rules.md",
    "core/data-quality-rules.md",
    "core/seo-aeo-definition.md",
    "core/final-output-standards.md",
    "core/decision-tree.md",
]


def beyond_seo_available():
    """True if the Beyond SEO skill files are present in the repo."""
    return os.path.isdir(_BRAIN_DIR) and os.path.isfile(os.path.join(_BRAIN_DIR, "SKILL.md"))


def beyond_seo_brain():
    """Return the compact Beyond SEO brain as a single system-prompt string.

    Cached after first load. Returns "" if the skill folder is missing so
    callers degrade gracefully to their existing personas.
    """
    global _BRAIN_CACHE
    if _BRAIN_CACHE is not None:
        return _BRAIN_CACHE
    if not beyond_seo_available():
        _BRAIN_CACHE = ""
        return _BRAIN_CACHE
    parts = [
        "=== BEYOND SEO OPERATING RULES (follow these in every SEO answer) ===",
        "You operate as a senior SEO/AEO/GEO strategist. No fluff, no fake "
        "guarantees, no generic checklists. Every recommendation must connect "
        "to crawlability, intent, authority, local visibility, conversion, or "
        "AI-search visibility, and must include: issue, evidence, impact, exact "
        "fix, priority, and how to measure it. Never invent rankings, search "
        "volume, traffic, or backlinks — if data is missing, say so and label "
        "estimates (Confirmed / Likely / Directional / Estimated / Not Verified).",
    ]
    for rel in _BRAIN_CORE_FILES:
        fp = os.path.join(_BRAIN_DIR, rel)
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                parts.append(fh.read().strip())
        except Exception:
            continue
    _BRAIN_CACHE = "\n\n".join(parts).strip()
    return _BRAIN_CACHE


def ai_system_prompt(base_persona=""):
    """Combine a caller's persona with the Beyond SEO brain (if available)."""
    brain = beyond_seo_brain()
    if not brain:
        return base_persona
    if not base_persona:
        return brain
    return base_persona.rstrip() + "\n\n" + brain


# ============================================================
# APIFY DATA LAYER (real crawl / SERP / authority data)
# ============================================================
# Env-gated. When APIFY_API_TOKEN is absent the helpers return None and the
# brain falls back to "Advisory mode" (reasoning without live data) so the
# site never breaks.
def apify_enabled():
    return bool(_env("APIFY_API_TOKEN"))


def apify_run_actor(actor_id, run_input, timeout=120):
    """Run an Apify actor synchronously and return its dataset items (list).

    Returns None on any failure (missing token, network error, bad actor) so
    callers can degrade to advisory mode. The token is read from the env and
    never logged.
    """
    token = _env("APIFY_API_TOKEN")
    if not token:
        return None
    try:
        import requests
        # run-sync-get-dataset-items returns the produced items directly.
        url = (
            f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
            f"?token={token}&timeout={timeout}"
        )
        resp = requests.post(url, json=run_input, timeout=timeout + 15)
        if resp.status_code >= 400:
            print(f"[apify] actor {actor_id} -> HTTP {resp.status_code}")
            return None
        return resp.json()
    except Exception as e:
        print(f"[apify] actor {actor_id} failed: {e}")
        return None


def apify_site_overview(url, max_pages=5):
    """Credit-safe crawl of a site using Apify's website-content-crawler.

    Returns a compact dict {url, pages_crawled, titles, sample} or None when
    Apify is not configured / the crawl fails. Kept small to stay within AI
    token limits and Apify credits.
    """
    if not apify_enabled() or not url:
        return None
    items = apify_run_actor(
        "apify~website-content-crawler",
        {
            "startUrls": [{"url": url}],
            "maxCrawlPages": max_pages,
            "crawlerType": "cheerio",
        },
        timeout=120,
    )
    if not items:
        return None
    titles, sample = [], ""
    for it in items[:max_pages]:
        t = (it.get("metadata", {}) or {}).get("title") or it.get("title") or ""
        if t:
            titles.append(t)
        if not sample:
            sample = (it.get("text") or "")[:600]
    return {
        "url": url,
        "pages_crawled": len(items),
        "titles": titles[:max_pages],
        "sample": sample,
        "source": "apify:website-content-crawler",
        "quality": "Directional",
    }


# ============================================================
# EMAIL (SMTP)
# ============================================================
def email_config(db=None):
    """Resolve SMTP settings from env first, then the api_settings table.

    Returns a dict {host, port, user, password, from_email} or None.
    """
    host = _env("SMTP_HOST")
    password = _env("SMTP_PASSWORD")
    if host and password:
        user = _env("SMTP_USER") or _env("SMTP_FROM")
        return {
            "host": host,
            "port": int(_env("SMTP_PORT", "587")),
            "user": user,
            "password": password,
            "from_email": _env("SMTP_FROM") or user,
        }
    if db is not None:
        try:
            row = db.execute("SELECT * FROM api_settings WHERE provider='smtp'").fetchone()
            if row and row["api_key"]:
                row = dict(row)
                cfg = json.loads(row.get("config_json") or "{}")
                from_email = cfg.get("from_email", row["api_key"])
                return {
                    "host": cfg.get("host", "smtp.gmail.com"),
                    "port": int(cfg.get("port", 587)),
                    "user": from_email,
                    "password": row["api_key"],
                    "from_email": from_email,
                }
        except Exception as e:  # pragma: no cover
            print(f"[email_config] DB lookup failed: {e}")
    return None


def email_enabled(db=None):
    return email_config(db) is not None


def send_email(to_email, subject, html_body=None, text_body=None, db=None):
    """Send an email. Returns (ok: bool, detail: str).

    When SMTP is not configured, logs to console and returns (False, ...)
    so callers can keep working without raising.
    """
    cfg = email_config(db)
    if not cfg or not to_email:
        print(f"[EMAIL:not-configured] to={to_email} subject={subject!r}")
        return (False, "email-not-configured")
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg["from_email"]
        msg["To"] = to_email
        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))
        if not text_body and not html_body:
            msg.attach(MIMEText("", "plain"))
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
        print(f"[EMAIL:sent] to={to_email} subject={subject!r}")
        return (True, "sent")
    except Exception as e:
        print(f"[EMAIL:error] to={to_email}: {e}")
        return (False, str(e))


# ============================================================
# STRIPE (real payments)
# ============================================================
def stripe_enabled():
    return bool(_env("STRIPE_SECRET_KEY"))


def _stripe():
    import stripe
    stripe.api_key = _env("STRIPE_SECRET_KEY")
    return stripe


def create_checkout_session(pkg, app_user, success_url, cancel_url):
    """Create a monthly subscription Checkout Session. Returns (url, session_id)."""
    stripe = _stripe()
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": pkg["name"],
                    "description": pkg.get("tagline", ""),
                },
                "unit_amount": int(pkg["price"]) * 100,
                "recurring": {"interval": "month"},
            },
            "quantity": 1,
        }],
        customer_email=app_user.get("email"),
        client_reference_id=str(app_user["id"]),
        metadata={"app_user_id": str(app_user["id"]), "package_id": pkg["id"]},
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return session.url, session.id


def retrieve_checkout_session(session_id):
    """Fetch a Checkout Session (used to verify payment on the success redirect)."""
    stripe = _stripe()
    return stripe.checkout.Session.retrieve(session_id)


def verify_webhook(payload, sig_header):
    """Parse + verify a Stripe webhook event. Verifies the signature when
    STRIPE_WEBHOOK_SECRET is set, otherwise trusts the JSON body."""
    secret = _env("STRIPE_WEBHOOK_SECRET")
    stripe = _stripe()
    if secret and sig_header:
        return stripe.Webhook.construct_event(payload, sig_header, secret)
    return json.loads(payload)


# ============================================================
# GOOGLE OAUTH
# ============================================================
def google_enabled():
    return bool(_env("GOOGLE_CLIENT_ID") and _env("GOOGLE_CLIENT_SECRET"))


def google_redirect_uri():
    return _env("GOOGLE_REDIRECT_URI") or (public_base_url() + "/api/auth/google/callback")


def google_auth_url(state):
    from urllib.parse import urlencode
    params = {
        "client_id": _env("GOOGLE_CLIENT_ID"),
        "redirect_uri": google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "include_granted_scopes": "true",
        "state": state,
        "prompt": "select_account",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


def google_exchange_code(code):
    """Exchange an auth code for the user's Google profile (email, name, id)."""
    import requests
    tok = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": _env("GOOGLE_CLIENT_ID"),
            "client_secret": _env("GOOGLE_CLIENT_SECRET"),
            "redirect_uri": google_redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=15,
    ).json()
    access = tok.get("access_token")
    if not access:
        raise RuntimeError(f"Google token exchange failed: {tok}")
    info = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access}"},
        timeout=15,
    ).json()
    return info


# ============================================================
# TWILIO (real calls)
# ============================================================
def twilio_config(db=None):
    sid = _env("TWILIO_ACCOUNT_SID")
    token = _env("TWILIO_AUTH_TOKEN")
    frm = _env("TWILIO_PHONE_NUMBER")
    if sid and token and frm:
        return {"sid": sid, "token": token, "from": frm}
    if db is not None:
        try:
            row = db.execute("SELECT * FROM api_settings WHERE provider='twilio' AND is_active=1").fetchone()
            if row and row["api_key"]:
                cfg = json.loads(dict(row).get("config_json") or "{}")
                if cfg.get("account_sid") and cfg.get("phone_number"):
                    return {"sid": cfg["account_sid"], "token": row["api_key"], "from": cfg["phone_number"]}
        except Exception as e:  # pragma: no cover
            print(f"[twilio_config] DB lookup failed: {e}")
    return None


def twilio_enabled(db=None):
    return twilio_config(db) is not None


def place_call(to_number, twiml_url, db=None):
    """Place a real outbound call via Twilio. Returns (ok, detail, call_sid)."""
    cfg = twilio_config(db)
    if not cfg:
        return (False, "twilio-not-configured", None)
    try:
        from twilio.rest import Client
        client = Client(cfg["sid"], cfg["token"])
        call = client.calls.create(to=to_number, from_=cfg["from"], url=twiml_url)
        return (True, "initiated", call.sid)
    except Exception as e:
        return (False, str(e), None)


# ============================================================
# QUESTIONNAIRE ANALYSIS + DEPARTMENT ROUTING
# ============================================================
# Keyword rules -> (focus area label, department role that owns it).
_ANALYSIS_RULES = [
    (("review", "reputation", "rating", "stars", "testimonial"), "Reputation / Review Generation", "account_manager"),
    (("google business", "gbp", "google maps", "map pack", "local pack", "maps"), "Local SEO / GBP Optimization", "tech_seo"),
    (("keyword", "ranking", "rank ", "organic", "search engine", "seo"), "SEO Strategy", "tech_seo"),
    (("website", "site speed", "redesign", "ux", "mobile", "page speed"), "Web / UX", "operations_manager"),
    (("ads", "ppc", "google ads", "paid", "adwords"), "Paid Media", "sales"),
    (("social", "facebook", "instagram", "linkedin", "tiktok"), "Social Media", "account_manager"),
    (("content", "blog", "article", "copywriting"), "Content Marketing", "tech_seo"),
    (("competitor", "competition", "rival"), "Competitive Analysis", "operations_manager"),
    (("email marketing", "newsletter", "drip"), "Email Marketing", "account_manager"),
]


def analyze_questionnaire(answers, business_name="", client_name="", website=""):
    """Turn raw questionnaire answers into a structured strategy report.

    Uses the Beyond SEO brain to produce evidence-based, no-fluff focus areas
    and, when APIFY_API_TOKEN is set and a website is provided, enriches the
    report with a credit-safe live crawl. Returns a dict with focus_areas,
    departments (role names), summary, plus mode/site_data/recommendations.
    """
    try:
        text = json.dumps(answers, default=str).lower()
    except Exception:
        text = str(answers).lower()
    focus, depts = [], []
    for kws, label, dept in _ANALYSIS_RULES:
        if any(k in text for k in kws):
            if label not in focus:
                focus.append(label)
            if dept not in depts:
                depts.append(dept)
    if not focus:
        focus = ["General Local SEO"]
        depts = ["tech_seo"]
    n = len(answers) if isinstance(answers, dict) else 0
    name = business_name or client_name or "New client"

    # Data layer: try a live crawl only if Apify is configured + URL given.
    site_data = apify_site_overview(website) if (website and apify_enabled()) else None
    mode = "Apify Intelligence" if site_data else ("Advisory" if beyond_seo_available() else "Basic")

    # No-fluff recommendations per focus area (issue/impact/fix shape).
    recommendations = [_focus_recommendation(f) for f in focus]

    summary = f"{name}: priority focus on {', '.join(focus)} (based on {n} answered questions)."
    if site_data:
        summary += (
            f" Live crawl: {site_data['pages_crawled']} page(s) sampled "
            f"[{site_data['quality']} data]."
        )
    else:
        summary += " No live site data (Advisory mode) — set APIFY_API_TOKEN for live crawl."

    return {
        "business": name,
        "website": website or "",
        "answered": n,
        "focus_areas": focus,
        "departments": depts,
        "mode": mode,
        "site_data": site_data,
        "recommendations": recommendations,
        "generated_at": datetime.utcnow().isoformat(),
        "summary": summary,
    }


# Concrete, no-fluff next-action per focus area (Beyond SEO style: not generic).
_FOCUS_ACTIONS = {
    "Reputation / Review Generation": "Set up a review-request flow (post-service SMS/email) and respond to every Google review within 24h; measure: new reviews/month + avg rating.",
    "SEO Strategy": "Build topical service+location pages mapped to buyer intent; measure: indexed pages and non-brand clicks in Search Console.",
    "Web / UX": "Fix mobile Core Web Vitals (LCP/CLS) and add clear CTAs above the fold; measure: CWV pass rate + form/call conversion.",
    "Paid Media": "Start with high-intent local search ads on top 5 money keywords with call tracking; measure: cost per qualified lead.",
    "Competitive Analysis": "Map top 3 competitors' ranking pages and backlink sources; measure: keyword gap closed per month.",
    "General Local SEO": "Optimize Google Business Profile (categories, services, photos, posts) and NAP consistency; measure: GBP calls/direction requests.",
}


def _focus_recommendation(focus_label):
    return {
        "area": focus_label,
        "action": _FOCUS_ACTIONS.get(focus_label, _FOCUS_ACTIONS["General Local SEO"]),
        "priority": "High",
    }


def route_questionnaire_report(db, questionnaire_id, report):
    """Persist the auto-report and push a notification to each relevant department."""
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS questionnaire_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            questionnaire_id INTEGER,
            business TEXT,
            report_json TEXT,
            departments TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""")
        db.execute(
            "INSERT INTO questionnaire_reports (questionnaire_id, business, report_json, departments) VALUES (?,?,?,?)",
            (questionnaire_id, report.get("business"), json.dumps(report), ",".join(report.get("departments", []))),
        )
        roles = report.get("departments") or []
        # always include super_admin so leadership sees every report
        target_roles = list(dict.fromkeys(roles + ["super_admin"]))
        placeholders = ",".join("?" * len(target_roles))
        users = db.execute(
            f"SELECT id FROM users WHERE role IN ({placeholders})", tuple(target_roles)
        ).fetchall()
        for u in users:
            db.execute(
                """INSERT INTO notifications (user_id, title, message, type, link)
                   VALUES (?,?,?,?,?)""",
                (u["id"], f"SEO Strategy Report: {report.get('business')}",
                 report.get("summary", "") + " Focus: " + ", ".join(report.get("focus_areas", [])),
                 "task", "/dashboard#questionnaires"),
            )
    except Exception as e:
        print(f"[route_questionnaire_report] {e}")


# ============================================================
# BACKGROUND SCHEDULER (questionnaire reminders every 2 days)
# ============================================================
_scheduler = None
REMINDER_INTERVAL_DAYS = int(_env("REMINDER_INTERVAL_DAYS", "2"))
MAX_REMINDERS = int(_env("MAX_REMINDERS", "5"))


def _reminder_email_html(name, link):
    first = (name or "there").split(" ")[0]
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto">
      <h2 style="color:#1a73e8">One quick step to start your SEO work</h2>
      <p>Hi {first},</p>
      <p>We can't begin optimizing your business until we understand your goals.
      Please take 5 minutes to complete your <strong>SEO Strategy Questionnaire</strong> —
      it's the first step before our team starts work.</p>
      <p style="margin:28px 0">
        <a href="{link}" style="background:#1a73e8;color:#fff;padding:12px 22px;
        border-radius:6px;text-decoration:none">Complete the questionnaire →</a>
      </p>
      <p style="color:#666;font-size:13px">If you've already submitted it, please ignore this email.</p>
      <p style="color:#666;font-size:13px">— The RankForge AI Team · (800) 971-0199</p>
    </div>"""


def run_questionnaire_reminders():
    """Email clients who signed up but haven't completed the questionnaire."""
    try:
        db = get_db()
    except Exception as e:
        print(f"[reminders] db open failed: {e}")
        return
    sent = 0
    try:
        link = frontend_base_url() + "/pages/client-questionnaire.html"
        rows = db.execute(
            """SELECT id, full_name, email, COALESCE(reminder_count,0) AS rc
               FROM app_users
               WHERE COALESCE(questionnaire_completed,0)=0
                 AND email IS NOT NULL AND email != ''
                 AND COALESCE(reminder_count,0) < ?""",
            (MAX_REMINDERS,),
        ).fetchall()
        for r in rows:
            ok, _ = send_email(
                r["email"],
                "Reminder: complete your SEO Strategy Questionnaire",
                html_body=_reminder_email_html(r["full_name"], link),
                db=db,
            )
            db.execute(
                "UPDATE app_users SET reminder_count=COALESCE(reminder_count,0)+1, last_reminder_at=datetime('now') WHERE id=?",
                (r["id"],),
            )
            # In-app nudge for admins to follow up
            try:
                admins = db.execute("SELECT id FROM users WHERE role IN ('super_admin','account_manager')").fetchall()
                for a in admins:
                    db.execute(
                        """INSERT INTO notifications (user_id, title, message, type, link)
                           VALUES (?,?,?,?,?)""",
                        (a["id"], "Questionnaire reminder sent",
                         f"Reminder #{r['rc'] + 1} sent to {r['email']} (questionnaire still pending).",
                         "info", "/dashboard#questionnaires"),
                    )
            except Exception:
                pass
            if ok:
                sent += 1
        db.commit()
    except Exception as e:
        print(f"[reminders] {e}")
    finally:
        try:
            db.close()
        except Exception:
            pass
    print(f"[reminders] run complete — {sent} email(s) sent")


def start_scheduler():
    """Start the background scheduler once. Safe to call multiple times."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    if _env("ENABLE_SCHEDULER", "true").lower() not in ("1", "true", "yes", "on"):
        print("[scheduler] disabled via ENABLE_SCHEDULER")
        return None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception as e:
        print(f"[scheduler] APScheduler unavailable: {e}")
        return None
    try:
        sched = BackgroundScheduler(daemon=True, timezone="UTC")
        sched.add_job(
            run_questionnaire_reminders,
            "interval",
            days=REMINDER_INTERVAL_DAYS,
            id="questionnaire_reminders",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        sched.start()
        _scheduler = sched
        print(f"[scheduler] started — questionnaire reminders every {REMINDER_INTERVAL_DAYS} day(s)")
        return sched
    except Exception as e:
        print(f"[scheduler] failed to start: {e}")
        return None


def integration_status(db=None):
    """Snapshot of which integrations are live (used by /api/integrations/status)."""
    return {
        "email": email_enabled(db),
        "stripe": stripe_enabled(),
        "google_oauth": google_enabled(),
        "twilio": twilio_enabled(db),
        "scheduler": _scheduler is not None,
        "beyond_seo_brain": beyond_seo_available(),
        "apify": apify_enabled(),
    }
