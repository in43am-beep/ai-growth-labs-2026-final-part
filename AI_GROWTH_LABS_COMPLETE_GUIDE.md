# RankForge AI — Complete System Guide & Operations Manual

> **Version:** 2.0 | **Date:** May 2026 | **Status:** Production Ready
> **Frontend:** 56 pages | **Backend:** 99+ API endpoints | **Database:** 28 tables

---

## TABLE OF CONTENTS

1. [System Overview](#1-system-overview)
2. [Dashboard Roles & Access](#2-dashboard-roles--access)
3. [API Settings — How to Configure](#3-api-settings--how-to-configure)
4. [Free DNA Audit — How It Works](#4-free-dna-audit--how-it-works)
5. [Lead Generation Flow](#5-lead-generation-flow)
6. [Client Management](#6-client-management)
7. [Financial Management](#7-financial-management)
8. [Team Operations](#8-team-operations)
9. [API Cost Analysis](#9-api-cost-analysis)
10. [What You Need To Do (Branding & Setup)](#10-what-you-need-to-do)
11. [Production Launch Checklist](#11-production-launch-checklist)

---

## 1. System Overview

### Architecture
```
┌─────────────────────────────────────────────────┐
│              FRONTEND (Static HTML)              │
│  56 pages — Services, Industries, Blog, Audit    │
│  CSS: Dark luxury theme with glassmorphism       │
│  JS: Mega menu, counter animation, lazy load     │
│  Forms: Contact → backend, Audit → backend       │
└──────────────────────┬──────────────────────────┘
                       │ API calls
                       ▼
┌─────────────────────────────────────────────────┐
│              BACKEND (FastAPI + Python)           │
│  99+ REST API endpoints                          │
│  JWT session authentication                      │
│  SQLite database (agency.db)                     │
│  16 Jinja2 dashboard templates                   │
│  Real website crawler for audits                 │
│  9 API integrations (all configurable)           │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              DATABASE (SQLite)                   │
│  28 tables: users, clients, projects, tasks,     │
│  payments, invoices, leads, reports, audits,     │
│  api_settings, function_configs, etc.            │
│  10 demo users, 7 clients, 6 projects preloaded │
└─────────────────────────────────────────────────┘
```

### Tech Stack
| Component | Technology |
|-----------|-----------|
| Frontend | Vanilla HTML5/CSS3/JS |
| Backend | Python FastAPI |
| Database | SQLite |
| Auth | bcrypt password hashing + JWT sessions |
| Fonts | Cabinet Grotesk + Satoshi (Fontshare) |
| Icons | 47 inline gradient SVGs |
| Audit Engine | Real crawler (BeautifulSoup + requests) |

---

## 2. Dashboard Roles & Access

### 7 Role Types

#### 🔴 Super Admin (admin / admin123)
**Full system access — everything:**
- Dashboard: Client count, revenue, active projects, task stats
- Clients: Create, edit, view all clients with details
- Projects: Assign workers, set priorities, track progress
- Tasks: Create, assign, manage all tasks
- Payments: Record payments, view history
- Analytics: Traffic, rankings, revenue graphs
- Settings: **API key management, integration config**
- Team: View all workers, monitor activity
- Reports: Generate & view client reports
- Activity: Full audit trail of all actions

**How to use:**
1. Login → `/login` → admin / admin123
2. Dashboard shows overview of everything
3. Sidebar has all navigation options
4. Settings page (`/settings`) is where you put API keys

---

#### 🟢 Tech SEO Worker (sarah_k / password123)
**SEO execution & task management:**
- Kanban Board: Drag tasks between To-Do, In Progress, Done
- Assigned Projects: 5 active projects shown
- Time Tracker: Log hours per task
- SEO Audit: Can run audits on client websites
- Tasks: Only sees tasks assigned to them

---

#### 🟡 Sales (lisa_c / password123)
**Lead pipeline & proposals:**
- Lead Pipeline: New → Contacted → Qualified → Proposal → Won/Lost
- 3 demo leads with scores and values
- Client List: View all active clients
- Proposals: Create & send proposals
- Sales Metrics: Close rate, pipeline value

---

#### 🟣 Social Media (marcus_j / password123)
**Social content & scheduling:**
- Tasks assigned to social media projects
- Social post creation & scheduling
- Content calendar view

---

#### 🔵 Finance (rachel_g / password123)
**Money management:**
- Payments: Record & track all payments ($25K+ in demo data)
- Expenses: Track business expenses ($9K+ in demo)
- Salaries: View team salary info
- Invoices: Create & manage invoices
- **Report button**: Generate full client report (opens in new tab)
- CSV Export: Download payment data
- Financial Summary: Revenue, expenses, profit

---

#### 🟤 Ops Manager (ops_manager / password123)
**Team oversight & project management:**
- All Projects: View & manage all 6+ projects
- Team Workload: See who's assigned to what
- Performance Metrics: Team productivity stats
- Task Management: Assign & reassign tasks

---

#### ⚪ Client Portal (client_chen / password123)
**Client self-service:**
- Own Projects: See their projects and progress
- Task Status: Visual progress bars
- Rankings: Keyword position tracking
- Reports: View reports shared by team

---

## 3. API Settings — How to Configure

### Where: Admin Dashboard → Settings (`/settings`)

The settings page has 3 sections:

### Section 1: API Providers (Key Input Fields)

| Provider | Field(s) | Where to Get Key | Cost |
|----------|----------|-----------------|------|
| **Claude AI** | API Key | [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) | ~$0.003/1K tokens (~$5-15/mo) |
| **ChatGPT** | API Key | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | ~$0.002/1K tokens (~$5-15/mo) |
| **Google Gemini** | API Key | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) | Free tier: 60 req/min |
| **SMTP (Gmail)** | App Password + From Email | [Google App Passwords](https://myaccount.google.com/apppasswords) | Free |
| **Twilio** | Auth Token + Account SID + Phone | [console.twilio.com](https://console.twilio.com) | $1/mo + $0.0085/min |
| **WhatsApp** | API Token + Phone Number ID | [developers.facebook.com](https://developers.facebook.com/apps) | Free (Meta Business) |
| **Slack** | Bot Token + Channel | [api.slack.com/apps](https://api.slack.com/apps) | Free |
| **Stripe** | Secret Key + Pub Key + Webhook | [dashboard.stripe.com/apikeys](https://dashboard.stripe.com/apikeys) | 2.9% + 30¢/txn |
| **Google Search Console** | OAuth Token + Client ID/Secret + Property URL | [console.cloud.google.com](https://console.cloud.google.com/apis/credentials) | Free |

**How to add:**
1. Login as admin → Go to Settings
2. Find the provider card
3. Paste API key in the input field
4. Fill extra fields if needed (e.g., Twilio SID, SMTP email)
5. Click "Save & Activate"
6. Status badge changes to "Active" ✓
7. Key is saved in database → backend uses it automatically

### Section 2: Function-Specific Configuration

Each feature can use a different API provider:

| Function | Options | What It Powers |
|----------|---------|---------------|
| Free DNA Audit | Always Active (Real Crawler) | 16-pillar website audit — no API needed |
| Content Generation | Demo / Claude / ChatGPT / Gemini | Blog posts, ad copy, social content, emails |
| AI Chat Assistant | Demo / Claude / ChatGPT / Gemini | SEO Q&A, strategy suggestions, real-time answers |
| Competitor Analysis | Demo / Claude / ChatGPT / Gemini | Website comparison, gap analysis, strategy |
| Email Notifications | Demo / SMTP | Lead alerts, report delivery, payment reminders |
| Voice Calls & IVR | Demo / Twilio | Inbound/outbound calls, AI voice agent, SMS |
| Client Messaging | Demo / WhatsApp / Slack | Client updates, report sharing, team notifications |
| Billing & Payments | Demo / Stripe | Invoicing, subscriptions, payment processing |

**How to configure:**
1. Select provider from dropdown
2. Click "Save Preference"
3. Make sure the selected provider's API key is configured in Section 1

### Section 3: Integration Guide
Reference cards explaining what each integration does and its cost.

---

## 4. Free DNA Audit — How It Works

### User Journey
```
Client visits website → Free Audit page → Enters URL + business name
       ↓
    Form submits to /api/public/free-audit
       ↓
    Backend CRAWLS the actual website (real HTTP request)
       ↓
    Analyzes HTML: title, meta, headings, images, links,
    schema, SSL, headers, robots.txt, sitemap, etc.
       ↓
    Scores 16 pillars (0-100 each)
       ↓
    Returns complete report with:
    - Overall score + grade (A/B/C/D/F)
    - 16 pillar scores with findings & recommendations
    - AI automated tasks list
    - Human required tasks list
    - Credential required tasks list (with links)
       ↓
    Client sees report → Downloads PDF → Gets follow-up
       ↓
    Lead saved in sales_leads table → Shows in Sales dashboard
```

### 16 Audit Pillars (All AI Automated)

| # | Pillar | Score Based On |
|---|--------|---------------|
| 1 | Technical SEO | Title tag (30-60 chars), meta desc (120-160), canonical, H1 count, robots, sitemap |
| 2 | On-Page SEO | Internal links (10+), external links, images with alt text, favicon, broken links |
| 3 | Content Quality | Word count (1000+), forms present, phone/email visible |
| 4 | Schema & JSON-LD | JSON-LD blocks found, schema types (LocalBusiness, Organization, FAQ) |
| 5 | Social Media SEO | og:title, og:description, og:image tags |
| 6 | Security & SSL | HTTPS active, 6 security headers checked |
| 7 | Performance | Response time (<2s), HTML size (<100KB), JS/CSS count |
| 8 | Mobile | Viewport meta tag, @media queries in CSS |
| 9 | Core Web Vitals | Render-blocking JS/CSS, images without width/height, preload hints |
| 10 | AI Crawler Access | GPTBot, ClaudeBot, ChatGPT-User, Google-Extended, PerplexityBot blocked? |
| 11 | Image & WebP | Alt text coverage, WebP/AVIF usage percentage |
| 12 | XML Sitemap | Exists, URL count, lastmod dates, priority tags |
| 13 | Robots.txt | Exists, sitemap reference, crawl-delay, disallow rules |
| 14 | Internal Linking | Nav links, footer links, body links, link-to-text ratio |
| 15 | Canonical | Domain match, protocol match, path match vs actual URL |
| 16 | E-E-A-T | Author tags, about page, contact info, testimonials, credentials |

### Where Do Audit Leads Go?
- Saved in `sales_leads` table with source="free_audit"
- Visible in **Sales Dashboard** (lisa_c login) → Lead Pipeline
- Admin can see all leads in admin dashboard
- Lead includes: business name, email, phone, website, audit score

### Who Completes the Audit?
- **AI does everything automatically** — no human needed for the basic audit
- For deeper analysis (backlinks, real CWV, keyword research), human uses external tools
- Report clearly separates what AI did vs what needs human action

---

## 5. Lead Generation Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Free Audit  │     │ Contact Form │     │  AI Chat     │
│  Form        │     │              │     │  Widget      │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            ▼
               ┌────────────────────────┐
               │   sales_leads table    │
               │   Source: free_audit / │
               │   contact_form / chat  │
               │   Status: new          │
               └────────────┬───────────┘
                            ▼
               ┌────────────────────────┐
               │  Sales Dashboard       │
               │  (lisa_c login)        │
               │  Lead Pipeline:        │
               │  New → Contacted →     │
               │  Qualified → Proposal  │
               │  → Won / Lost          │
               └────────────┬───────────┘
                            ▼
               ┌────────────────────────┐
               │  Convert to Client     │
               │  Create Project        │
               │  Assign Workers        │
               └────────────────────────┘
```

---

## 6. Client Management

### Client Lifecycle
1. **Lead captured** (audit/contact/chat) → appears in sales pipeline
2. **Sales qualifies** → creates proposal → client signs
3. **Admin creates client** → assigns package (Starter/Growth/Pro)
4. **Project created** → assigned to workers
5. **Workers execute** → update tasks, log time
6. **Reports generated** → sent to client
7. **Client views** → through client portal
8. **Finance tracks** → payments, invoices

### Packages
| Package | Monthly | Includes |
|---------|---------|----------|
| Starter | $1,500 | Basic local SEO, GBP optimization, monthly report |
| Growth | $3,000 | Full SEO, content, social media, weekly reports |
| Pro | $5,000 | Everything + paid ads, link building, daily monitoring |

---

## 7. Financial Management

### Finance Dashboard Features (rachel_g login)
- **Payment Records**: All client payments with status tracking
- **Expense Tracking**: Categorized business expenses
- **Salary Info**: Team member salary data
- **Invoice Management**: Create, send, track invoices
- **Report Generation**: Click "Report" button → full client report in new tab
- **CSV Export**: Download payment data as CSV file
- **Financial Summary**: Total revenue, expenses, profit margin

---

## 8. Team Operations

### Workflow
```
Admin assigns project → Worker sees in dashboard → Worker updates tasks
       ↓                                                    ↓
  Ops Manager monitors                              Time entries logged
       ↓                                                    ↓
  Performance tracked                               Reports generated
       ↓                                                    ↓
  Activity logged                                    Client notified
```

### Communication
- **Team Chat**: Internal messaging between all users
- **Notifications**: Auto-generated alerts for new leads, task completions, payments
- **Activity Timeline**: Full audit trail of all actions

---

## 9. API Cost Analysis

### Monthly Cost Estimates

| Scenario | AI Provider | SMTP | Twilio | Stripe | Total/mo |
|----------|------------|------|--------|--------|----------|
| **Minimal (Demo)** | $0 | $0 | $0 | $0 | **$0** |
| **Basic (10 clients)** | $10 (Gemini free) | $0 (Gmail) | $5 | 2.9%+30¢ | **~$15** |
| **Growth (50 clients)** | $30 (Claude) | $0 (Gmail) | $20 | 2.9%+30¢ | **~$50** |
| **Pro (100+ clients)** | $100 (Claude) | $10 (SendGrid) | $50 | 2.9%+30¢ | **~$160** |

### Free Alternatives
| Paid Service | Free Alternative |
|-------------|-----------------|
| Ahrefs ($99/mo) | Google Search Console (free) + Ubersuggest (limited free) |
| SEMrush ($130/mo) | Google Keyword Planner (free) + SimilarWeb (free tier) |
| Moz Pro ($99/mo) | MozBar extension (free) + Google Search Console |
| Twilio ($1+/mo) | WhatsApp Business API (free tier) |
| SendGrid ($15/mo) | Gmail App Password (free, 500/day limit) |
| Stripe (2.9%) | PayPal (2.9%) or manual invoicing |

---

## 10. What You Need To Do

### Branding (Replace Placeholders)

| What | Current Placeholder | Replace With |
|------|-------------------|-------------|
| GA4 ID | `G-XXXXXXXXXX` | Your Google Analytics Measurement ID |
| Tawk.to | `YOUR_PROPERTY_ID/YOUR_WIDGET_ID` | Your Tawk.to IDs from [dashboard.tawk.to](https://dashboard.tawk.to) |
| Calendly | `calendly.com/rankforgeai/strategy-call` | Your real Calendly booking link |
| Social Links | facebook.com/rankforgeai etc. | Your real social media profile URLs |
| Team Photos | Placeholder initials on About page | Real team member photos |
| Phone | +1 (800) 971-0199 | Your real business phone number |
| Email | hello@YOUR_DOMAIN_HERE | Your real business email |
| Logo | "RankForgeAI" text | Your actual logo/branding |
| OG Image | Generic branded image | Custom branded OG image (1200x630px) |
| Canonical URLs | devinapps.com domain | Your production domain |
| FormSubmit | FormSubmit.co endpoint | Your email for form submissions |

### API Keys (Add in Admin Settings)

**Minimum to start (Free):**
1. Google Gemini API key (free tier) — enables AI features
2. Gmail App Password (free) — enables email notifications

**Recommended:**
3. Claude or ChatGPT API key — better AI quality
4. Stripe keys — enable payment processing
5. Google Search Console — real ranking data

### Domain & Hosting
1. Buy domain (e.g., YOUR_DOMAIN_HERE)
2. Host frontend on Vercel/Netlify (free)
3. Host backend on Render/Railway/Fly.io ($5-7/mo)
4. Point domain DNS to hosting
5. Update all canonical URLs to new domain
6. Update all internal links

---

## 11. Production Launch Checklist

- [ ] Replace all placeholder text (phone, email, social links)
- [ ] Add real team photos on About page
- [ ] Set up Google Analytics (replace G-XXXXXXXXXX)
- [ ] Set up Tawk.to live chat (replace property/widget IDs)
- [ ] Connect real Calendly link
- [ ] Add at least one AI API key (Gemini is free)
- [ ] Set up Gmail App Password for SMTP
- [ ] Configure domain & hosting
- [ ] Update canonical URLs to production domain
- [ ] Update OG image URLs to production domain
- [ ] Test all forms (contact, audit)
- [ ] Test all 7 demo logins work
- [ ] Test free audit on 3+ websites
- [ ] Set up Stripe for payments (optional)
- [ ] Set up Google Search Console (optional)
- [ ] Create real content for blog posts
- [ ] Add real case studies
- [ ] Submit sitemap to Google Search Console

---

## Quick Reference

### Login URLs
- **Frontend:** `https://yourdomain.com/`
- **Backend:** `https://yourdomain.com:8000/login`
- **Settings:** `https://yourdomain.com:8000/settings`
- **Free Audit:** `https://yourdomain.com/pages/free-audit.html`

### Important Files to Edit
| Purpose | File |
|---------|------|
| Homepage | `index.html` |
| Contact info (all pages) | Search & replace in all HTML files |
| Styling | `css/style.css` |
| JavaScript | `js/main.js` |
| Backend logic | `dashboard/main.py` |
| Database schema | `dashboard/database.py` |
| Dashboard templates | `dashboard/templates/*.html` |
| API settings page | `dashboard/templates/settings.html` |

### Database Location
- `dashboard/agency.db` — SQLite file, portable, no server needed
- Backup: just copy this file
- Reset: delete file, restart server (auto-creates with seed data)
