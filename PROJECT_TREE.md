# RankForge AI — Project Structure & Tree

_Generated: 2026-06-01 10:45 UTC_

RankForge AI is a multi-service local-SEO agency platform: a static marketing frontend + a FastAPI backend (REST API, SQLite DB, admin dashboards, AI call/chat agents, client portal with package gating).

## Directory tree

```
.
├── assets
│   └── images
│       └── og-default.jpg
├── css
│   └── style.css
├── dashboard
│   ├── static
│   │   ├── css
│   │   └── js
│   ├── templates
│   │   ├── activity_timeline.html
│   │   ├── admin_dashboard.html
│   │   ├── analytics.html
│   │   ├── blog_admin.html
│   │   ├── client_detail.html
│   │   ├── client_portal.html
│   │   ├── finance_dashboard.html
│   │   ├── login.html
│   │   ├── monitor.html
│   │   ├── ops_dashboard.html
│   │   ├── performance.html
│   │   ├── rankings_chart.html
│   │   ├── sales_dashboard.html
│   │   ├── settings.html
│   │   ├── social_dashboard.html
│   │   ├── team_chat.html
│   │   └── worker_dashboard.html
│   ├── agency.db
│   ├── database.py
│   ├── generate_templates.py
│   ├── main.py
│   ├── pyproject.toml
│   └── requirements.txt
├── data
│   └── blog-posts.json
├── js
│   ├── auth.js
│   ├── form-validation.js
│   ├── live-chat.js
│   ├── main.js
│   └── voice-call.js
├── pages
│   ├── blog
│   │   ├── ai-seo-chatgpt-citations-2026.html
│   │   ├── dentists-google-maps-2026.html
│   │   ├── ethical-review-generation-guide.html
│   │   ├── gbp-optimization-guide-2026.html
│   │   ├── lawyers-more-leads-google.html
│   │   └── restaurant-local-seo-2026.html
│   ├── about.html
│   ├── ai-seo.html
│   ├── analytics-reporting.html
│   ├── blog-post.html
│   ├── blog.html
│   ├── brand-strategy.html
│   ├── case-studies.html
│   ├── client-questionnaire.html
│   ├── contact.html
│   ├── content-creation.html
│   ├── cro.html
│   ├── dashboard-user.html
│   ├── digital-pr.html
│   ├── disclaimer.html
│   ├── ecommerce-seo.html
│   ├── email-marketing.html
│   ├── free-audit.html
│   ├── free-resources.html
│   ├── gbp-optimization.html
│   ├── geo-optimization.html
│   ├── geofencing.html
│   ├── influencer-marketing.html
│   ├── lead-nurture.html
│   ├── link-building.html
│   ├── local-seo.html
│   ├── login.html
│   ├── marketing-consulting.html
│   ├── marketplace-marketing.html
│   ├── paid-advertising.html
│   ├── privacy-policy.html
│   ├── programmatic-ads.html
│   ├── reputation-management.html
│   ├── sales-enablement.html
│   ├── seo-for-auto-repair.html
│   ├── seo-for-chiropractors.html
│   ├── seo-for-cleaning.html
│   ├── seo-for-construction.html
│   ├── seo-for-dentists.html
│   ├── seo-for-electricians.html
│   ├── seo-for-financial-advisors.html
│   ├── seo-for-gyms.html
│   ├── seo-for-hvac.html
│   ├── seo-for-insurance.html
│   ├── seo-for-landscaping.html
│   ├── seo-for-lawyers.html
│   ├── seo-for-medical-spas.html
│   ├── seo-for-movers.html
│   ├── seo-for-pet-services.html
│   ├── seo-for-photographers.html
│   ├── seo-for-plumbers.html
│   ├── seo-for-real-estate.html
│   ├── seo-for-restaurants.html
│   ├── seo-for-roofing.html
│   ├── seo-for-salons.html
│   ├── seo-for-veterinarians.html
│   ├── signup.html
│   ├── social-media.html
│   ├── terms.html
│   ├── ux-design.html
│   ├── video-seo.html
│   └── web-design.html
├── site
│   ├── css
│   │   └── main.css
│   ├── js
│   │   └── main.js
│   ├── pages
│   │   ├── about.html
│   │   ├── ai-seo.html
│   │   ├── blog.html
│   │   ├── case-studies.html
│   │   ├── contact.html
│   │   ├── content-creation.html
│   │   ├── disclaimer.html
│   │   ├── free-audit.html
│   │   ├── gbp-optimization.html
│   │   ├── local-seo.html
│   │   ├── paid-advertising.html
│   │   ├── privacy-policy.html
│   │   ├── reputation-management.html
│   │   ├── seo-for-dentists.html
│   │   ├── seo-for-hvac.html
│   │   ├── seo-for-lawyers.html
│   │   ├── seo-for-medical-spas.html
│   │   ├── seo-for-plumbers.html
│   │   ├── seo-for-restaurants.html
│   │   ├── social-media.html
│   │   └── terms.html
│   ├── templates
│   │   ├── ai-seo-agency-os.html
│   │   ├── client-proposal.html
│   │   ├── client-reporting.html
│   │   ├── competitor-styles.html
│   │   ├── discovery-call.html
│   │   ├── dna-audit-prompt-level1.html
│   │   ├── dna-audit-prompt-level2.html
│   │   ├── index.html
│   │   ├── kickoff-call.html
│   │   ├── onboarding-form.html
│   │   ├── pro-tips-working-patterns.html
│   │   ├── service-ai-seo.html
│   │   ├── service-content-creation.html
│   │   ├── service-gbp-optimization.html
│   │   ├── service-paid-ads.html
│   │   ├── service-reputation-management.html
│   │   └── service-social-media.html
│   ├── COMPLETE_EXECUTION_GUIDE.md
│   ├── COMPLETE_STRATEGY.md
│   └── index.html
├── templates
│   ├── ai-seo-agency-os.html
│   ├── client-proposal.html
│   ├── client-reporting.html
│   ├── competitor-styles.html
│   ├── discovery-call.html
│   ├── dna-audit-prompt-level1.html
│   ├── dna-audit-prompt-level2.html
│   ├── index.html
│   ├── kickoff-call.html
│   ├── onboarding-form.html
│   ├── pro-tips-working-patterns.html
│   ├── service-ai-seo.html
│   ├── service-content-creation.html
│   ├── service-gbp-optimization.html
│   ├── service-paid-ads.html
│   ├── service-reputation-management.html
│   └── service-social-media.html
├── 404.html
├── AI_GROWTH_LABS_COMPLETE_GUIDE.md
├── AI_Growth_Labs_Complete_System_Report.pdf
├── API_GUIDE.md
├── COMPLETE_EXECUTION_GUIDE.md
├── COMPLETE_STRATEGY.md
├── DATA_TREE.md
├── DEPLOYMENT_GUIDE.md
├── Dockerfile
├── FEASIBILITY_REPORT.md
├── FREE_AUDIT_ROADMAP.md
├── PROGRESS_LOG.md
├── PROJECT_PLAN.md
├── PROJECT_TREE.md
├── README.md
├── SEO_AUDIT_REPORT.md
├── build-pages.sh
├── fly.toml
├── generate_pages.py
├── generate_report.py
├── index.html
├── nginx.conf
├── proxy_headers.conf
├── robots.txt
├── sitemap.xml
└── start.sh

18 directories, 184 files
```

## Component overview

### Frontend (static marketing site)
- **`index.html`** — homepage (hero, services, pricing, FAQ).
- **`pages/`** — 61 marketing/service/industry pages + auth pages (`login.html`, `signup.html`, `dashboard-user.html`), `client-questionnaire.html`, `free-audit.html`, `free-resources.html`, `blog.html` + `blog-post.html`.
- **`pages/blog/`** — 6 long-form SEO blog articles.
- **`css/style.css`** — single global stylesheet (includes client-dashboard package-gating styles).
- **`js/`** — `auth.js` (signup/login), `main.js` (nav, toasts, cookie banner), `voice-call.js` (AI Call widget — "Sarah"), `live-chat.js` (custom chatbot — "Alex"), `form-validation.js`.

### Backend (`dashboard/`, FastAPI + SQLite)
- **`main.py`** — ~146 REST endpoints + server-rendered admin dashboards. Auth (JWT/bcrypt), leads, blog CRUD, AI call/chat agents (Gemini + smart keyword fallback), SEO questionnaire, notifications, **client packages + payment gating**.
- **`database.py`** — schema (33 tables) + seed data + migrations.
- **`templates/`** — Jinja admin/role dashboards (super_admin, ops, sales, finance, social, worker, client portal, blog admin, settings).
- **`requirements.txt` / `pyproject.toml`** — Python deps.

### Deployment
- **`Dockerfile`** — multi-stage (Python deps → runtime with FastAPI + nginx).
- **`nginx.conf` / `proxy_headers.conf`** — static serving on 8080, reverse-proxy `/api`, `/dashboard`, etc. to FastAPI on 8000, gzip + cache + custom 404.
- **`start.sh`** — boots uvicorn (8000) then nginx (8080).
- **`.env.example`** — SECRET_KEY, DATABASE_URL, GEMINI_API_KEY, etc.
- **`fly.toml`** — Fly.io config (internal_port 8080).
- **`generate_pages.py`** — portable page generator (outputs to `./generated/pages`, gitignored).

## Key client-facing flows

### Auth + client dashboard (package gating) — NEW
- Signup/login → JWT → `pages/dashboard-user.html`.
- **Step 1 alert**: client must complete the 25-question SEO Strategy Questionnaire first (`client-questionnaire.html`, auto-prefilled when logged in).
- **Free Actions** (always active pre-purchase): questionnaire, free audit, free resources.
- **Packages**: Local Growth Starter ($1,997), Local Growth Pro ($3,997), Local Dominance ($6,997).
- **SEO tasks are locked** (🔒) until a package is purchased; after `Buy & Activate` they unlock per the chosen package tier.
- Everything persists: `app_users.package / payment_status / paid_at / questionnaire_completed`, a `payments` row, and an admin notification.

### AI agents
- **AI Call ("Sarah")** and **Live Chat ("Alex")** — Gemini-powered with a smart keyword fallback when the API quota is exhausted. Text-based (not real telephony).

## Relevant API endpoints (client portal)
- `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/me`, `PUT /api/auth/update`
- `GET /api/packages` — list packages (public)
- `GET /api/user/dashboard` — profile + payment status + free actions + tasks (locked/active)
- `POST /api/user/buy-package` — activate package, record payment, notify admin
- `GET /api/seo-questionnaire/questions`, `POST /api/seo-questionnaire/submit` (links to logged-in user)
- `GET /api/notifications`, `POST /api/notifications/{id}/read`
