#!/usr/bin/env python3
"""
RankForge AI - Complete System Report Generator
Generates a comprehensive PDF with charts, tables, and system documentation
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                 PageBreak, Image, HRFlowable)
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
import os, datetime

W, H = A4

# Colors
DARK_BG = colors.HexColor("#0B1120")
CYAN = colors.HexColor("#06B6D4")
DARK_CARD = colors.HexColor("#0F172A")
GREEN = colors.HexColor("#34D399")
RED = colors.HexColor("#EF4444")
AMBER = colors.HexColor("#F59E0B")
BLUE = colors.HexColor("#3B82F6")
PURPLE = colors.HexColor("#8B5CF6")
WHITE = colors.white
GRAY = colors.HexColor("#94A3B8")
LIGHT_GRAY = colors.HexColor("#E2E8F0")

def build_report():
    filename = "/home/ubuntu/repos/ai-growth-labs-new/AI_Growth_Labs_Complete_System_Report.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4, topMargin=30, bottomMargin=30,
                           leftMargin=40, rightMargin=40)

    styles = getSampleStyleSheet()
    # Custom styles
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=28,
                                  textColor=colors.HexColor("#1E293B"), spaceAfter=6,
                                  fontName='Helvetica-Bold')
    h1 = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor("#0F172A"),
                         spaceAfter=8, spaceBefore=16, fontName='Helvetica-Bold')
    h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=16, textColor=colors.HexColor("#1E3A5F"),
                         spaceAfter=6, spaceBefore=12, fontName='Helvetica-Bold')
    h3 = ParagraphStyle('H3', parent=styles['Heading3'], fontSize=13, textColor=colors.HexColor("#334155"),
                         spaceAfter=4, spaceBefore=8, fontName='Helvetica-Bold')
    body = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor("#334155"),
                           spaceAfter=4, leading=14, fontName='Helvetica')
    body_bold = ParagraphStyle('BodyBold', parent=body, fontName='Helvetica-Bold')
    small = ParagraphStyle('Small', parent=body, fontSize=8, textColor=GRAY)
    center = ParagraphStyle('Center', parent=body, alignment=TA_CENTER)
    bullet = ParagraphStyle('Bullet', parent=body, leftIndent=20, bulletIndent=10,
                             bulletFontName='Helvetica', bulletFontSize=10)

    elements = []

    def hr():
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"),
                                    spaceAfter=8, spaceBefore=8))

    def section_header(text, icon=""):
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(f"{icon} {text}", h1))
        hr()

    def sub_header(text):
        elements.append(Paragraph(text, h2))

    def add_table(data, col_widths=None, header_color=colors.HexColor("#0F172A")):
        if not col_widths:
            col_widths = [doc.width / len(data[0])] * len(data[0])
        t = Table(data, colWidths=col_widths, repeatRows=1)
        style = [
            ('BACKGROUND', (0, 0), (-1, 0), header_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, colors.HexColor("#F8FAFC")]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]
        t.setStyle(TableStyle(style))
        elements.append(t)
        elements.append(Spacer(1, 8))

    # ===================== COVER PAGE =====================
    elements.append(Spacer(1, 80))
    elements.append(Paragraph("RankForge AI", ParagraphStyle('CoverTitle', parent=title_style,
                               fontSize=42, alignment=TA_CENTER, textColor=CYAN)))
    elements.append(Paragraph("Agency Operating System", ParagraphStyle('CoverSub', parent=title_style,
                               fontSize=24, alignment=TA_CENTER, textColor=colors.HexColor("#334155"))))
    elements.append(Spacer(1, 20))
    hr()
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Complete System Guide & Documentation", ParagraphStyle('CoverDesc',
                               parent=body, fontSize=16, alignment=TA_CENTER, textColor=colors.HexColor("#64748B"))))
    elements.append(Spacer(1, 40))

    cover_data = [
        ["Document", "RankForge AI - Complete System Report"],
        ["Version", "2.0 Final"],
        ["Date", datetime.datetime.now().strftime("%B %d, %Y")],
        ["Pages", "55+ Frontend | 99+ API Endpoints | 22+ Database Tables"],
        ["Roles", "11 User Roles with Role-Based Access Control"],
        ["APIs", "9 Integration Points (Demo Mode Ready)"],
    ]
    add_table(cover_data, col_widths=[120, 370])

    elements.append(Spacer(1, 30))
    elements.append(Paragraph("CONFIDENTIAL - FOR INTERNAL USE ONLY", ParagraphStyle('Conf',
                               parent=center, fontSize=10, textColor=RED)))
    elements.append(PageBreak())

    # ===================== TABLE OF CONTENTS =====================
    elements.append(Paragraph("Table of Contents", title_style))
    hr()
    toc_items = [
        ("1. System Overview & Architecture", "What the system does, tech stack"),
        ("2. Database Structure (22+ Tables)", "Complete schema with all columns"),
        ("3. User Roles & Access Control (11 Roles)", "Who sees what, permissions matrix"),
        ("4. Backend Dashboard Order & Hierarchy", "Panel-by-panel breakdown"),
        ("5. API Integrations (9 APIs)", "Setup instructions, costs, alternatives"),
        ("6. Free Audit Form Flow", "Submission → Storage → Who sees it → Who completes it"),
        ("7. Lead Generation Workflow", "How leads come in, where they go, conversion tracking"),
        ("8. Branding Customization Guide", "What to change, where to change it"),
        ("9. Cost Analysis & Alternatives", "Monthly costs, free alternatives, scaling"),
        ("10. Production Launch Checklist", "Step-by-step to go live"),
        ("11. Revenue & Financial Overview", "Charts and projections"),
    ]
    for title, desc in toc_items:
        elements.append(Paragraph(f"<b>{title}</b>", body))
        elements.append(Paragraph(f"<i>{desc}</i>", small))
        elements.append(Spacer(1, 4))
    elements.append(PageBreak())

    # ===================== 1. SYSTEM OVERVIEW =====================
    section_header("1. System Overview & Architecture", "🏗️")

    elements.append(Paragraph("RankForge AI is a complete agency operating system built for SEO/digital marketing agencies. "
                               "It provides end-to-end management of clients, projects, tasks, billing, team performance, "
                               "and automated SEO auditing with real website crawling.", body))
    elements.append(Spacer(1, 8))

    sub_header("Tech Stack")
    stack_data = [
        ["Component", "Technology", "Purpose"],
        ["Backend", "Python FastAPI", "REST API server, authentication, business logic"],
        ["Database", "SQLite", "Persistent storage (22+ tables, easily upgradeable to PostgreSQL)"],
        ["Frontend", "HTML/CSS/JS", "55+ static pages, responsive design, dark theme"],
        ["Templates", "Jinja2", "Server-side rendered dashboard pages"],
        ["Auth", "JWT + bcrypt", "Secure session tokens, hashed passwords"],
        ["Audit Engine", "BeautifulSoup + requests", "Real website crawling & SEO analysis"],
        ["Charts", "Chart.js", "Analytics, rankings, revenue visualizations"],
        ["Deployment", "Devin Apps / Fly.io", "Frontend CDN + Backend container"],
    ]
    add_table(stack_data, col_widths=[80, 130, 280])

    elements.append(Spacer(1, 8))
    sub_header("System Architecture Diagram")
    elements.append(Paragraph("""
    <b>Frontend (55+ Pages)</b> → Static HTML/CSS/JS served via CDN<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;↓ API Calls (fetch/XHR)<br/>
    <b>Backend (FastAPI)</b> → 99+ API Endpoints, JWT Auth, Rate Limiting<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;↓ SQL Queries<br/>
    <b>Database (SQLite)</b> → 22+ Tables, Persistent Storage<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;↓ External Calls<br/>
    <b>Integrations</b> → AI APIs, SMTP, Twilio, Stripe, WhatsApp, Slack, GSC
    """, body))

    # Architecture bar chart
    d = Drawing(480, 200)
    bc = VerticalBarChart()
    bc.x = 50; bc.y = 30; bc.height = 140; bc.width = 400
    bc.data = [[55, 99, 22, 11, 9, 16, 7]]
    bc.categoryAxis.categoryNames = ['Pages', 'API Endpoints', 'DB Tables', 'User Roles', 'Integrations', 'Templates', 'Demo Users']
    bc.bars[0].fillColor = CYAN
    bc.valueAxis.valueMin = 0; bc.valueAxis.valueMax = 110
    bc.categoryAxis.labels.fontSize = 7
    bc.valueAxis.labels.fontSize = 8
    d.add(bc)
    d.add(String(200, 180, 'System Components', fontSize=11, fontName='Helvetica-Bold', fillColor=colors.HexColor("#1E293B")))
    elements.append(d)
    elements.append(PageBreak())

    # ===================== 2. DATABASE STRUCTURE =====================
    section_header("2. Database Structure (22+ Tables)", "🗄️")

    elements.append(Paragraph("The system uses SQLite with 22+ tables. Below is the complete schema:", body))

    db_tables = [
        ["Table Name", "Purpose", "Key Columns"],
        ["users", "All system users (11 roles)", "id, username, password_hash, role, full_name, salary, rank"],
        ["clients", "Client businesses", "id, business_name, contact_name, email, website, industry, location, package, status"],
        ["projects", "Active campaigns", "id, client_id, name, service_type, progress, status, assigned_worker_id"],
        ["tasks", "Individual task items", "id, project_id, title, status, priority, assigned_to, due_date"],
        ["payments", "Payment records", "id, client_id, amount, status (paid/pending/overdue), invoice_number"],
        ["expenses", "Business expenses", "id, category, description, amount, date"],
        ["keyword_rankings", "SEO rankings", "id, client_id, keyword, position, previous_position, search_volume"],
        ["sales_leads", "Incoming leads", "id, business_name, email, phone, source, status, notes"],
        ["invoices", "Generated invoices", "id, client_id, amount, status, items_json"],
        ["contracts", "Client contracts", "id, client_id, title, start_date, end_date, value, status"],
        ["time_entries", "Time tracking", "id, user_id, task_id, start_time, end_time, hours"],
        ["client_reports", "Monthly reports", "id, client_id, report_data, sent_to_client"],
        ["activity_log", "System activity", "id, user_id, action_type, description, timestamp"],
        ["api_settings", "API configurations", "id, provider, api_key, status, config_json"],
        ["function_configs", "Per-function API", "function_name, provider, updated_by"],
        ["approval_requests", "Client approvals", "id, client_id, title, description, status"],
        ["notifications", "User notifications", "id, user_id, type, message, is_read"],
        ["social_posts", "Social media posts", "id, client_id, platform, content, scheduled_date"],
        ["client_credentials", "Client tool logins", "id, client_id, credential_type, username, password_enc"],
        ["client_locations", "Multi-location", "id, client_id, location_name, address, phone, gbp_url"],
        ["chat_messages", "Team chat", "id, sender_id, receiver_id, message, timestamp"],
        ["chat_requests", "Chat request queue", "id, from_user_id, to_user_id, status"],
    ]
    add_table(db_tables, col_widths=[85, 115, 290])
    elements.append(PageBreak())

    # ===================== 3. USER ROLES =====================
    section_header("3. User Roles & Access Control (11 Roles)", "👥")

    elements.append(Paragraph("The system supports 11 distinct user roles. Each role has specific dashboard views and permissions:", body))

    roles_data = [
        ["Role", "Username", "Dashboard", "Key Permissions"],
        ["Super Admin", "admin", "Full admin dashboard", "Everything - clients, projects, tasks, payments, analytics, settings, audit, team"],
        ["Tech SEO", "sarah_k", "Worker dashboard", "Own tasks, projects, time tracking, SEO audit tool, suggestions"],
        ["Sales", "lisa_c", "Sales dashboard", "Lead pipeline, proposals, client list, lead collection tools"],
        ["Social Media", "marcus_j", "Worker dashboard", "Own tasks, social posts, projects, time tracker"],
        ["Finance", "rachel_g", "Finance dashboard", "Payments, expenses, salaries, invoices, CSV export, reports"],
        ["Ops Manager", "ops_manager", "Operations dashboard", "Team workload, all projects, tasks, approvals, performance, analytics"],
        ["Client", "client_chen", "Client portal", "Own projects, tasks, rankings, reports, invoices, approvals"],
        ["Worker", "david_w", "Worker dashboard", "Own tasks, projects, time tracking, suggestions"],
        ["Content Writer", "(create)", "Worker dashboard", "Content tasks, writing assignments"],
        ["Client Manager", "(create)", "Dashboard", "Client relationship management"],
        ["Finance Manager", "(create)", "Finance dashboard", "Extended finance permissions"],
    ]
    add_table(roles_data, col_widths=[75, 65, 105, 245])

    elements.append(Spacer(1, 12))
    sub_header("Role Access Matrix")
    access_data = [
        ["Feature", "Super Admin", "Ops Mgr", "Tech SEO", "Sales", "Finance", "Social", "Client"],
        ["Dashboard Stats", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes"],
        ["All Clients", "Yes", "Yes", "No", "Yes", "No", "No", "Own Only"],
        ["All Projects", "Yes", "Yes", "Own", "No", "No", "Own", "Own"],
        ["All Tasks", "Yes", "Yes", "Own", "Own", "No", "Own", "View"],
        ["Payments", "Yes", "No", "No", "No", "Yes", "No", "Own"],
        ["Invoices", "Yes", "No", "No", "No", "Yes", "No", "Own"],
        ["Analytics", "Yes", "Yes", "No", "No", "Yes", "No", "No"],
        ["Settings/API", "Yes", "No", "No", "No", "No", "No", "No"],
        ["SEO Audit", "Yes", "No", "Yes", "No", "No", "No", "No"],
        ["Team Monitor", "Yes", "Yes", "No", "No", "No", "No", "No"],
        ["Activity Log", "Yes", "Yes", "No", "No", "No", "No", "No"],
        ["Performance", "Yes", "Yes", "No", "No", "No", "No", "No"],
        ["CSV Export", "Yes", "Yes", "No", "No", "Yes", "No", "No"],
        ["Report Gen", "Yes", "Yes", "No", "No", "Yes", "No", "View"],
    ]
    add_table(access_data, col_widths=[75, 55, 55, 55, 50, 55, 50, 50])

    # Pie chart for roles
    d = Drawing(400, 180)
    pc = Pie()
    pc.x = 100; pc.y = 10; pc.width = 150; pc.height = 150
    pc.data = [1, 2, 1, 1, 1, 1, 2, 1, 1]
    pc.labels = ['Admin', 'Tech SEO', 'Sales', 'Social', 'Finance', 'Ops', 'Worker', 'Client', 'Other']
    pc.slices[0].fillColor = CYAN
    pc.slices[1].fillColor = GREEN
    pc.slices[2].fillColor = AMBER
    pc.slices[3].fillColor = PURPLE
    pc.slices[4].fillColor = BLUE
    pc.slices[5].fillColor = RED
    pc.slices[6].fillColor = colors.HexColor("#6366F1")
    pc.slices[7].fillColor = colors.HexColor("#EC4899")
    pc.slices[8].fillColor = GRAY
    pc.sideLabels = True
    pc.slices.fontSize = 7
    d.add(pc)
    d.add(String(130, 170, 'User Roles Distribution', fontSize=10, fontName='Helvetica-Bold'))
    elements.append(d)
    elements.append(PageBreak())

    # ===================== 4. BACKEND DASHBOARD ORDER =====================
    section_header("4. Backend Dashboard Order & Hierarchy", "📊")

    elements.append(Paragraph("Each role gets a customized dashboard view. Here's the complete panel order for each:", body))

    sub_header("Super Admin Dashboard (admin)")
    admin_panels = [
        ["#", "Panel / Section", "Description"],
        ["1", "Stats Overview", "Monthly Revenue, Total Collected, Pending, Active Clients/Projects, Task Completion"],
        ["2", "All Projects", "Table: Client, Project, Service, Worker, Lead, Progress, Priority, Status"],
        ["3", "All Clients", "Table: Business, Contact, Industry, Location, Package, Payment, Status, View"],
        ["4", "Team Members", "Table: Name, Role, Rank, Salary, Status"],
        ["5", "Recent Tasks", "Table: Task, Project, Assigned, Priority, Status"],
        ["6", "Payment Records", "Table: Invoice, Client, Amount, Due Date, Paid Date, Status, Report Gen"],
        ["7", "Invoices", "Custom invoice creation"],
        ["8", "Keyword Rankings", "Rankings table per client with position tracking"],
        ["9", "Active Contracts", "Contract management"],
        ["10", "SEO DNA Audit", "Run audit on any website with AI provider selection"],
    ]
    add_table(admin_panels, col_widths=[25, 110, 355])

    sub_header("Sidebar Navigation (Super Admin)")
    nav_data = [
        ["Link", "Type", "Destination"],
        ["Dashboard", "Page section", "Main dashboard overview"],
        ["Clients", "Hash anchor", "#clients-section on dashboard"],
        ["Projects", "Hash anchor", "#projects-section on dashboard"],
        ["Tasks", "Hash anchor", "#tasks-section on dashboard"],
        ["Workers", "Hash anchor", "#workers-section on dashboard"],
        ["Payments", "Hash anchor", "#payments-section on dashboard"],
        ["SEO Audit", "Hash anchor", "#audit-section on dashboard"],
        ["Team Monitor", "Separate page", "/monitor - Real-time team status"],
        ["Team Chat", "Separate page", "/team-chat - Internal messaging"],
        ["Invoices", "Hash anchor", "#invoices-section on dashboard"],
        ["Rankings", "Hash anchor", "#rankings-section on dashboard"],
        ["Contracts", "Hash anchor", "#contracts-section on dashboard"],
        ["Analytics", "Separate page", "/analytics - Revenue forecasting & charts"],
        ["Activity Log", "Separate page", "/activity - System activity timeline"],
        ["Performance", "Separate page", "/performance - Worker leaderboard"],
        ["API Settings", "Separate page", "/settings - API keys & integrations"],
        ["Visit Frontend", "External link", "Opens frontend website in new tab"],
    ]
    add_table(nav_data, col_widths=[90, 75, 325])
    elements.append(PageBreak())

    sub_header("Other Role Dashboards")
    other_roles = [
        ["Role", "Dashboard Sections", "Sidebar Links"],
        ["Tech SEO / Worker", "Stats, Time Tracker, Kanban Board, My Projects, Notifications, Suggestions, SEO Audit", "Dashboard, My Tasks, My Projects, Notifications, SEO Audit, Suggestions, Team Chat"],
        ["Sales", "Stats, Lead Pipeline (Kanban), Lead Collection Tools, Recent Clients", "Dashboard, Leads, Lead Tools, Proposals, Clients, Team Chat"],
        ["Social Media", "Same as Worker + Social post creation", "Dashboard, My Tasks, My Projects, Team Chat"],
        ["Finance", "Stats (Income/Expenses/Profit), Payments, Expenses, Salaries, Invoices, CSV Export", "Dashboard, Payments, Expenses, Salaries, Invoices, Reports, Export, Analytics, Team Chat"],
        ["Ops Manager", "Stats, Team Workload, All Projects, All Tasks, Overdue, Approvals", "Dashboard, Projects, Workers, Tasks, Overdue, Approvals, Analytics, Activity, Performance, Monitor, Chat"],
        ["Client", "Stats, Your Projects, Task Progress, Rankings, Reports, Invoices, Approvals", "Dashboard, Projects, Rankings, Reports, Invoices, Approvals"],
    ]
    add_table(other_roles, col_widths=[70, 200, 220])
    elements.append(PageBreak())

    # ===================== 5. API INTEGRATIONS =====================
    section_header("5. API Integrations (9 APIs)", "🔌")

    elements.append(Paragraph("All 9 integrations work in demo mode out of the box. To activate real APIs, "
                               "go to Settings page and paste your API keys. The system automatically switches from demo to live.", body))

    api_data = [
        ["#", "API", "Purpose", "Monthly Cost", "Where to Get Key", "Settings Location"],
        ["1", "Claude AI\n(Anthropic)", "SEO audits,\ncontent gen", "$5-50/mo\n(usage)", "console.anthropic.com\n/settings/keys", "Settings → AI\nProviders"],
        ["2", "ChatGPT\n(OpenAI)", "SEO audits,\ncontent gen", "$5-50/mo\n(usage)", "platform.openai.com\n/api-keys", "Settings → AI\nProviders"],
        ["3", "Gemini\n(Google)", "SEO audits,\ncontent gen", "$0-20/mo\n(free tier)", "aistudio.google.com\n/app/apikey", "Settings → AI\nProviders"],
        ["4", "SMTP\n(Gmail)", "Email reports,\nnotifications", "FREE\n(Gmail)", "Gmail → Settings →\nApp Passwords", "Settings →\nCommunication"],
        ["5", "Twilio", "Voice calls,\nSMS, IVR", "$1/mo +\nper call", "console.twilio.com", "Settings →\nCommunication"],
        ["6", "WhatsApp\n(Meta)", "Client updates,\nreport sharing", "FREE tier\navailable", "developers.facebook\n.com/apps", "Settings →\nCommunication"],
        ["7", "Slack", "Team alerts,\nnotifications", "FREE", "api.slack.com\n/apps", "Settings →\nCommunication"],
        ["8", "Stripe", "Billing,\nsubscriptions", "2.9% +\n$0.30/txn", "dashboard.stripe\n.com/apikeys", "Settings →\nBilling"],
        ["9", "Google\nSearch Console", "Real keyword\nrankings", "FREE", "console.cloud\n.google.com", "Settings →\nAnalytics"],
    ]
    add_table(api_data, col_widths=[20, 60, 70, 55, 95, 70])

    elements.append(Spacer(1, 12))
    sub_header("API Cost Comparison Chart")

    d = Drawing(480, 200)
    bc = VerticalBarChart()
    bc.x = 60; bc.y = 30; bc.height = 140; bc.width = 380
    bc.data = [[25, 25, 10, 0, 1, 0, 0, 3, 0]]
    bc.categoryAxis.categoryNames = ['Claude', 'ChatGPT', 'Gemini', 'SMTP', 'Twilio', 'WhatsApp', 'Slack', 'Stripe', 'GSC']
    bc.bars[0].fillColor = CYAN
    bc.valueAxis.valueMin = 0; bc.valueAxis.valueMax = 30
    bc.categoryAxis.labels.fontSize = 7
    bc.valueAxis.labels.fontSize = 8
    d.add(bc)
    d.add(String(180, 180, 'Monthly API Costs (USD Estimate)', fontSize=11, fontName='Helvetica-Bold'))
    elements.append(d)

    elements.append(Spacer(1, 8))
    sub_header("Minimum vs Full Setup Costs")
    cost_data = [
        ["Setup Level", "APIs Needed", "Monthly Cost", "What You Get"],
        ["Minimum (Free)", "Real Crawler only", "$0/mo", "Free DNA audits with real crawl data, demo mode for everything else"],
        ["Basic ($5/mo)", "1 AI + Gmail SMTP", "$5-10/mo", "AI-powered audits + email reports to clients"],
        ["Standard ($30/mo)", "AI + SMTP + Stripe + Twilio", "$25-35/mo", "Full billing, voice calls, AI audits, email"],
        ["Full ($60/mo)", "All 9 APIs", "$50-70/mo", "Complete automation - AI, billing, voice, WhatsApp, Slack, GSC"],
    ]
    add_table(cost_data, col_widths=[80, 110, 70, 230])

    elements.append(Spacer(1, 8))
    sub_header("How to Add API Keys")
    elements.append(Paragraph("""
    <b>Method 1 — Dashboard UI (Recommended):</b><br/>
    1. Login as Super Admin (admin / admin123)<br/>
    2. Go to Settings page (sidebar → API Settings)<br/>
    3. Find the API card (e.g., Claude AI)<br/>
    4. Paste your API key in the input field<br/>
    5. Click "Save & Activate"<br/>
    6. Status badge changes to "Active"<br/><br/>
    <b>Method 2 — Per-Function Configuration:</b><br/>
    1. Settings page → "Function-Specific API Configuration" section<br/>
    2. Select which provider to use for each function (content, chat, email, etc.)<br/>
    3. Click "Save Preference"<br/><br/>
    <b>Method 3 — Environment Variables:</b><br/>
    Set these in your server environment:<br/>
    CLAUDE_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, TWILIO_ACCOUNT_SID,<br/>
    TWILIO_AUTH_TOKEN, STRIPE_SECRET_KEY, WHATSAPP_TOKEN, SLACK_WEBHOOK_URL,<br/>
    GSC_CLIENT_ID, SMTP_PASSWORD
    """, body))
    elements.append(PageBreak())

    # ===================== 6. FREE AUDIT FLOW =====================
    section_header("6. Free Audit Form Flow", "🔍")

    elements.append(Paragraph("The Free DNA Audit is the primary lead generation tool. Here's the complete flow:", body))

    flow_data = [
        ["Step", "What Happens", "Who Does It", "Where"],
        ["1", "Visitor fills out form on frontend\n(name, email, phone, website, industry)", "Website visitor\n(potential client)", "Frontend:\n/pages/free-audit.html"],
        ["2", "Form submits to backend API\n(/api/public/free-audit)", "Automatic\n(JavaScript)", "Backend API\n(no auth needed)"],
        ["3", "Backend crawls the website\n(BeautifulSoup + requests)", "Automatic\n(Real Crawler)", "Server-side\npython function"],
        ["4", "Audit results generated:\n8 sections scored, overall grade", "Automatic\n(scoring algorithm)", "Backend\n_build_audit_from_crawl()"],
        ["5", "Results shown to visitor instantly\n(score, grade, findings)", "Automatic\n(frontend JS)", "Free audit page\nresults section"],
        ["6", "Lead saved to sales_leads table\n(name, email, phone, website)", "Automatic\n(database insert)", "Database:\nsales_leads table"],
        ["7", "Sales team sees new lead\nin their dashboard pipeline", "Lisa Chen\n(Sales role)", "Sales Dashboard\nLead Pipeline"],
        ["8", "Sales follows up via email/phone\nusing contact info from lead", "Sales team\n(manual)", "Sales Dashboard\nor external tools"],
        ["9", "Super Admin can also see\nall leads in dashboard", "Admin\n(Super Admin)", "Admin Dashboard\nor Activity Log"],
    ]
    add_table(flow_data, col_widths=[30, 145, 80, 95])

    elements.append(Spacer(1, 12))
    sub_header("What the Audit Checks (Real Crawl)")
    audit_checks = [
        ["Category", "Score Range", "What It Checks"],
        ["Technical SEO (87/100 avg)", "0-100", "Title tag, meta description, canonical, robots.txt, sitemap, H1-H3 structure, language"],
        ["On-Page SEO (63/100 avg)", "0-100", "Internal/external links, images without alt text, broken # links, favicon, CSS/JS count"],
        ["Content Quality (75/100 avg)", "0-100", "Word count, contact forms, phone numbers, email addresses found on page"],
        ["Schema Markup (60/100 avg)", "0-100", "JSON-LD structured data, Open Graph tags for social sharing"],
        ["Security (65/100 avg)", "0-100", "HTTPS/SSL, security headers (HSTS, X-Frame, CSP, XSS Protection)"],
        ["Performance (75/100 avg)", "0-100", "Page load time, response time, page size"],
        ["Mobile (85/100 avg)", "0-100", "Viewport meta tag, responsive CSS (@media queries)"],
        ["Social (70/100 avg)", "0-100", "OG tags (title, description, image), Twitter cards"],
    ]
    add_table(audit_checks, col_widths=[110, 55, 325])
    elements.append(PageBreak())

    # ===================== 7. LEAD GENERATION WORKFLOW =====================
    section_header("7. Lead Generation Workflow", "🎯")

    elements.append(Paragraph("The system has 3 lead generation channels:", body))

    lead_channels = [
        ["Channel", "How It Works", "Where Leads Go", "Who Manages"],
        ["Free DNA Audit", "Visitor enters website URL → gets real SEO audit → lead captured", "sales_leads table → Sales Dashboard pipeline", "Sales team (lisa_c)"],
        ["Contact Form", "Visitor fills contact form → message + info captured", "sales_leads table → Sales Dashboard", "Sales team (lisa_c)"],
        ["Manual Entry", "Sales team adds leads from calls, events, outreach", "sales_leads table → Sales Dashboard", "Sales team (lisa_c)"],
    ]
    add_table(lead_channels, col_widths=[80, 160, 130, 100])

    elements.append(Spacer(1, 8))
    sub_header("Lead Pipeline Stages")
    pipeline_data = [
        ["Stage", "Description", "Action Required"],
        ["New", "Lead just came in from form/audit", "Sales reviews and makes first contact"],
        ["Contacted", "First contact made (call/email)", "Schedule discovery call"],
        ["Qualified", "Lead confirmed as good fit", "Prepare proposal"],
        ["Proposal Sent", "Proposal/pricing sent to lead", "Follow up, answer questions"],
        ["Negotiating", "Discussing terms, packages", "Close the deal"],
        ["Won", "Deal closed, became client", "Create client record, start onboarding"],
        ["Lost", "Lead declined or went cold", "Log reason, consider re-engagement later"],
    ]
    add_table(pipeline_data, col_widths=[80, 195, 215])

    # Pipeline funnel chart
    d = Drawing(480, 180)
    bc = VerticalBarChart()
    bc.x = 60; bc.y = 30; bc.height = 120; bc.width = 380
    bc.data = [[100, 70, 45, 30, 20, 15]]
    bc.categoryAxis.categoryNames = ['New Leads', 'Contacted', 'Qualified', 'Proposal', 'Negotiating', 'Won']
    bc.bars[0].fillColor = CYAN
    bc.valueAxis.valueMin = 0; bc.valueAxis.valueMax = 110
    bc.categoryAxis.labels.fontSize = 8
    d.add(bc)
    d.add(String(180, 160, 'Lead Conversion Funnel (Example)', fontSize=10, fontName='Helvetica-Bold'))
    elements.append(d)
    elements.append(PageBreak())

    # ===================== 8. BRANDING CUSTOMIZATION =====================
    section_header("8. Branding Customization Guide", "🎨")

    elements.append(Paragraph("Here's everything you need to change to make this system your own brand:", body))

    brand_data = [
        ["What to Change", "Where to Change It", "Files to Edit"],
        ["Company Name\n'RankForge AI'", "All 55+ HTML pages\n(header, footer, title tags)", "Find & replace 'RankForge AI'\nin all files under pages/ and index.html"],
        ["Phone Number\n+1 (800) 971-0199", "All 55+ HTML pages\n(header, footer, contact)", "Find & replace the phone number\nin all HTML files"],
        ["Email Address\nhello@YOUR_DOMAIN_HERE", "All 55+ HTML pages\n(footer, contact page)", "Find & replace the email\nin all HTML files"],
        ["Logo / Brand Colors", "CSS file and HTML headers", "Edit css/styles.css\nChange #06B6D4 (cyan) to your color"],
        ["Social Media URLs", "All page footers", "Replace facebook/instagram/linkedin/\ntiktok URLs in all files"],
        ["Domain Name", "OG tags, canonical URLs,\nschema markup", "Replace YOUR_DOMAIN_HERE\nwith your domain"],
        ["GA4 Tracking ID\nG-XXXXXXXXXX", "index.html\n(head section)", "Replace G-XXXXXXXXXX with\nyour Google Analytics ID"],
        ["Tawk.to Widget", "index.html\n(before </body>)", "Replace YOUR_PROPERTY_ID\nwith your Tawk.to IDs"],
        ["Calendly Link", "Contact page\n(booking section)", "Replace calendly.com/rankforgeai\nwith your Calendly URL"],
        ["Team Photos", "About page\n(team section)", "Replace placeholder initials\nwith real team photo URLs"],
        ["WhatsApp Number", "All page footers\n(floating button)", "Replace 18009710199\nwith your WhatsApp number"],
        ["Dashboard Branding", "Sidebar header in\nall dashboard templates", "Edit templates/*.html\nchange 'AI GrowthLabs'"],
    ]
    add_table(brand_data, col_widths=[100, 120, 270])
    elements.append(PageBreak())

    # ===================== 9. COST ANALYSIS =====================
    section_header("9. Cost Analysis & Alternatives", "💰")

    sub_header("Hosting Costs")
    hosting_data = [
        ["Provider", "Plan", "Monthly Cost", "Best For"],
        ["Devin Apps", "Frontend CDN", "Included", "Static frontend (current)"],
        ["Fly.io", "Free / Hobby", "$0-5/mo", "Backend + DB (recommended)"],
        ["Render.com", "Free / Starter", "$0-7/mo", "Alternative to Fly.io"],
        ["Railway.app", "Usage-based", "$5-15/mo", "Easy deployment"],
        ["DigitalOcean", "Droplet", "$6-12/mo", "Full server control"],
        ["Vercel", "Free tier", "$0", "Frontend only (alternative)"],
    ]
    add_table(hosting_data, col_widths=[80, 80, 80, 250])

    sub_header("Tool Alternatives")
    alt_data = [
        ["Category", "Current", "Cost", "Free Alternative", "Alt Cost"],
        ["AI Provider", "Claude/ChatGPT", "$5-50/mo", "Google Gemini Free Tier", "$0"],
        ["Email", "Gmail SMTP", "Free", "Mailgun Free (5K/mo)", "$0"],
        ["Voice/SMS", "Twilio", "$1+/mo", "Google Voice (US only)", "$0"],
        ["WhatsApp", "Meta Business API", "$0-varies", "Direct WhatsApp link", "$0"],
        ["Notifications", "Slack Webhooks", "Free", "Discord Webhooks", "$0"],
        ["Payments", "Stripe", "2.9%/txn", "PayPal Invoicing", "2.9%"],
        ["SEO Rankings", "Google Search Console", "Free", "Built-in manual entry", "$0"],
        ["SEO Tools", "Semrush/Ahrefs", "$99-229/mo", "Free audit crawler (built-in)", "$0"],
        ["Analytics", "Google Analytics", "Free", "Plausible/Umami", "$0-9"],
        ["Live Chat", "Tawk.to", "Free", "Crisp Free Plan", "$0"],
    ]
    add_table(alt_data, col_widths=[70, 85, 55, 120, 50])

    # Cost comparison chart
    d = Drawing(480, 200)
    bc = VerticalBarChart()
    bc.x = 60; bc.y = 30; bc.height = 140; bc.width = 380
    bc.data = [[0, 10, 35, 70], [229, 150, 100, 50]]
    bc.categoryAxis.categoryNames = ['Free Setup', 'Basic', 'Standard', 'Full']
    bc.bars[0].fillColor = GREEN
    bc.bars[1].fillColor = GRAY
    bc.valueAxis.valueMin = 0; bc.valueAxis.valueMax = 250
    bc.categoryAxis.labels.fontSize = 9
    d.add(bc)
    d.add(String(140, 185, 'Monthly Cost: Your System vs Traditional Tools', fontSize=10, fontName='Helvetica-Bold'))
    # Legend
    d.add(Rect(360, 160, 10, 10, fillColor=GREEN, strokeColor=None))
    d.add(String(375, 162, 'Your System', fontSize=7))
    d.add(Rect(360, 145, 10, 10, fillColor=GRAY, strokeColor=None))
    d.add(String(375, 147, 'Traditional', fontSize=7))
    elements.append(d)
    elements.append(PageBreak())

    # ===================== 10. PRODUCTION LAUNCH CHECKLIST =====================
    section_header("10. Production Launch Checklist", "🚀")

    checklist = [
        ["#", "Step", "Priority", "Time Est.", "Notes"],
        ["1", "Replace company name in all files", "Critical", "30 min", "Find & replace 'RankForge AI' → your brand"],
        ["2", "Replace phone + email in all pages", "Critical", "15 min", "Find & replace in all 55+ HTML files"],
        ["3", "Replace social media URLs", "High", "10 min", "Facebook, Instagram, LinkedIn, TikTok"],
        ["4", "Add real GA4 tracking ID", "High", "5 min", "Replace G-XXXXXXXXXX in index.html"],
        ["5", "Set up Tawk.to live chat", "High", "10 min", "Create free account → get widget code"],
        ["6", "Create Calendly link", "High", "15 min", "calendly.com → create booking page"],
        ["7", "Add team photos to About page", "Medium", "20 min", "Replace placeholder initials with images"],
        ["8", "Set up at least 1 AI API key", "High", "5 min", "Claude recommended → Settings → AI Providers"],
        ["9", "Configure Gmail SMTP", "High", "10 min", "Gmail App Password → Settings → Communication"],
        ["10", "Deploy backend to hosting", "Critical", "30 min", "Fly.io / Render / Railway"],
        ["11", "Deploy frontend to hosting", "Critical", "15 min", "Vercel / Netlify / Cloudflare Pages"],
        ["12", "Point custom domain", "High", "15 min", "DNS A/CNAME records"],
        ["13", "Test free audit form end-to-end", "Critical", "10 min", "Submit form → check results → check sales_leads"],
        ["14", "Test contact form", "High", "5 min", "Submit → check sales_leads table"],
        ["15", "Create real admin account", "Critical", "5 min", "Change admin password from admin123"],
        ["16", "Set up Stripe (if billing needed)", "Medium", "15 min", "Get API keys → Settings → Billing"],
        ["17", "Add OG image with your brand", "Medium", "10 min", "1200x630 image → assets/images/og-default.jpg"],
        ["18", "Test all demo logins work", "High", "10 min", "Login with each of 7 demo accounts"],
    ]
    add_table(checklist, col_widths=[20, 180, 55, 50, 185])
    elements.append(PageBreak())

    # ===================== 11. REVENUE & FINANCIAL OVERVIEW =====================
    section_header("11. Revenue & Financial Overview", "📈")

    elements.append(Paragraph("Current demo data financial snapshot:", body))

    fin_data = [
        ["Metric", "Value", "Details"],
        ["Monthly Recurring Revenue", "$23,982", "6 active clients × their package rates"],
        ["Total Collected", "$15,988", "4 paid invoices"],
        ["Pending Revenue", "$7,994", "2 unpaid invoices (1 pending, 1 overdue)"],
        ["Total Expenses", "$38,137", "Salaries + tools + marketing + office"],
        ["Staff Salaries", "$37,000/mo", "7 team members"],
        ["Tools Cost", "$548/mo", "Semrush, Ahrefs, Canva, Hosting"],
        ["Marketing", "$500/mo", "Google Ads"],
    ]
    add_table(fin_data, col_widths=[130, 80, 280])

    sub_header("Client Revenue by Package")
    pkg_data = [
        ["Package", "Monthly Fee", "Clients", "Monthly Revenue"],
        ["Growth Starter", "$997/mo", "1 (Precision Plumbing)", "$997"],
        ["Growth Pro", "$2,997/mo", "3 (SmileBright, Bella's, Phoenix)", "$8,991"],
        ["Growth Elite", "$6,997/mo", "2 (Martinez Legal, Glow Aesthetics)", "$13,994"],
        ["Total", "", "6 Active Clients", "$23,982/mo"],
    ]
    add_table(pkg_data, col_widths=[90, 80, 170, 100])

    # Revenue bar chart
    d = Drawing(480, 200)
    bc = VerticalBarChart()
    bc.x = 60; bc.y = 30; bc.height = 140; bc.width = 380
    bc.data = [[997, 8991, 13994]]
    bc.categoryAxis.categoryNames = ['Growth Starter\n($997)', 'Growth Pro\n($2,997 x3)', 'Growth Elite\n($6,997 x2)']
    bc.bars[0].fillColor = CYAN
    bc.valueAxis.valueMin = 0; bc.valueAxis.valueMax = 15000
    bc.categoryAxis.labels.fontSize = 8
    d.add(bc)
    d.add(String(180, 180, 'Monthly Revenue by Package', fontSize=11, fontName='Helvetica-Bold'))
    elements.append(d)

    elements.append(Spacer(1, 12))

    # Revenue projection line chart
    d = Drawing(480, 200)
    lc = HorizontalLineChart()
    lc.x = 60; lc.y = 30; lc.height = 140; lc.width = 380
    lc.data = [[23982, 28000, 35000, 45000, 55000, 65000],
               [38137, 39000, 40000, 41000, 42000, 43000]]
    lc.categoryAxis.categoryNames = ['Month 1', 'Month 2', 'Month 3', 'Month 4', 'Month 5', 'Month 6']
    lc.lines[0].strokeColor = CYAN
    lc.lines[0].strokeWidth = 2
    lc.lines[1].strokeColor = RED
    lc.lines[1].strokeWidth = 2
    lc.valueAxis.valueMin = 0; lc.valueAxis.valueMax = 70000
    lc.categoryAxis.labels.fontSize = 8
    d.add(lc)
    d.add(String(180, 180, '6-Month Revenue Projection', fontSize=11, fontName='Helvetica-Bold'))
    d.add(Rect(370, 160, 10, 10, fillColor=CYAN, strokeColor=None))
    d.add(String(385, 162, 'Revenue', fontSize=7))
    d.add(Rect(370, 145, 10, 10, fillColor=RED, strokeColor=None))
    d.add(String(385, 147, 'Expenses', fontSize=7))
    elements.append(d)

    elements.append(PageBreak())

    # ===================== FINAL SUMMARY =====================
    section_header("Summary", "📋")

    elements.append(Paragraph("""
    <b>RankForge AI Agency Operating System</b> is a complete, production-ready platform for running an SEO/digital marketing agency.
    <br/><br/>
    <b>What's Included:</b><br/>
    • 55+ frontend pages with responsive design, dark theme, and real contact/audit forms<br/>
    • 99+ API endpoints covering all agency operations<br/>
    • 22+ database tables for persistent data storage<br/>
    • 11 user roles with role-based access control<br/>
    • 9 API integrations (all working in demo mode)<br/>
    • Real website crawler for SEO audits (no external API needed)<br/>
    • Lead generation through free audit + contact forms<br/>
    • Complete financial management (invoices, payments, expenses, salaries)<br/>
    • Team management (tasks, time tracking, performance, chat)<br/>
    • Client portal (separate dashboard for clients)<br/>
    • Analytics and reporting with downloadable reports<br/><br/>
    <b>To Go Live:</b><br/>
    1. Follow the Branding Customization Guide (Section 8)<br/>
    2. Complete the Production Launch Checklist (Section 10)<br/>
    3. Deploy to your hosting provider<br/>
    4. Add your API keys through the Settings page<br/>
    5. Start generating leads through the free audit form<br/><br/>
    <b>Total Setup Time:</b> ~3-4 hours<br/>
    <b>Minimum Monthly Cost:</b> $0 (free tier possible)<br/>
    <b>Recommended Monthly Cost:</b> $10-35/mo for basic automation
    """, body))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Generated by RankForge AI System | " + datetime.datetime.now().strftime("%B %d, %Y"),
                               ParagraphStyle('Footer', parent=center, fontSize=8, textColor=GRAY)))

    # Build
    doc.build(elements)
    print(f"Report generated: {filename}")
    return filename

if __name__ == "__main__":
    build_report()
