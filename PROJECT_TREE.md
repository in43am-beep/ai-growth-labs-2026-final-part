# RankForge AI — Complete Project Tree & Code Documentation

> **PURPOSE:** Complete project structure, every file explained, every function documented,
> every database table described, and every API endpoint listed.
>
> **Last Updated:** May 2026 | **Total Files:** 168 | **Total Lines of Code:** ~25,000+

---

## Directory Structure

```
ai-growth-labs-new/
│
├── index.html                          # Homepage (869 lines) — hero, services, testimonials, FAQ, footer
├── 404.html                            # Custom 404 error page
├── robots.txt                          # Search engine crawler rules
├── sitemap.xml                         # XML sitemap for SEO
│
├── css/
│   └── style.css                       # Main stylesheet (1652 lines) — dark luxury theme, glassmorphism, mega menu
│
├── js/
│   ├── main.js                         # Main JS (212 lines) — sticky CTA, counter animation, lazy load, mega menu
│   └── form-validation.js              # Form validation utility (rate limiting, honeypot, sanitization)
│
├── assets/
│   └── images/
│       └── og-default.jpg              # Open Graph image for social sharing (1200x630)
│
├── pages/                              # 55 frontend pages
│   ├── about.html                      # About page with team section
│   ├── contact.html                    # Contact form + Calendly embed
│   ├── free-audit.html                 # Free DNA SEO Audit (854 lines) — 16-pillar real crawl audit
│   ├── blog.html                       # Blog listing page
│   ├── case-studies.html               # Case studies / portfolio
│   ├── privacy-policy.html             # Privacy policy
│   ├── terms.html                      # Terms of service
│   ├── disclaimer.html                 # Legal disclaimer
│   │
│   ├── # ---- SERVICE PAGES (25) ----
│   ├── local-seo.html                  # Local SEO service
│   ├── gbp-optimization.html           # Google Business Profile optimization
│   ├── ai-seo.html                     # AI-powered SEO
│   ├── geofencing.html                 # Geofencing marketing
│   ├── geo-optimization.html           # GEO / AI search optimization
│   ├── paid-advertising.html           # PPC / Google Ads
│   ├── social-media.html               # Social media management
│   ├── programmatic-ads.html           # Programmatic advertising
│   ├── digital-pr.html                 # Digital PR & outreach
│   ├── influencer-marketing.html       # Influencer marketing
│   ├── content-creation.html           # Content creation service
│   ├── video-seo.html                  # Video SEO / YouTube
│   ├── email-marketing.html            # Email marketing
│   ├── brand-strategy.html             # Brand strategy
│   ├── sales-enablement.html           # Sales enablement
│   ├── analytics-reporting.html        # Analytics & reporting
│   ├── cro.html                        # Conversion rate optimization
│   ├── ecommerce-seo.html              # E-commerce SEO
│   ├── ux-design.html                  # UX/UI design
│   ├── web-design.html                 # Web design
│   ├── reputation-management.html      # Reputation management
│   ├── link-building.html              # Link building
│   ├── lead-nurture.html               # Lead nurturing
│   ├── marketing-consulting.html       # Marketing consulting
│   ├── marketplace-marketing.html      # Marketplace (Amazon/Etsy) marketing
│   │
│   ├── # ---- INDUSTRY PAGES (22) ----
│   ├── seo-for-dentists.html
│   ├── seo-for-chiropractors.html
│   ├── seo-for-medical-spas.html
│   ├── seo-for-veterinarians.html
│   ├── seo-for-salons.html
│   ├── seo-for-gyms.html
│   ├── seo-for-lawyers.html
│   ├── seo-for-financial-advisors.html
│   ├── seo-for-insurance.html
│   ├── seo-for-restaurants.html
│   ├── seo-for-pet-services.html
│   ├── seo-for-plumbers.html
│   ├── seo-for-hvac.html
│   ├── seo-for-electricians.html
│   ├── seo-for-roofing.html
│   ├── seo-for-real-estate.html
│   ├── seo-for-auto-repair.html
│   ├── seo-for-cleaning.html
│   ├── seo-for-movers.html
│   ├── seo-for-landscaping.html
│   ├── seo-for-photographers.html
│   └── seo-for-construction.html
│
│   ├── # ---- BLOG POSTS (6) ----
│   └── blog/
│       ├── ai-seo-chatgpt-citations-2026.html
│       ├── dentists-google-maps-2026.html
│       ├── ethical-review-generation-guide.html
│       ├── gbp-optimization-guide-2026.html
│       ├── lawyers-more-leads-google.html
│       └── restaurant-local-seo-2026.html
│
├── dashboard/                          # Backend system (FastAPI)
│   ├── main.py                         # Main backend (3379 lines) — 99+ API endpoints
│   ├── database.py                     # Database setup (724 lines) — 28 tables, seed data
│   ├── requirements.txt                # Python dependencies
│   ├── pyproject.toml                  # Project metadata
│   ├── agency.db                       # SQLite database file
│   ├── generate_templates.py           # Template generator utility
│   │
│   ├── static/css/
│   │   └── dashboard.css               # Dashboard stylesheet
│   │
│   └── templates/                      # 16 Jinja2 dashboard templates
│       ├── login.html                  # Login page (all 7 roles)
│       ├── admin_dashboard.html        # Super Admin dashboard
│       ├── worker_dashboard.html       # Tech SEO / Social Media worker dashboard
│       ├── sales_dashboard.html        # Sales team dashboard
│       ├── finance_dashboard.html      # Finance dashboard (payments, expenses, salaries)
│       ├── ops_dashboard.html          # Operations manager dashboard
│       ├── client_portal.html          # Client portal dashboard
│       ├── social_dashboard.html       # Social media dashboard
│       ├── settings.html               # API Settings & Integrations (admin only)
│       ├── analytics.html              # Analytics dashboard
│       ├── performance.html            # Performance metrics
│       ├── activity_timeline.html      # Activity timeline
│       ├── rankings_chart.html         # Keyword rankings chart
│       ├── client_detail.html          # Individual client detail page
│       ├── monitor.html                # Team monitor / live view
│       └── team_chat.html              # Internal team chat
│
├── templates/                          # Agency operations templates
│   ├── index.html                      # Templates listing page
│   ├── ai-seo-agency-os.html           # Agency operating system overview
│   ├── client-proposal.html            # Client proposal template
│   ├── client-reporting.html           # Client reporting template
│   ├── competitor-styles.html          # Competitor analysis styles
│   ├── discovery-call.html             # Discovery call script
│   ├── dna-audit-prompt-level1.html    # DNA audit AI prompt (basic)
│   ├── dna-audit-prompt-level2.html    # DNA audit AI prompt (advanced)
│   ├── kickoff-call.html               # Client kickoff call guide
│   ├── onboarding-form.html            # Client onboarding form
│   ├── pro-tips-working-patterns.html  # Pro tips & patterns
│   └── service-*.html                  # Individual service delivery guides (6 files)
│
├── # ---- DOCUMENTATION ----
├── README.md                           # Project overview
├── API_GUIDE.md                        # Complete API documentation
├── DATA_TREE.md                        # Database schema documentation
├── PROJECT_TREE.md                     # This file — complete code tree
├── DEPLOYMENT_GUIDE.md                 # Deployment instructions
├── COMPLETE_EXECUTION_GUIDE.md         # Full execution guide
├── COMPLETE_STRATEGY.md                # Business strategy document
├── FEASIBILITY_REPORT.md               # Project feasibility analysis
├── PROGRESS_LOG.md                     # Development progress log
├── PROJECT_PLAN.md                     # Project plan & timeline
├── SEO_AUDIT_REPORT.md                 # SEO audit methodology report
│
├── generate_pages.py                   # Page generator script (56 pages)
├── generate_report.py                  # PDF report generator
└── build-pages.sh                      # Build script for all pages
```

---

## Database Schema (28 Tables)

| Table | Rows | Key Columns | Purpose |
|-------|------|-------------|---------|
| `users` | 10 | id, username, password_hash, role, rank, salary | All system users (7 roles) |
| `clients` | 7 | id, business_name, email, industry, package, monthly_payment | Client accounts |
| `projects` | 6 | id, client_id, title, service_type, status, assigned_worker_id | Active projects |
| `tasks` | 11 | id, project_id, title, status, assigned_to, priority, due_date | Task management |
| `payments` | 6 | id, client_id, amount, status, due_date, paid_date | Payment tracking |
| `expenses` | 6 | id, category, description, amount, date | Business expenses |
| `invoices` | 0 | id, client_id, invoice_number, total, status | Invoice management |
| `invoice_items` | 0 | id, invoice_id, description, quantity, rate, amount | Line items |
| `sales_leads` | 3+ | id, business_name, email, source, status | Lead pipeline |
| `client_reports` | 10 | id, client_id, report_type, report_data, pdf_path | Generated reports |
| `keyword_rankings` | 1 | id, client_id, keyword, position, search_volume | SEO rankings |
| `seo_audits` | 0 | id, client_id, website_url, audit_data, overall_score | Stored audits |
| `api_settings` | 0 | id, provider, api_key, is_active, config_json | API integrations |
| `function_configs` | 3 | function_name, provider, updated_by | Function→API mapping |
| `package_tasks` | 82 | id, package, category, title, is_automated | Package task templates |
| `activity_log` | 1 | id, user_id, action, details, entity_type | Audit trail |
| `notifications` | 4 | id, user_id, title, message, type, is_read | User notifications |
| `chat_messages` | 0 | id, session_id, visitor_name, messages, status | AI chat sessions |
| `team_chats` | 0 | id, from_user_id, to_user_id, message | Internal chat |
| `social_posts` | 0 | id, client_id, platform, content, status | Social media posts |
| `time_entries` | 0 | id, user_id, task_id, hours, notes | Time tracking |
| `contracts` | 0 | id, client_id, title, monthly_value, status | Client contracts |
| `approval_requests` | 0 | id, task_id, request_type, status | Approval workflow |
| `suggestions` | 0 | id, user_id, title, description, status | Team suggestions |
| `client_credentials` | 0 | id, client_id, credential_type, username, password_enc | Client logins |
| `client_locations` | 0 | id, client_id, location_name, address, gbp_url | Multi-location |
| `file_attachments` | 0 | id, related_type, filename, filepath | File uploads |
| `chat_requests` | 0 | id, from_user_id, to_user_id, status | Chat requests |

---

## API Endpoints (99+)

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/login` | Login page |
| POST | `/login` | Authenticate user |
| GET | `/logout` | Logout & clear session |

### Dashboard Pages (Role-based)
| Method | Endpoint | Access |
|--------|----------|--------|
| GET | `/dashboard` | Auto-redirects based on role |
| GET | `/settings` | Super Admin only |
| GET | `/analytics` | Admin, Ops Manager |
| GET | `/performance` | Admin, Ops Manager |
| GET | `/monitor` | Admin, Ops Manager |
| GET | `/activity` | Admin |
| GET | `/team-chat` | All authenticated users |

### Client Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/clients` | List all clients |
| POST | `/api/clients` | Create new client |
| GET | `/api/clients/{id}` | Get client details |
| PUT | `/api/clients/{id}` | Update client |
| GET | `/client/{id}` | Client detail page |

### Project Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects` | List projects |
| POST | `/api/projects` | Create project |
| PUT | `/api/projects/{id}` | Update project |

### Task Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tasks` | List tasks |
| POST | `/api/tasks` | Create task |
| PUT | `/api/tasks/{id}` | Update task |
| PUT | `/api/tasks/{id}/status` | Change task status |

### Financial
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/payments` | List payments |
| POST | `/api/payments` | Record payment |
| GET | `/api/expenses` | List expenses |
| POST | `/api/expenses` | Add expense |
| GET | `/api/invoices` | List invoices |
| POST | `/api/invoices` | Create invoice |
| GET | `/api/salaries` | List salaries |
| GET | `/api/financial-summary` | Summary stats |
| GET | `/api/export/payments` | CSV export |

### SEO & Audit
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/public/free-audit` | **Free DNA audit — 16 pillars, real crawl** |
| POST | `/api/audit/{client_id}` | Run audit for a client |
| GET | `/api/rankings/{client_id}` | Keyword rankings |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports/{client_id}` | List reports |
| POST | `/api/reports/generate/{client_id}` | Generate report |
| GET | `/reports/{client_id}/{report_id}` | View report |

### Settings & Integrations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings/api` | List API settings |
| POST | `/api/settings/api` | Save API key |
| GET | `/api/settings/function-config` | Get function configs |
| POST | `/api/settings/function-config` | Save function config |
| GET | `/api/integrations/status` | Check all integration statuses |

### Communication
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/team-chat` | Get chat messages |
| POST | `/api/team-chat` | Send chat message |
| GET | `/api/notifications` | Get notifications |
| PUT | `/api/notifications/{id}/read` | Mark as read |
| POST | `/api/chat/sessions` | Create AI chat session |

### Public (No Login)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/public/free-audit` | Free SEO audit |
| POST | `/api/public/contact` | Contact form submission |

---

## User Roles & Access

| Role | Username | Password | Dashboard Access |
|------|----------|----------|-----------------|
| Super Admin | admin | admin123 | Everything — clients, projects, tasks, payments, analytics, settings, team |
| Tech SEO Worker | sarah_k | password123 | Kanban board, time tracker, assigned projects, SEO audit tools |
| Sales | lisa_c | password123 | Lead pipeline, proposals, client list, sales metrics |
| Social Media | marcus_j | password123 | Social posts, tasks, assigned projects |
| Finance | rachel_g | password123 | Payments, expenses, salaries, invoices, CSV export, reports |
| Ops Manager | ops_manager | password123 | Team workload, all projects, tasks, performance metrics |
| Client Portal | client_chen | password123 | Own projects, task progress, rankings, reports |

---

## Free DNA Audit — 16 Pillars (All AI Automated)

The free audit performs a **real website crawl** and checks 16 categories:

| # | Pillar | What It Checks |
|---|--------|----------------|
| 1 | Technical SEO | Title tag, meta description, H1/H2/H3, canonical, robots.txt, sitemap, language |
| 2 | On-Page SEO | Internal/external links, images, alt text, favicon, broken links |
| 3 | Content Quality | Word count, forms, phone/email presence, content depth |
| 4 | Schema & JSON-LD | Structured data blocks, schema types (LocalBusiness, Organization, etc.) |
| 5 | Social Media SEO | Open Graph tags (title, description, image) |
| 6 | Security & SSL | HTTPS, security headers (CSP, HSTS, X-Frame, etc.) |
| 7 | Performance | Server response time, HTML size, JS/CSS file count |
| 8 | Mobile Readiness | Viewport meta tag, responsive CSS (@media queries) |
| 9 | Core Web Vitals | Render-blocking JS/CSS, images without dimensions, preload hints, inline handlers |
| 10 | AI Crawler Access | GPTBot, ClaudeBot, ChatGPT-User, Google-Extended, PerplexityBot blocking check |
| 11 | Image Alt Text & WebP | Image format breakdown (JPG/PNG/WebP/AVIF), alt text coverage |
| 12 | XML Sitemap Validation | Sitemap exists, URL count, lastmod dates, priority tags |
| 13 | Robots.txt Check | Exists, sitemap reference, crawl-delay, disallow rule count |
| 14 | Internal Linking Depth | Nav links, footer links, body links, link-to-text ratio |
| 15 | Canonical Mismatch | Domain mismatch, protocol mismatch, path mismatch detection |
| 16 | E-E-A-T Author Signals | Author attribution, about page, contact info, social proof, credentials |

### Report Output Categories
- **⚡ AI Automated Tasks** — Tasks AI handles automatically (no login needed)
- **👨‍💻 Human Action Required** — Tasks needing content creation or design decisions
- **🔑 Login Credentials Required** — Tasks requiring third-party API keys (with links where to get them)

---

## Design System (2026 Dark Luxury)

| Property | Value |
|----------|-------|
| Primary BG | `#050810` (deep space black) |
| Secondary BG | `#0A0F1E` (dark navy) |
| Card BG | `#0F1629` |
| Accent Primary | `#00D4FF` (electric cyan) |
| Accent Secondary | `#7B2FFF` (deep violet) |
| Accent Glow | `#00FF88` (neon green) |
| Display Font | Cabinet Grotesk (via Fontshare) |
| Body Font | Satoshi (via Fontshare) |
| Mono Font | JetBrains Mono |
| Icons | 47 premium gradient dual-tone SVGs (inline) |

---

## API Integrations (9 Providers)

| Provider | Purpose | Cost |
|----------|---------|------|
| Claude AI | SEO audits, content generation, competitor analysis | ~$0.003/1K tokens |
| ChatGPT | Same as Claude (alternative) | ~$0.002/1K tokens |
| Google Gemini | Same as Claude (alternative) | Free tier available |
| SMTP (Gmail) | Email reports, notifications | Free (Gmail App Password) |
| Twilio | Voice calls, SMS, AI voice agent | $1/mo + per-call |
| WhatsApp Business | Client messaging, report sharing | Free (Meta Business account) |
| Slack | Team notifications | Free |
| Stripe | Billing, invoicing, subscriptions | 2.9% + 30¢/txn |
| Google Search Console | Real keyword rankings, click/impression data | Free (OAuth setup) |
