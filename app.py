from __future__ import annotations

import csv
import hashlib
import html
import ipaddress
import json
import os
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, getaddresses, make_msgid, parseaddr
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from markupsafe import Markup, escape
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-onlypt-secret")

LEADS_FILE = Path(app.instance_path) / "leads.csv"
LEAD_THREADS_FILE = Path(app.instance_path) / "lead_threads.json"
NOTIFICATIONS_LOG_FILE = Path(app.instance_path) / "notification_errors.log"
SUBMISSION_LIMIT_FILE = Path(app.instance_path) / "submission_limits.json"
EMAIL_RATE_FILE = Path(app.instance_path) / "email_rate.json"
EMAIL_QUEUE_FILE = Path(app.instance_path) / "email_queue.json"
TRAFFIC_LOG_FILE = Path(app.instance_path) / "traffic_events.jsonl"
IP_REGION_CACHE_FILE = Path(app.instance_path) / "ip_region_cache.json"
TRAFFIC_REPORT_STATE_FILE = Path(app.instance_path) / "traffic_report_state.json"
PAGE_EDITS_DIR = Path(app.instance_path) / "page_edits"
CONTENT_FILE = Path(app.instance_path) / "content_overrides.json"
UPLOAD_DIR = Path(app.instance_path) / "uploads"
BACKGROUND_UPLOAD_DIR = UPLOAD_DIR / "backgrounds"
FAVICON_UPLOAD_DIR = UPLOAD_DIR / "favicons"
ADMIN_USERNAME = os.environ.get("ONLYPT_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ONLYPT_ADMIN_PASSWORD", "REDACTED_ADMIN_PASSWORD")
try:
    SITE_TIMEZONE = ZoneInfo(os.environ.get("ONLYPT_SITE_TIMEZONE", "America/New_York"))
except ZoneInfoNotFoundError:
    SITE_TIMEZONE = timezone.utc
ALLOWED_BACKGROUND_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
ALLOWED_FAVICON_EXTENSIONS = {"ico", "png", "svg", "webp"}
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "").strip()
TWILIO_WHATSAPP_TO = os.environ.get("TWILIO_WHATSAPP_TO", "").strip()
IP_SUBMISSION_LIMIT = 3
IP_SUBMISSION_WINDOW_SECONDS = 10 * 60
EMAIL_SUBMISSION_LIMIT = 5
EMAIL_SUBMISSION_WINDOW_SECONDS = 60 * 60
GLOBAL_EMAIL_LIMIT = 2
GLOBAL_EMAIL_WINDOW_SECONDS = 60
MAX_EMAIL_QUEUE_ATTEMPTS = 6
PUBLIC_TRAFFIC_ENDPOINTS = {"home", "employers", "therapists", "about", "contact"}

EDITABLE_PAGES = {
    "home": {"label": "Home", "endpoint": "home", "template": "index.html"},
    "employers": {"label": "Employers", "endpoint": "employers", "template": "employers.html"},
    "therapists": {"label": "Therapists", "endpoint": "therapists", "template": "therapists.html"},
    "about": {"label": "About", "endpoint": "about", "template": "about.html"},
    "contact": {"label": "Contact", "endpoint": "contact", "template": "contact.html"},
}

PAGE_DRAFT_FIELDS = [
    "draft_headline",
    "draft_subheadline",
    "primary_cta",
    "secondary_cta",
    "layout_notes",
    "draft_body",
]


def cms_field(key: str, label: str, default: str, field_type: str = "text", group: str = "Content") -> dict[str, str]:
    return {
        "key": key,
        "label": label,
        "default": default,
        "type": field_type,
        "group": group,
    }


CONTENT_PAGES = {
    "general": {
        "label": "General",
        "endpoint": "home",
        "fields": [
            cms_field("brand.name", "Brand name", "onlyPT", group="Brand"),
            cms_field("brand.subtitle", "Brand subtitle", "Recruiting", group="Brand"),
            cms_field("meta.description", "Meta description", "onlyPT Recruiting helps healthcare employers hire licensed Physical Therapists with focused, clinically fluent recruiting.", "textarea", "Meta"),
            cms_field("nav.home", "Nav: Home", "Home", group="Navigation"),
            cms_field("nav.employers", "Nav: Employers", "Employers", group="Navigation"),
            cms_field("nav.therapists", "Nav: Therapists", "Therapists", group="Navigation"),
            cms_field("nav.about", "Nav: About", "About", group="Navigation"),
            cms_field("nav.contact", "Nav: Contact", "Contact", group="Navigation"),
            cms_field("header.cta", "Header CTA", "Start a Search", group="Navigation"),
            cms_field("footer.description", "Footer description", "Focused Physical Therapy recruiting for healthcare employers and PT professionals.", "textarea", "Footer"),
            cms_field("footer.employers", "Footer link: Employers", "Employers", group="Footer"),
            cms_field("footer.therapists", "Footer link: Therapists", "Therapists", group="Footer"),
            cms_field("footer.about", "Footer link: About", "About", group="Footer"),
            cms_field("footer.contact", "Footer link: Contact", "Contact", group="Footer"),
            cms_field("footer.admin", "Footer link: Admin", "Admin", group="Footer"),
            cms_field("site.favicon", "Page tab icon", "", "favicon", "Page Tab"),
            cms_field("background.enabled", "Use uploaded site background", "off", "toggle", "Background"),
            cms_field("background.image", "Site background photo", "", "image", "Background"),
            cms_field("layout.first_section_top", "First container top offset", "22", "range", "Layout"),
        ],
    },
    "email": {
        "label": "Email Notifications",
        "endpoint": "contact",
        "fields": [
            cms_field("lead_email.to", "Admin notification email", "", group="Notification target"),
            cms_field("lead_email.enabled", "Send email lead notifications", "off", "toggle", "Notification target"),
            cms_field("traffic_report.daily_enabled", "Send daily traffic report", "off", "toggle", "Notification target"),
            cms_field("traffic_report.weekly_enabled", "Send weekly traffic report", "off", "toggle", "Notification target"),
            cms_field("traffic_report.to", "Traffic report recipient", "", group="Notification target"),
            cms_field("lead_email.from_email", "Sender email address", "", group="Sender identity"),
            cms_field("lead_email.from_name", "Sender display name", "onlyPT Recruiting", group="Sender identity"),
            cms_field("lead_email.smtp_host", "SMTP server", "smtppro.zoho.com", group="SMTP access"),
            cms_field("lead_email.smtp_port", "SMTP port", "465", group="SMTP access"),
            cms_field("lead_email.smtp_security", "SMTP security", "ssl", group="SMTP access"),
            cms_field("lead_email.smtp_username", "SMTP username", "", group="SMTP access"),
            cms_field("lead_email.smtp_password", "SMTP password", "", "password", "SMTP access"),
        ],
    },
    "home": {
        "label": "Home",
        "endpoint": "home",
        "fields": [
            cms_field("hero.title", "Hero headline", "PT hiring, handled by people who understand PT.", "textarea", "Hero"),
            cms_field("hero.lede", "Hero supporting copy", "onlyPT Recruiting helps healthcare employers hire licensed Physical Therapists through focused sourcing, clinical fluency, and candidate conversations built around real fit.", "textarea", "Hero"),
            cms_field("hero.signal1.label", "Signal 1 label", "License", group="Hero"),
            cms_field("hero.signal1.value", "Signal 1 value", "Verified", group="Hero"),
            cms_field("hero.signal2.label", "Signal 2 label", "Setting", group="Hero"),
            cms_field("hero.signal2.value", "Signal 2 value", "Matched", group="Hero"),
            cms_field("hero.signal3.label", "Signal 3 label", "Market", group="Hero"),
            cms_field("hero.signal3.value", "Signal 3 value", "Mapped", group="Hero"),
            cms_field("hero.primary_cta", "Primary CTA", "Hire a PT", group="Hero"),
            cms_field("hero.secondary_cta", "Secondary CTA", "Explore PT Roles", group="Hero"),
            cms_field("hero.stat.number", "Hero stat number", "100%", group="Hero"),
            cms_field("hero.stat.caption", "Hero stat caption", "focused on Physical Therapists", group="Hero"),
            cms_field("problem.title", "Problem heading", "PT recruiting is too specialized for a generic search.", "textarea", "Problem"),
            cms_field("problem.card1.title", "Problem card 1 title", "Local markets matter", group="Problem"),
            cms_field("problem.card1.body", "Problem card 1 body", "Compensation, commute radius, setting preference, and license timing can change the search before a resume ever arrives.", "textarea", "Problem"),
            cms_field("problem.card2.title", "Problem card 2 title", "Clinical fit matters", group="Problem"),
            cms_field("problem.card2.body", "Problem card 2 body", "Outpatient ortho, hospital, SNF, home health, leadership, and specialty experience each require a different conversation.", "textarea", "Problem"),
            cms_field("problem.card3.title", "Problem card 3 title", "Candidate trust matters", group="Problem"),
            cms_field("problem.card3.body", "Problem card 3 body", "PTs respond when the recruiter can speak clearly about caseload, mentorship, productivity, growth, and quality of care.", "textarea", "Problem"),
            cms_field("why.eyebrow", "Why eyebrow", "Why onlyPT", group="Why"),
            cms_field("why.title", "Why heading", "Narrow focus. Better conversations. Stronger shortlists.", "textarea", "Why"),
            cms_field("why.body", "Why body", "Because we recruit only Physical Therapists, every search starts with the details that make a PT role easier or harder to fill: setting, patient population, schedule, productivity, growth path, and the market reality around compensation.", "textarea", "Why"),
            cms_field("why.proof1", "Proof item 1", "Founded with clinical PT perspective and healthcare recruiting discipline.", "textarea", "Why"),
            cms_field("why.proof2", "Proof item 2", "Screening built around license, setting fit, motivation, and offer readiness.", "textarea", "Why"),
            cms_field("why.proof3", "Proof item 3", "Clear communication from first role intake through accepted offer.", "textarea", "Why"),
            cms_field("process.eyebrow", "Process eyebrow", "Process", group="Process"),
            cms_field("process.title", "Process heading", "A focused search rhythm from intake to start date.", "textarea", "Process"),
            cms_field("process.step1.title", "Step 1 title", "Understand the role", group="Process"),
            cms_field("process.step1.body", "Step 1 body", "We clarify setting, must-haves, compensation, timeline, and what will make the opportunity compelling.", "textarea", "Process"),
            cms_field("process.step2.title", "Step 2 title", "Build the search", group="Process"),
            cms_field("process.step2.body", "Step 2 body", "We map the PT market and tailor outreach around the role's real strengths.", "textarea", "Process"),
            cms_field("process.step3.title", "Step 3 title", "Screen deeply", group="Process"),
            cms_field("process.step3.body", "Step 3 body", "We evaluate license status, clinical fit, motivation, schedule needs, and readiness to move.", "textarea", "Process"),
            cms_field("process.step4.title", "Step 4 title", "Present selectively", group="Process"),
            cms_field("process.step4.body", "Step 4 body", "You see qualified candidates with context, not a stack of unfiltered resumes.", "textarea", "Process"),
            cms_field("process.step5.title", "Step 5 title", "Support the close", group="Process"),
            cms_field("process.step5.body", "Step 5 body", "We help keep momentum through interviews, offer, notice period, and start date.", "textarea", "Process"),
            cms_field("audience.employer.label", "Employer panel label", "For Employers", group="Audience"),
            cms_field("audience.employer.title", "Employer panel title", "Need to fill a PT role?", group="Audience"),
            cms_field("audience.employer.body", "Employer panel body", "Get a recruiting partner who can speak the clinical language and run a disciplined search.", "textarea", "Audience"),
            cms_field("audience.therapist.label", "Therapist panel label", "For PTs", group="Audience"),
            cms_field("audience.therapist.title", "Therapist panel title", "Considering your next move?", group="Audience"),
            cms_field("audience.therapist.body", "Therapist panel body", "Start a confidential conversation about roles that match your goals and setting preferences.", "textarea", "Audience"),
        ],
    },
    "employers": {
        "label": "Employers",
        "endpoint": "employers",
        "fields": [
            cms_field("hero.eyebrow", "Hero eyebrow", "For Employers", group="Hero"),
            cms_field("hero.title", "Hero headline", "Hire Physical Therapists with a search built for the PT market.", "textarea", "Hero"),
            cms_field("hero.body", "Hero body", "We support clinics, hospitals, SNFs, home health providers, and multi-site healthcare groups that need stronger PT candidate flow without adding more burden to internal teams.", "textarea", "Hero"),
            cms_field("hero.cta", "Hero CTA", "Discuss a Role", group="Hero"),
            cms_field("solve.eyebrow", "Solve eyebrow", "What we solve", group="What we solve"),
            cms_field("solve.title", "Solve heading", "Hard-to-fill PT openings need more than job board traffic.", "textarea", "What we solve"),
            cms_field("solve.body", "Solve body", "We help you clarify the role, reach passive candidates, screen for clinical and logistical fit, and keep qualified PTs engaged through the decision process.", "textarea", "What we solve"),
            cms_field("service1.title", "Service 1 title", "Permanent PT search", group="Services"),
            cms_field("service1.body", "Service 1 body", "Staff PT, specialty PT, and experienced clinician searches.", "textarea", "Services"),
            cms_field("service2.title", "Service 2 title", "Leadership roles", group="Services"),
            cms_field("service2.body", "Service 2 body", "Clinic Director, lead therapist, and growth-track positions.", "textarea", "Services"),
            cms_field("service3.title", "Service 3 title", "Multi-site support", group="Services"),
            cms_field("service3.body", "Service 3 body", "Repeatable search support for groups hiring across markets.", "textarea", "Services"),
            cms_field("service4.title", "Service 4 title", "Market insight", group="Services"),
            cms_field("service4.body", "Service 4 body", "Role positioning, compensation feedback, and candidate objections.", "textarea", "Services"),
            cms_field("settings.eyebrow", "Settings eyebrow", "Settings", group="Practice map"),
            cms_field("settings.title", "Settings heading", "Recruiting across the places PTs actually practice.", "textarea", "Practice map"),
            cms_field("settings.body", "Settings body", "Each care environment changes the candidate conversation: schedule, caseload, patient mix, productivity, mentorship, and what makes the opportunity worth a move.", "textarea", "Practice map"),
            cms_field("practice.chip1", "Practice chip 1", "Caseload", group="Practice map"),
            cms_field("practice.chip2", "Practice chip 2", "Schedule", group="Practice map"),
            cms_field("practice.chip3", "Practice chip 3", "Patient mix", group="Practice map"),
            cms_field("practice.chip4", "Practice chip 4", "Productivity", group="Practice map"),
            cms_field("practice.chip5", "Practice chip 5", "Mentorship", group="Practice map"),
            cms_field("practice.chip6", "Practice chip 6", "Commute", group="Practice map"),
            cms_field("practice.chip7", "Practice chip 7", "License", group="Practice map"),
            cms_field("practice.chip8", "Practice chip 8", "Growth path", group="Practice map"),
            cms_field("practice.core.title", "Practice core title", "Practice map", group="Practice map"),
            cms_field("practice.core.subtitle", "Practice core subtitle", "setting first recruiting", group="Practice map"),
            cms_field("practice.node1.title", "Practice 1 title", "Outpatient Orthopedics", group="Practice map"),
            cms_field("practice.node1.detail", "Practice 1 detail", "volume, mentorship, post-op mix", group="Practice map"),
            cms_field("practice.node2.title", "Practice 2 title", "Hospital & Acute Care", group="Practice map"),
            cms_field("practice.node2.detail", "Practice 2 detail", "acuity, coverage, team rhythm", group="Practice map"),
            cms_field("practice.node3.title", "Practice 3 title", "Skilled Nursing", group="Practice map"),
            cms_field("practice.node3.detail", "Practice 3 detail", "productivity, census, care model", group="Practice map"),
            cms_field("practice.node4.title", "Practice 4 title", "Home Health", group="Practice map"),
            cms_field("practice.node4.detail", "Practice 4 detail", "territory, autonomy, visit load", group="Practice map"),
            cms_field("practice.node5.title", "Practice 5 title", "Pediatric Therapy", group="Practice map"),
            cms_field("practice.node5.detail", "Practice 5 detail", "population, family fit, schedule", group="Practice map"),
            cms_field("practice.node6.title", "Practice 6 title", "Sports Medicine", group="Practice map"),
            cms_field("practice.node6.detail", "Practice 6 detail", "athletes, pace, specialty depth", group="Practice map"),
            cms_field("practice.node7.title", "Practice 7 title", "Private Practice", group="Practice map"),
            cms_field("practice.node7.detail", "Practice 7 detail", "culture, growth path, ownership", group="Practice map"),
            cms_field("practice.node8.title", "Practice 8 title", "Multi-Clinic Groups", group="Practice map"),
            cms_field("practice.node8.detail", "Practice 8 detail", "market coverage, repeat hiring", group="Practice map"),
            cms_field("cta.eyebrow", "CTA eyebrow", "Next step", group="CTA"),
            cms_field("cta.title", "CTA heading", "Tell us about the PT role that needs attention.", "textarea", "CTA"),
            cms_field("cta.body", "CTA body", "We will talk through the setting, requirements, search difficulty, timeline, and what a realistic hiring strategy should look like.", "textarea", "CTA"),
            cms_field("cta.button", "CTA button", "Start a Search", group="CTA"),
        ],
    },
    "therapists": {
        "label": "Therapists",
        "endpoint": "therapists",
        "fields": [
            cms_field("hero.eyebrow", "Hero eyebrow", "For Physical Therapists", group="Hero"),
            cms_field("hero.title", "Hero headline", "Explore PT roles with someone who understands the work behind the title.", "textarea", "Hero"),
            cms_field("hero.body", "Hero body", "Your next move should fit your clinical interests, schedule, growth goals, and life outside the clinic. We keep conversations confidential and practical.", "textarea", "Hero"),
            cms_field("hero.cta", "Hero CTA", "Start a Conversation", group="Hero"),
            cms_field("feature1.title", "Feature 1 title", "Confidential", group="Features"),
            cms_field("feature1.body", "Feature 1 body", "You can explore opportunities without broadcasting your search or risking current workplace relationships.", "textarea", "Features"),
            cms_field("feature2.title", "Feature 2 title", "Fit-first", group="Features"),
            cms_field("feature2.body", "Feature 2 body", "We listen for setting preference, caseload, mentorship, compensation, leadership goals, and geography.", "textarea", "Features"),
            cms_field("feature3.title", "Feature 3 title", "Clear support", group="Features"),
            cms_field("feature3.body", "Feature 3 body", "We help you understand the opportunity, interview process, offer details, and timing before you commit.", "textarea", "Features"),
            cms_field("roles.eyebrow", "Roles eyebrow", "Roles", group="Roles"),
            cms_field("roles.title", "Roles heading", "Opportunities can range from staff PT to leadership track.", "textarea", "Roles"),
            cms_field("roles.body", "Roles body", "Whether you are actively searching or just curious about the market, a focused conversation can help you compare options with less noise.", "textarea", "Roles"),
            cms_field("roles.proof1", "Proof item 1", "Permanent staff PT roles in outpatient, inpatient, SNF, home health, and specialty settings.", "textarea", "Roles"),
            cms_field("roles.proof2", "Proof item 2", "Clinic Director and lead therapist roles for PTs ready to grow into leadership.", "textarea", "Roles"),
            cms_field("roles.proof3", "Proof item 3", "Market conversations around compensation, schedule, commute, and growth path.", "textarea", "Roles"),
            cms_field("cta.eyebrow", "CTA eyebrow", "Confidential PT intake", group="CTA"),
            cms_field("cta.title", "CTA heading", "Tell us what kind of PT role would actually be worth a move.", "textarea", "CTA"),
            cms_field("cta.button", "CTA button", "Contact onlyPT", group="CTA"),
        ],
    },
    "about": {
        "label": "About",
        "endpoint": "about",
        "fields": [
            cms_field("hero.eyebrow", "Hero eyebrow", "About onlyPT", group="Hero"),
            cms_field("hero.title", "Hero headline", "A recruiting firm built around one discipline: Physical Therapy.", "textarea", "Hero"),
            cms_field("hero.body", "Hero body", "onlyPT Recruiting exists because PT hiring is not generic healthcare hiring. The details of clinical setting, patient mix, documentation expectations, mentorship, productivity, and growth path all affect whether a candidate is truly right for a role.", "textarea", "Hero"),
            cms_field("ledger.label1", "Ledger label 1", "Discipline", group="Ledger"),
            cms_field("ledger.value1", "Ledger value 1", "Physical Therapy", group="Ledger"),
            cms_field("ledger.label2", "Ledger label 2", "Search Mode", group="Ledger"),
            cms_field("ledger.value2", "Ledger value 2", "Specialist", group="Ledger"),
            cms_field("ledger.label3", "Ledger label 3", "Noise Level", group="Ledger"),
            cms_field("ledger.value3", "Ledger value 3", "Low", group="Ledger"),
            cms_field("perspective.eyebrow", "Perspective eyebrow", "Point of view", group="Perspective"),
            cms_field("perspective.title", "Perspective heading", "Specialization is the strategy.", group="Perspective"),
            cms_field("perspective.body", "Perspective body", "Instead of spreading attention across every healthcare title, onlyPT keeps the work centered on Physical Therapists. That focus helps us ask better questions, position roles more honestly, and build trust with both employers and clinicians.", "textarea", "Perspective"),
            cms_field("perspective.quote", "Founder quote", "Good recruiting is not just matching a credential to a vacancy. It is understanding what makes a PT say yes, stay engaged, accept the offer, and thrive after day one.", "textarea", "Perspective"),
            cms_field("values.eyebrow", "Values eyebrow", "Principles", group="Values"),
            cms_field("values.title", "Values heading", "The way we work.", group="Values"),
            cms_field("values.card1.title", "Value 1 title", "Focused", group="Values"),
            cms_field("values.card1.body", "Value 1 body", "We stay close to the PT market and avoid searches that dilute the quality of our candidate conversations.", "textarea", "Values"),
            cms_field("values.card2.title", "Value 2 title", "Attentive", group="Values"),
            cms_field("values.card2.body", "Value 2 body", "We listen carefully to employer needs and candidate motivations before pushing the process forward.", "textarea", "Values"),
            cms_field("values.card3.title", "Value 3 title", "Direct", group="Values"),
            cms_field("values.card3.body", "Value 3 body", "We communicate market feedback, candidate concerns, and search realities clearly.", "textarea", "Values"),
        ],
    },
    "contact": {
        "label": "Contact",
        "endpoint": "contact",
        "fields": [
            cms_field("hero.eyebrow", "Contact eyebrow", "Contact", group="Intro"),
            cms_field("hero.title", "Contact headline", "Tell us where the PT conversation should start.", "textarea", "Intro"),
            cms_field("hero.body", "Contact body", "Employers can share an open role. Physical Therapists can start a confidential career conversation.", "textarea", "Intro"),
            cms_field("method.email", "Email", "hello@onlyptrecruiting.com", group="Contact methods"),
            cms_field("method.response", "Response time", "Response within one business day", group="Contact methods"),
            cms_field("form.audience_label", "Audience label", "I am a", group="Form"),
            cms_field("form.option_employer", "Employer option", "Healthcare employer", group="Form"),
            cms_field("form.option_therapist", "Therapist option", "Physical Therapist", group="Form"),
            cms_field("form.name", "Name label", "Name", group="Form"),
            cms_field("form.email", "Email label", "Email", group="Form"),
            cms_field("form.organization", "Organization label", "Organization", group="Form"),
            cms_field("form.phone", "Phone label", "Phone", group="Form"),
            cms_field("form.role", "Role label", "Role or setting", group="Form"),
            cms_field("form.role_placeholder", "Role placeholder", "Outpatient PT, Clinic Director, Home Health PT...", group="Form"),
            cms_field("form.message", "Message label", "Message", group="Form"),
            cms_field("form.submit", "Submit button", "Send Message", group="Form"),
            cms_field("flash.missing", "Missing fields message", "Please add your name, email, and a short message.", "textarea", "Messages"),
            cms_field("flash.success", "Success message", "Thanks. We received your note and will follow up shortly.", "textarea", "Messages"),
        ],
    },
}


def write_lead(form_data: dict[str, str]) -> None:
    LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "created_at",
        "audience",
        "name",
        "email",
        "organization",
        "phone",
        "role",
        "message",
    ]
    row = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "audience": form_data.get("audience", ""),
        "name": form_data.get("name", ""),
        "email": form_data.get("email", ""),
        "organization": form_data.get("organization", ""),
        "phone": form_data.get("phone", ""),
        "role": form_data.get("role", ""),
        "message": form_data.get("message", ""),
    }
    is_new = not LEADS_FILE.exists()
    with LEADS_FILE.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def now_timestamp() -> float:
    return datetime.now(timezone.utc).timestamp()


def load_json_file(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return fallback


def write_json_file(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def client_ip_address() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.remote_addr or "unknown"


def is_public_ip(ip_value: str) -> bool:
    try:
        address = ipaddress.ip_address(ip_value)
    except ValueError:
        return False
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def lookup_ip_region(ip_value: str) -> dict[str, str]:
    if not is_public_ip(ip_value):
        return {
            "ip": ip_value,
            "country": "Local",
            "region": "",
            "city": "",
            "timezone": "",
            "isp": "",
            "source": "local",
        }

    cache = load_json_file(IP_REGION_CACHE_FILE, {})
    cached = cache.get(ip_value)
    if isinstance(cached, dict) and cached.get("country") is not None:
        return cached

    region = {
        "ip": ip_value,
        "country": "Unknown",
        "region": "",
        "city": "",
        "timezone": "",
        "isp": "",
        "source": "unresolved",
    }
    try:
        query = urllib.parse.quote(ip_value)
        endpoint = (
            f"http://ip-api.com/json/{query}"
            "?fields=status,country,regionName,city,timezone,isp,query,message"
        )
        with urllib.request.urlopen(endpoint, timeout=1.6) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("status") == "success":
            region = {
                "ip": str(payload.get("query") or ip_value),
                "country": str(payload.get("country") or "Unknown"),
                "region": str(payload.get("regionName") or ""),
                "city": str(payload.get("city") or ""),
                "timezone": str(payload.get("timezone") or ""),
                "isp": str(payload.get("isp") or ""),
                "source": "ip-api",
            }
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        log_notification_error(f"IP region lookup failed for {ip_value}: {error}")

    cache[ip_value] = region
    try:
        write_json_file(IP_REGION_CACHE_FILE, cache)
    except OSError as error:
        log_notification_error(f"IP region cache write failed: {error}")
    return region


def traffic_visitor_id(ip_value: str, user_agent: str) -> str:
    raw = f"{ip_value}|{user_agent}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:16]


def traffic_device_type(user_agent: str) -> str:
    value = user_agent.lower()
    if any(marker in value for marker in ("bot", "crawler", "spider", "preview")):
        return "Bot"
    if "ipad" in value or "tablet" in value:
        return "Tablet"
    if any(marker in value for marker in ("mobile", "iphone", "android")):
        return "Mobile"
    return "Desktop"


def append_traffic_event(event: dict[str, object]) -> None:
    try:
        TRAFFIC_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with TRAFFIC_LOG_FILE.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError as error:
        log_notification_error(f"Traffic event write failed: {error}")


def base_traffic_event(event_type: str) -> dict[str, object]:
    ip_value = client_ip_address()
    user_agent = request.headers.get("User-Agent", "")
    region = lookup_ip_region(ip_value)
    return {
        "type": event_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "path": request.path,
        "endpoint": request.endpoint or "",
        "method": request.method,
        "ip": ip_value,
        "visitor_id": traffic_visitor_id(ip_value, user_agent),
        "user_agent": user_agent[:500],
        "device": traffic_device_type(user_agent),
        "referrer": request.headers.get("Referer", "")[:500],
        "region": region,
    }


def should_record_page_view(response) -> bool:
    return (
        request.method == "GET"
        and response.status_code < 400
        and request.endpoint in PUBLIC_TRAFFIC_ENDPOINTS
        and request.args.get("admin_preview") != "1"
        and not request.path.startswith(("/admin", "/dev", "/static", "/uploads"))
    )


def record_form_submission_event(form_data: dict[str, str]) -> None:
    event = base_traffic_event("form_submission")
    event["form"] = {
        "audience": form_data.get("audience", ""),
        "email_domain": email_domain(form_data.get("email", "")),
        "has_phone": bool(form_data.get("phone", "").strip()),
    }
    append_traffic_event(event)


def iter_traffic_events(start: datetime | None = None, end: datetime | None = None) -> list[dict[str, object]]:
    if not TRAFFIC_LOG_FILE.exists():
        return []

    events: list[dict[str, object]] = []
    with TRAFFIC_LOG_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            created_at = parse_iso_datetime(str(event.get("created_at", "")))
            if created_at is None:
                continue
            if start and created_at < start:
                continue
            if end and created_at >= end:
                continue
            events.append(event)
    return events


def period_bounds(period: str, reference: datetime | None = None) -> tuple[datetime, datetime]:
    reference = reference or datetime.now(SITE_TIMEZONE)
    reference = reference.astimezone(SITE_TIMEZONE)
    day_start = reference.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        start = day_start.replace(day=day_start.day) - timedelta(days=day_start.weekday())
        return start.astimezone(timezone.utc), (start + timedelta(days=7)).astimezone(timezone.utc)
    return day_start.astimezone(timezone.utc), (day_start + timedelta(days=1)).astimezone(timezone.utc)


def count_by(events: list[dict[str, object]], key_fn, limit: int = 10) -> list[dict[str, object]]:
    counts: dict[str, int] = {}
    for event in events:
        key = key_fn(event) or "Unknown"
        counts[str(key)] = counts.get(str(key), 0) + 1
    return [
        {"label": label, "count": count}
        for label, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


def mask_ip(ip_value: str) -> str:
    try:
        address = ipaddress.ip_address(ip_value)
    except ValueError:
        return "Unknown"
    if address.version == 4:
        parts = ip_value.split(".")
        if len(parts) == 4:
            return ".".join([parts[0], parts[1], parts[2], "*"])
    return f"{address.compressed[:12]}..."


def traffic_event_local_date(event: dict[str, object]) -> str:
    created_at = parse_iso_datetime(str(event.get("created_at", "")))
    if created_at is None:
        return "unknown"
    return created_at.astimezone(SITE_TIMEZONE).strftime("%Y-%m-%d")


def traffic_location_label(event: dict[str, object]) -> str:
    region = event.get("region") or {}
    location = ", ".join(
        part
        for part in [
            str(region.get("city", "")),
            str(region.get("region", "")),
            str(region.get("country", "")),
        ]
        if part
    )
    return location or "Unknown"


def enrich_traffic_event(event: dict[str, object]) -> dict[str, object]:
    created_at = parse_iso_datetime(str(event.get("created_at", "")))
    item = dict(event)
    item["local_time"] = created_at.astimezone(SITE_TIMEZONE).strftime("%Y-%m-%d %H:%M") if created_at else "-"
    item["location_label"] = traffic_location_label(event)
    item["ip_label"] = mask_ip(str(event.get("ip", "")))
    return item


def group_traffic_events(events: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[str, dict[str, object]] = {}
    for event in events:
        ip_value = str(event.get("ip", "") or "unknown")
        local_date = traffic_event_local_date(event)
        group_key = f"{ip_value}|{local_date}"
        group = groups.setdefault(
            group_key,
            {
                "id": hashlib.sha1(group_key.encode("utf-8", errors="ignore")).hexdigest()[:12],
                "ip": ip_value,
                "ip_label": mask_ip(ip_value),
                "local_date": local_date,
                "events": [],
                "page_paths": [],
                "event_count": 0,
                "page_view_count": 0,
                "form_submission_count": 0,
                "first_time": "",
                "last_time": "",
                "location_label": traffic_location_label(event),
                "device": event.get("device") or "Unknown",
                "referrer": event.get("referrer") or "Direct",
            },
        )
        enriched = enrich_traffic_event(event)
        group_events = group["events"]
        if isinstance(group_events, list):
            group_events.append(enriched)

        group["event_count"] = int(group.get("event_count", 0)) + 1
        if event.get("type") == "page_view":
            group["page_view_count"] = int(group.get("page_view_count", 0)) + 1
            path = str(event.get("path") or "-")
            page_paths = group["page_paths"]
            if isinstance(page_paths, list) and path not in page_paths:
                page_paths.append(path)
        if event.get("type") == "form_submission":
            group["form_submission_count"] = int(group.get("form_submission_count", 0)) + 1

        created_at = parse_iso_datetime(str(event.get("created_at", "")))
        if created_at is not None:
            local_time = created_at.astimezone(SITE_TIMEZONE).strftime("%Y-%m-%d %H:%M")
            if not group.get("first_time"):
                group["first_time"] = local_time
            group["last_time"] = local_time

        if traffic_location_label(event) != "Unknown":
            group["location_label"] = traffic_location_label(event)
        if event.get("device"):
            group["device"] = event.get("device")
        if event.get("referrer"):
            group["referrer"] = event.get("referrer")

    grouped = list(groups.values())
    grouped.sort(key=lambda item: str(item.get("last_time") or item.get("first_time") or ""), reverse=True)
    for group in grouped:
        events_list = group.get("events")
        if isinstance(events_list, list):
            events_list.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        page_paths = group.get("page_paths")
        group["page_label"] = ", ".join(page_paths[:3]) if isinstance(page_paths, list) and page_paths else "-"
        if isinstance(page_paths, list) and len(page_paths) > 3:
            group["page_label"] = f"{group['page_label']} +{len(page_paths) - 3}"
    return grouped


def summarize_traffic(start: datetime, end: datetime) -> dict[str, object]:
    events = iter_traffic_events(start, end)
    page_views = [event for event in events if event.get("type") == "page_view"]
    form_submissions = [event for event in events if event.get("type") == "form_submission"]
    visit_groups = group_traffic_events(events)
    page_visit_groups = [group for group in visit_groups if int(group.get("page_view_count", 0)) > 0]

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "events": events,
        "visit_groups": visit_groups,
        "totals": {
            "page_views": len(page_views),
            "unique_visitors": len(visit_groups),
            "unique_page_visitors": len(page_visit_groups),
            "form_submissions": len(form_submissions),
            "conversion_rate": round((len(form_submissions) / len(page_visit_groups) * 100), 1) if page_visit_groups else 0,
        },
        "pages": count_by(page_views, lambda event: event.get("path"), 60),
        "regions": count_by(
            visit_groups,
            lambda group: group.get("location_label", ""),
            60,
        ),
        "countries": count_by(visit_groups, lambda group: group.get("location_label", ""), 60),
        "devices": count_by(visit_groups, lambda group: group.get("device", ""), 20),
        "referrers": count_by(visit_groups, lambda group: group.get("referrer") or "Direct", 60),
        "recent_groups": visit_groups,
    }


def traffic_period_label(start: datetime, end: datetime) -> str:
    local_start = start.astimezone(SITE_TIMEZONE)
    local_end = (end - timedelta(seconds=1)).astimezone(SITE_TIMEZONE)
    if (end - start).days >= 7:
        return f"{local_start.strftime('%Y-%m-%d')} to {local_end.strftime('%Y-%m-%d')}"
    return local_start.strftime("%Y-%m-%d")


def traffic_report_subject(period: str, start: datetime, end: datetime) -> str:
    label = "Weekly" if period == "week" else "Daily"
    return f"{label} onlyPT traffic report - {traffic_period_label(start, end)}"


def build_traffic_report(
    period: str,
    reference: datetime | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    period_name: str | None = None,
    period_label: str | None = None,
    subject: str | None = None,
) -> dict[str, str]:
    if start is None or end is None:
        start, end = period_bounds(period, reference)
    summary = summarize_traffic(start, end)
    totals = summary["totals"]
    period_name = period_name or ("Weekly" if period == "week" else "Daily")
    period_label = period_label or traffic_period_label(start, end)

    def lines_for_table(title: str, rows: list[dict[str, object]]) -> list[str]:
        output = [title]
        if not rows:
            output.append("- No data")
            return output
        output.extend(f"- {row['label']}: {row['count']}" for row in rows)
        return output

    text_lines = [
        f"{period_name} onlyPT traffic report",
        period_label,
        "",
        f"Page views: {totals['page_views']}",
        f"Unique visitors: {totals['unique_visitors']}",
        f"Form submissions: {totals['form_submissions']}",
        f"Conversion rate: {totals['conversion_rate']}%",
        "",
        *lines_for_table("Top pages", summary["pages"]),
        "",
        *lines_for_table("Top regions", summary["regions"]),
        "",
        *lines_for_table("Devices", summary["devices"]),
        "",
        *lines_for_table("Referrers", summary["referrers"]),
    ]
    text_body = "\n".join(text_lines)

    def html_rows(rows: list[dict[str, object]]) -> str:
        if not rows:
            return '<tr><td colspan="2" style="padding:12px;color:#5f6d68;">No data</td></tr>'
        return "\n".join(
            f"""
            <tr>
              <td style="padding:10px 12px;border-bottom:1px solid #e4e9e5;color:#18211f;font-weight:700;">{html.escape(str(row['label']))}</td>
              <td style="padding:10px 12px;border-bottom:1px solid #e4e9e5;color:#1d6f67;font-weight:800;text-align:right;">{row['count']}</td>
            </tr>
            """
            for row in rows
        )

    def table_block(title: str, rows: list[dict[str, object]]) -> str:
        return f"""
        <h2 style="margin:26px 0 10px;font-family:Arial,sans-serif;font-size:16px;line-height:1.3;color:#18211f;">{html.escape(title)}</h2>
        <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;background:#fffffb;border:1px solid #e4e9e5;border-radius:8px;overflow:hidden;">
          {html_rows(rows)}
        </table>
        """

    html_body = f"""<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
  <body style="margin:0;padding:0;background:#f7f5ee;color:#18211f;">
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:#f7f5ee;border-collapse:collapse;">
      <tr>
        <td align="center" style="padding:28px 14px;">
          <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:760px;background:#fffffb;border:1px solid #dce8e3;border-radius:8px;overflow:hidden;">
            <tr>
              <td style="padding:28px 30px;background:#fffffb;border-bottom:1px solid #dce8e3;">
                <div style="font-family:Georgia,serif;font-size:30px;font-weight:700;color:#18211f;">onlyPT</div>
                <p style="margin:10px 0 0;font-family:Arial,sans-serif;font-size:12px;font-weight:800;letter-spacing:0.12em;text-transform:uppercase;color:#1d6f67;">{html.escape(period_name)} traffic report</p>
                <h1 style="margin:18px 0 0;font-family:Georgia,serif;font-size:34px;line-height:1.05;color:#18211f;">{html.escape(period_label)}</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:24px 30px 30px;">
                <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;">
                  <tr>
                    <td style="padding:14px;background:#f7f5ee;border:1px solid #e4e9e5;"><small style="display:block;color:#5f6d68;font-family:Arial,sans-serif;font-size:11px;font-weight:800;text-transform:uppercase;">Page views</small><strong style="display:block;margin-top:7px;font-family:Georgia,serif;font-size:30px;">{totals['page_views']}</strong></td>
                    <td style="padding:14px;background:#f7f5ee;border:1px solid #e4e9e5;"><small style="display:block;color:#5f6d68;font-family:Arial,sans-serif;font-size:11px;font-weight:800;text-transform:uppercase;">Unique visitors</small><strong style="display:block;margin-top:7px;font-family:Georgia,serif;font-size:30px;">{totals['unique_visitors']}</strong></td>
                    <td style="padding:14px;background:#f7f5ee;border:1px solid #e4e9e5;"><small style="display:block;color:#5f6d68;font-family:Arial,sans-serif;font-size:11px;font-weight:800;text-transform:uppercase;">Form submissions</small><strong style="display:block;margin-top:7px;font-family:Georgia,serif;font-size:30px;">{totals['form_submissions']}</strong></td>
                    <td style="padding:14px;background:#f7f5ee;border:1px solid #e4e9e5;"><small style="display:block;color:#5f6d68;font-family:Arial,sans-serif;font-size:11px;font-weight:800;text-transform:uppercase;">Conversion</small><strong style="display:block;margin-top:7px;font-family:Georgia,serif;font-size:30px;">{totals['conversion_rate']}%</strong></td>
                  </tr>
                </table>
                {table_block("Top pages", summary["pages"])}
                {table_block("Top regions", summary["regions"])}
                {table_block("Devices", summary["devices"])}
                {table_block("Referrers", summary["referrers"])}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""

    return {
        "subject": subject or traffic_report_subject(period, start, end),
        "text": text_body,
        "html": html_body,
        "start": start.isoformat(),
        "end": end.isoformat(),
    }


def send_traffic_report(period: str, reference: datetime | None = None) -> bool:
    config = traffic_report_config()
    if period == "day" and config["daily_enabled"] != "on":
        return False
    if period == "week" and config["weekly_enabled"] != "on":
        return False
    report = build_traffic_report(period, reference)
    return send_smtp_email(report["subject"], report["text"], report["html"], config["to"], require_enabled=False)


def process_scheduled_traffic_reports(reference: datetime | None = None) -> int:
    reference = reference or datetime.now(timezone.utc)
    local_reference = reference.astimezone(SITE_TIMEZONE)
    state = load_json_file(TRAFFIC_REPORT_STATE_FILE, {})
    sent_count = 0

    yesterday = reference - timedelta(days=1)
    daily_start, _daily_end = period_bounds("day", yesterday)
    daily_key = daily_start.strftime("%Y-%m-%d")
    if state.get("daily_last_sent") != daily_key and local_reference.hour >= 1:
        if send_traffic_report("day", yesterday):
            state["daily_last_sent"] = daily_key
            sent_count += 1

    if local_reference.weekday() == 0 and local_reference.hour >= 2:
        previous_week = reference - timedelta(days=7)
        weekly_start, _weekly_end = period_bounds("week", previous_week)
        weekly_key = weekly_start.strftime("%Y-%m-%d")
        if state.get("weekly_last_sent") != weekly_key:
            if send_traffic_report("week", previous_week):
                state["weekly_last_sent"] = weekly_key
                sent_count += 1

    try:
        write_json_file(TRAFFIC_REPORT_STATE_FILE, state)
    except OSError as error:
        log_notification_error(f"Traffic report state write failed: {error}")
    return sent_count


def run_scheduled_jobs() -> dict[str, int]:
    return {
        "queued_emails_sent": process_email_queue(),
        "traffic_reports_sent": process_scheduled_traffic_reports(),
    }


def normalized_form_email() -> str:
    return email_address(request.form.get("email", "")).lower()


def submission_rate_limit_message() -> str:
    limits = load_json_file(SUBMISSION_LIMIT_FILE, {"ips": {}, "emails": {}})
    current_time = now_timestamp()
    ip = client_ip_address()
    email = normalized_form_email()

    ips = limits.setdefault("ips", {})
    emails = limits.setdefault("emails", {})
    ip_events = [event for event in ips.get(ip, []) if current_time - float(event) < IP_SUBMISSION_WINDOW_SECONDS]
    email_events = [
        event for event in emails.get(email, []) if email and current_time - float(event) < EMAIL_SUBMISSION_WINDOW_SECONDS
    ]

    ips[ip] = ip_events
    if email:
        emails[email] = email_events

    if len(ip_events) >= IP_SUBMISSION_LIMIT:
        write_json_file(SUBMISSION_LIMIT_FILE, limits)
        return "Too many submissions from this network. Please wait a few minutes and try again."

    if email and len(email_events) >= EMAIL_SUBMISSION_LIMIT:
        write_json_file(SUBMISSION_LIMIT_FILE, limits)
        return "Too many submissions from this email address. Please wait before sending another message."

    ip_events.append(current_time)
    if email:
        email_events.append(current_time)
    write_json_file(SUBMISSION_LIMIT_FILE, limits)
    return ""


def lead_id_for(row: dict[str, str]) -> str:
    signature = "|".join(
        str(row.get(key, "")).strip()
        for key in ("created_at", "email", "name", "organization", "phone", "role", "message")
    )
    return hashlib.sha1(signature.encode("utf-8")).hexdigest()[:16]


def default_lead_thread() -> dict[str, object]:
    return {
        "status": "new",
        "next_step": "",
        "notes": [],
        "updated_at": "",
    }


def load_lead_threads() -> dict[str, dict[str, object]]:
    if not LEAD_THREADS_FILE.exists():
        return {}

    try:
        with LEAD_THREADS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}

    if not isinstance(data, dict):
        return {}

    normalized = {}
    for lead_id, thread in data.items():
        if not isinstance(thread, dict):
            continue
        notes = thread.get("notes", [])
        normalized[str(lead_id)] = {
            "status": str(thread.get("status", "new") or "new"),
            "next_step": str(thread.get("next_step", "") or ""),
            "updated_at": str(thread.get("updated_at", "") or ""),
            "notes": notes if isinstance(notes, list) else [],
        }
    return normalized


def save_lead_threads(threads: dict[str, dict[str, object]]) -> None:
    LEAD_THREADS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LEAD_THREADS_FILE.open("w", encoding="utf-8") as file:
        json.dump(threads, file, ensure_ascii=False, indent=2)


def read_leads() -> list[dict[str, str]]:
    if not LEADS_FILE.exists():
        return []

    try:
        with LEADS_FILE.open("r", newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
    except OSError:
        return []

    threads = load_lead_threads()
    for row in rows:
        lead_id = lead_id_for(row)
        thread = {
            **default_lead_thread(),
            **threads.get(lead_id, {}),
        }
        row["lead_id"] = lead_id
        row["thread_status"] = str(thread.get("status", "new"))
        row["thread_next_step"] = str(thread.get("next_step", ""))
        row["thread_updated_at"] = str(thread.get("updated_at", ""))
        row["thread_notes"] = thread.get("notes", [])
        row["thread_note_count"] = str(len(row["thread_notes"]) if isinstance(row["thread_notes"], list) else 0)

    rows.reverse()
    return rows


def update_lead_thread(lead_id: str, status: str, next_step: str, note: str) -> dict[str, object]:
    valid_ids = {lead["lead_id"] for lead in read_leads()}
    if lead_id not in valid_ids:
        abort(404)

    threads = load_lead_threads()
    thread = {
        **default_lead_thread(),
        **threads.get(lead_id, {}),
    }
    now = datetime.now(timezone.utc).isoformat()
    clean_status = status.strip() or "new"
    if clean_status not in {"new", "contacted", "in_conversation", "follow_up", "closed"}:
        clean_status = "new"

    thread["status"] = clean_status
    thread["next_step"] = next_step.strip()
    thread["updated_at"] = now
    clean_note = note.strip()
    if clean_note:
        notes = thread.get("notes", [])
        if not isinstance(notes, list):
            notes = []
        notes.append(
            {
                "created_at": now,
                "body": clean_note,
            }
        )
        thread["notes"] = notes

    threads[lead_id] = thread
    save_lead_threads(threads)
    return thread


def twilio_whatsapp_address(value: str) -> str:
    address = value.strip()
    if not address:
        return ""
    return address if address.lower().startswith("whatsapp:") else f"whatsapp:{address}"


def log_notification_error(message: str) -> None:
    NOTIFICATIONS_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with NOTIFICATIONS_LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")


def format_lead_notification(form_data: dict[str, str]) -> str:
    audience_label = {
        "employer": "Healthcare employer",
        "therapist": "Physical Therapist",
    }.get(form_data.get("audience", ""), form_data.get("audience", "Unknown"))
    lines = [
        "New onlyPT contact form submission",
        f"Audience: {audience_label}",
        f"Name: {form_data.get('name', '').strip()}",
        f"Email: {form_data.get('email', '').strip()}",
        f"Phone: {form_data.get('phone', '').strip() or '-'}",
        f"Organization: {form_data.get('organization', '').strip() or '-'}",
        f"Role/setting: {form_data.get('role', '').strip() or '-'}",
        "",
        "Message:",
        form_data.get("message", "").strip(),
    ]
    body = "\n".join(lines).strip()
    return body if len(body) <= 1550 else f"{body[:1546]}\n..."


def email_address(value: str) -> str:
    _name, address = parseaddr(value.strip())
    return address if "@" in address else ""


def email_recipients(value: str) -> list[str]:
    recipients = []
    seen = set()
    for _name, address in getaddresses([value]):
        normalized = address.strip()
        if "@" not in normalized or normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        recipients.append(normalized)
    return recipients


def email_domain(address: str) -> str:
    if "@" not in address:
        return ""
    return address.rsplit("@", 1)[1].strip().lower()


def email_rate_has_slot(current_time: float | None = None) -> bool:
    current_time = current_time or now_timestamp()
    rate_data = load_json_file(EMAIL_RATE_FILE, {"sent_at": []})
    sent_at = [event for event in rate_data.get("sent_at", []) if current_time - float(event) < GLOBAL_EMAIL_WINDOW_SECONDS]
    rate_data["sent_at"] = sent_at
    write_json_file(EMAIL_RATE_FILE, rate_data)
    return len(sent_at) < GLOBAL_EMAIL_LIMIT


def record_email_sent(current_time: float | None = None) -> None:
    current_time = current_time or now_timestamp()
    rate_data = load_json_file(EMAIL_RATE_FILE, {"sent_at": []})
    sent_at = [event for event in rate_data.get("sent_at", []) if current_time - float(event) < GLOBAL_EMAIL_WINDOW_SECONDS]
    sent_at.append(current_time)
    rate_data["sent_at"] = sent_at
    write_json_file(EMAIL_RATE_FILE, rate_data)


def queued_lead_signature(form_data: dict[str, str]) -> str:
    signature = "|".join(
        str(form_data.get(key, "")).strip().lower()
        for key in ("email", "name", "organization", "phone", "role", "message")
    )
    return hashlib.sha1(signature.encode("utf-8")).hexdigest()


def enqueue_lead_email(form_data: dict[str, str], reason: str = "rate_limited") -> bool:
    queue = load_json_file(EMAIL_QUEUE_FILE, [])
    signature = queued_lead_signature(form_data)
    if any(item.get("signature") == signature and item.get("status") == "queued" for item in queue):
        return False

    queued_data = {key: str(value) for key, value in form_data.items()}
    queue.append(
        {
            "id": hashlib.sha1(f"{signature}|{now_timestamp()}".encode("utf-8")).hexdigest()[:16],
            "signature": signature,
            "status": "queued",
            "reason": reason,
            "attempts": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "next_attempt_at": now_timestamp(),
            "form_data": queued_data,
        }
    )
    write_json_file(EMAIL_QUEUE_FILE, queue)
    log_notification_error(f"Queued lead email notification because {reason}.")
    return True


def process_email_queue() -> int:
    queue = load_json_file(EMAIL_QUEUE_FILE, [])
    if not queue:
        return 0

    current_time = now_timestamp()
    delivered_count = 0
    changed = False
    for item in queue:
        if item.get("status") != "queued":
            continue
        if float(item.get("next_attempt_at", 0) or 0) > current_time:
            continue
        if not email_rate_has_slot(current_time):
            break

        item["attempts"] = int(item.get("attempts", 0)) + 1
        if send_lead_email_now(item.get("form_data", {})):
            item["status"] = "sent"
            item["sent_at"] = datetime.now(timezone.utc).isoformat()
            record_email_sent(current_time)
            delivered_count += 1
        elif item["attempts"] >= MAX_EMAIL_QUEUE_ATTEMPTS:
            item["status"] = "failed"
            item["failed_at"] = datetime.now(timezone.utc).isoformat()
            log_notification_error(f"Queued lead email notification failed permanently after {item['attempts']} attempts.")
        else:
            item["next_attempt_at"] = current_time + min(15 * 60 * item["attempts"], 60 * 60)
        changed = True

    if changed:
        write_json_file(EMAIL_QUEUE_FILE, queue)
    return delivered_count


def lead_email_config() -> dict[str, str]:
    email_values = load_content_overrides().get("email", {})

    def email_setting(field_key: str, fallback: str = "") -> str:
        if field_key in email_values:
            return str(email_values.get(field_key, "")).strip()
        return content_value("general", field_key, fallback).strip()

    return {
        "enabled": email_setting("lead_email.enabled", "off").lower(),
        "to": email_setting("lead_email.to"),
        "from_email": email_setting("lead_email.from_email"),
        "from_name": email_setting("lead_email.from_name", "onlyPT Recruiting") or "onlyPT Recruiting",
        "smtp_host": email_setting("lead_email.smtp_host", "smtppro.zoho.com"),
        "smtp_port": email_setting("lead_email.smtp_port", "465"),
        "smtp_security": email_setting("lead_email.smtp_security", "ssl").lower(),
        "smtp_username": email_setting("lead_email.smtp_username"),
        "smtp_password": email_setting("lead_email.smtp_password"),
    }


def traffic_report_config() -> dict[str, str]:
    email_values = load_content_overrides().get("email", {})
    return {
        "daily_enabled": str(email_values.get("traffic_report.daily_enabled", "off")).strip().lower(),
        "weekly_enabled": str(email_values.get("traffic_report.weekly_enabled", "off")).strip().lower(),
        "to": str(email_values.get("traffic_report.to", "")).strip(),
    }


def send_smtp_email(
    subject: str,
    text_body: str,
    html_body: str,
    to_override: str = "",
    require_enabled: bool = True,
) -> bool:
    config = lead_email_config()
    if require_enabled and config["enabled"] != "on":
        return False

    sender_email = email_address(config["from_email"])
    smtp_username = email_address(config["smtp_username"])
    recipients = email_recipients(to_override or config["to"])
    required = ["smtp_host", "smtp_port", "smtp_password"]
    if not sender_email or not smtp_username or not recipients or not all(config.get(key) for key in required):
        log_notification_error("SMTP email notification is enabled but required settings are missing.")
        return False

    try:
        port = int(config["smtp_port"])
    except ValueError:
        log_notification_error(f"SMTP email notification has invalid port: {config['smtp_port']}")
        return False

    message = EmailMessage()
    sender_name = config["from_name"]
    sender_domain = email_domain(sender_email)
    message["Subject"] = subject
    message["From"] = formataddr((sender_name, sender_email))
    message["To"] = ", ".join(recipients)
    message["Date"] = format_datetime(datetime.now(timezone.utc))
    message["Message-ID"] = make_msgid(domain=sender_domain or None)
    message["X-Auto-Response-Suppress"] = "All"
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        if config["smtp_security"] == "ssl":
            with smtplib.SMTP_SSL(config["smtp_host"], port, timeout=10) as smtp:
                smtp.login(smtp_username, config["smtp_password"])
                smtp.send_message(message, from_addr=sender_email, to_addrs=recipients)
        else:
            with smtplib.SMTP(config["smtp_host"], port, timeout=10) as smtp:
                if config["smtp_security"] in {"tls", "starttls"}:
                    smtp.starttls()
                smtp.login(smtp_username, config["smtp_password"])
                smtp.send_message(message, from_addr=sender_email, to_addrs=recipients)
    except (OSError, smtplib.SMTPException) as error:
        log_notification_error(f"SMTP email notification failed: {error}")
        return False

    return True


def lead_email_html(form_data: dict[str, str]) -> str:
    audience_label = {
        "employer": "Healthcare employer",
        "therapist": "Physical Therapist",
    }.get(form_data.get("audience", ""), form_data.get("audience", "Unknown"))
    submitted_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = [
        ("Audience", audience_label),
        ("Name", form_data.get("name", "").strip()),
        ("Email", form_data.get("email", "").strip()),
        ("Phone", form_data.get("phone", "").strip() or "-"),
        ("Organization", form_data.get("organization", "").strip() or "-"),
        ("Role / setting", form_data.get("role", "").strip() or "-"),
        ("Submitted", submitted_at),
    ]
    detail_rows = "\n".join(
        f"""
        <tr>
          <th style="padding:14px 18px;text-align:left;font-family:Arial,sans-serif;font-size:11px;line-height:1.4;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#5f6d68;border-bottom:1px solid #e4e9e5;width:170px;">{html.escape(label)}</th>
          <td style="padding:14px 18px;font-family:Arial,sans-serif;font-size:15px;line-height:1.55;font-weight:600;color:#18211f;border-bottom:1px solid #e4e9e5;">{html.escape(value)}</td>
        </tr>
        """
        for label, value in rows
    )
    message = html.escape(form_data.get("message", "").strip()).replace("\n", "<br>")
    preheader = f"New onlyPT lead from {form_data.get('name', '').strip() or 'the contact form'}"
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light">
    <meta name="supported-color-schemes" content="light">
    <title>New onlyPT contact form submission</title>
  </head>
  <body style="margin:0;padding:0;background:#f7f5ee;color:#18211f;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{html.escape(preheader)}</div>
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;background:#f7f5ee;">
      <tr>
        <td align="center" style="padding:28px 14px;">
          <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;max-width:680px;border-collapse:collapse;background:#fffffb;border:1px solid #dce8e3;border-radius:8px;overflow:hidden;">
            <tr>
              <td style="padding:28px 30px 26px;background:#fffffb;border-bottom:1px solid #dce8e3;">
                <div style="font-family:Georgia,serif;font-size:32px;line-height:1;font-weight:700;color:#18211f;letter-spacing:0;">onlyPT</div>
                <div style="margin-top:8px;font-family:Arial,sans-serif;font-size:12px;line-height:1.4;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#1d6f67;">Recruiting contact notification</div>
                <h1 style="margin:22px 0 0;font-family:Georgia,serif;font-size:34px;line-height:1.08;font-weight:700;color:#18211f;">New contact form submission</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:0;">
                <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;border-collapse:collapse;background:#fffffb;">
                  {detail_rows}
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:26px 30px 30px;background:#fffffb;">
                <div style="font-family:Arial,sans-serif;font-size:11px;line-height:1.4;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#5f6d68;margin-bottom:12px;">Message</div>
                <div style="font-family:Arial,sans-serif;font-size:16px;line-height:1.65;font-weight:500;color:#18211f;background:#f7f5ee;border:1px solid #e4e9e5;border-radius:8px;padding:18px;">{message}</div>
              </td>
            </tr>
            <tr>
              <td style="padding:18px 30px 24px;background:#f7f5ee;border-top:1px solid #e4e9e5;">
                <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;line-height:1.6;color:#5f6d68;">This transactional notification was generated by the onlyPT website contact form. Replying to this email will reply to the submitter when their email address is valid.</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def send_lead_email_now(form_data: dict[str, str]) -> bool:
    config = lead_email_config()
    if config["enabled"] != "on":
        return False

    sender_email = email_address(config["from_email"])
    smtp_username = email_address(config["smtp_username"])
    recipients = email_recipients(config["to"])
    required = ["smtp_host", "smtp_port", "smtp_password"]
    if not sender_email or not smtp_username or not recipients or not all(config.get(key) for key in required):
        log_notification_error("SMTP email notification is enabled but required settings are missing.")
        return False

    try:
        port = int(config["smtp_port"])
    except ValueError:
        log_notification_error(f"SMTP email notification has invalid port: {config['smtp_port']}")
        return False

    message = EmailMessage()
    sender_name = config["from_name"]
    sender_domain = email_domain(sender_email)
    message["Subject"] = "New onlyPT contact form submission"
    message["From"] = formataddr((sender_name, sender_email))
    message["To"] = ", ".join(recipients)
    message["Date"] = format_datetime(datetime.now(timezone.utc))
    message["Message-ID"] = make_msgid(domain=sender_domain or None)
    message["X-Auto-Response-Suppress"] = "All"
    message["X-Entity-Ref-ID"] = f"onlypt-contact-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    submitter_email = email_address(form_data.get("email", ""))
    if submitter_email:
        message["Reply-To"] = submitter_email
    message.set_content(format_lead_notification(form_data))
    message.add_alternative(lead_email_html(form_data), subtype="html")

    try:
        if config["smtp_security"] == "ssl":
            with smtplib.SMTP_SSL(config["smtp_host"], port, timeout=10) as smtp:
                smtp.login(smtp_username, config["smtp_password"])
                smtp.send_message(message, from_addr=sender_email, to_addrs=recipients)
        else:
            with smtplib.SMTP(config["smtp_host"], port, timeout=10) as smtp:
                if config["smtp_security"] in {"tls", "starttls"}:
                    smtp.starttls()
                smtp.login(smtp_username, config["smtp_password"])
                smtp.send_message(message, from_addr=sender_email, to_addrs=recipients)
    except (OSError, smtplib.SMTPException) as error:
        log_notification_error(f"SMTP email notification failed: {error}")
        return False

    return True


def notify_lead_email(form_data: dict[str, str]) -> bool:
    process_email_queue()
    current_time = now_timestamp()
    if not email_rate_has_slot(current_time):
        enqueue_lead_email(form_data, "global email rate limit")
        return False

    if send_lead_email_now(form_data):
        record_email_sent(current_time)
        return True

    enqueue_lead_email(form_data, "send failure")
    return False


def notify_lead_whatsapp(form_data: dict[str, str]) -> bool:
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, TWILIO_WHATSAPP_TO]):
        return False

    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{urllib.parse.quote(TWILIO_ACCOUNT_SID)}/Messages.json"
    payload = urllib.parse.urlencode(
        {
            "From": twilio_whatsapp_address(TWILIO_WHATSAPP_FROM),
            "To": twilio_whatsapp_address(TWILIO_WHATSAPP_TO),
            "Body": format_lead_notification(form_data),
        }
    ).encode("utf-8")
    auth_header = b"Basic " + b64encode(f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode("utf-8"))
    request_message = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": auth_header.decode("ascii"),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request_message, timeout=8) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:500]
        log_notification_error(f"Twilio WhatsApp HTTP {error.code}: {detail}")
    except OSError as error:
        log_notification_error(f"Twilio WhatsApp request failed: {error}")
    return False


def content_field_defaults(page_key: str) -> dict[str, str]:
    page = CONTENT_PAGES.get(page_key, {})
    return {field["key"]: field["default"] for field in page.get("fields", [])}


def load_content_overrides() -> dict[str, dict[str, str]]:
    if not CONTENT_FILE.exists():
        return {}

    try:
        with CONTENT_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}

    if not isinstance(data, dict):
        return {}

    normalized: dict[str, dict[str, str]] = {}
    for page_key, page_values in data.items():
        if isinstance(page_values, dict):
            normalized[str(page_key)] = {str(key): str(value) for key, value in page_values.items()}
    return normalized


def content_value(page_key: str, field_key: str, fallback: str | None = None) -> str:
    defaults = content_field_defaults(page_key)
    default = defaults.get(field_key, fallback or "")
    page_values = load_content_overrides().get(page_key, {})
    if page_key == "general" and field_key == "background.image" and not page_values.get(field_key):
        legacy_names = parse_background_image_names(page_values.get("background.images", ""))
        return legacy_names[0] if legacy_names else default
    if page_key == "general" and field_key == "background.images" and not page_values.get(field_key):
        return page_values.get("background.image", default)
    return page_values.get(field_key, default)


def first_block_start_height() -> int:
    raw_value = content_value("general", "layout.first_section_top", "22")
    try:
        value = int(float(str(raw_value).strip()))
    except (TypeError, ValueError):
        value = 22
    return max(0, min(120, value))


def editor_content_value(page_key: str, field_key: str, fallback: str | None = None) -> str:
    if page_key == "email":
        page_values = load_content_overrides().get("email", {})
        if field_key in page_values:
            return str(page_values.get(field_key, ""))
        return content_value("general", field_key, fallback)

    return content_value(page_key, field_key, fallback)


def save_content_values(page_key: str, values: dict[str, str]) -> dict[str, str]:
    page = CONTENT_PAGES.get(page_key)
    if page is None:
        abort(404)

    allowed = content_field_defaults(page_key)
    existing_values = {
        **allowed,
        **load_content_overrides().get(page_key, {}),
    }
    clean_values = {
        key: str(values.get(key, existing_values.get(key, ""))).strip()
        for key in allowed
    }
    all_content = load_content_overrides()
    all_content[page_key] = clean_values

    CONTENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CONTENT_FILE.open("w", encoding="utf-8") as file:
        json.dump(all_content, file, ensure_ascii=False, indent=2)

    return clean_values


def background_is_enabled() -> bool:
    return content_value("general", "background.enabled", "off").lower() == "on"


def parse_background_image_names(raw_value: str) -> list[str]:
    value = raw_value.strip()
    if not value:
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = [item.strip() for item in value.split(",")]

    if not isinstance(parsed, list):
        return []

    names = []
    seen = set()
    for item in parsed:
        safe_name = secure_filename(Path(str(item)).name)
        if not safe_name or safe_name in seen:
            continue
        if not (BACKGROUND_UPLOAD_DIR / safe_name).exists():
            continue
        seen.add(safe_name)
        names.append(safe_name)
    return names


def background_image_names() -> list[str]:
    image_name = content_value("general", "background.image", "").strip()
    image_names = parse_background_image_names(image_name)
    if image_names:
        return image_names[:1]

    legacy_names = parse_background_image_names(content_value("general", "background.images", ""))
    return legacy_names[:1]


def background_image_urls() -> list[str]:
    return [url_for("uploaded_background", filename=image_name) for image_name in background_image_names()[:1]]


def background_image_url() -> str:
    urls = background_image_urls()
    return urls[0] if urls else ""


def favicon_name() -> str:
    image_name = content_value("general", "site.favicon", "").strip()
    safe_name = secure_filename(Path(image_name).name)
    if safe_name and (FAVICON_UPLOAD_DIR / safe_name).exists():
        return safe_name
    return ""


def favicon_url() -> str:
    image_name = favicon_name()
    return url_for("uploaded_favicon", filename=image_name) if image_name else ""


def save_favicon_config(image_name: str | None) -> dict[str, str]:
    all_content = load_content_overrides()
    general_values = {
        **content_field_defaults("general"),
        **all_content.get("general", {}),
    }
    safe_name = secure_filename(Path(str(image_name or "")).name)
    if safe_name and not (FAVICON_UPLOAD_DIR / safe_name).exists():
        safe_name = ""

    general_values["site.favicon"] = safe_name
    all_content["general"] = {
        key: str(general_values.get(key, "")).strip()
        for key in content_field_defaults("general")
    }
    CONTENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CONTENT_FILE.open("w", encoding="utf-8") as file:
        json.dump(all_content, file, ensure_ascii=False, indent=2)

    return all_content["general"]


def save_background_config(image_name: str | None, enabled: str | None = None) -> dict[str, str]:
    all_content = load_content_overrides()
    general_values = {
        **content_field_defaults("general"),
        **all_content.get("general", {}),
    }
    safe_name = secure_filename(Path(str(image_name or "")).name)
    if safe_name and not (BACKGROUND_UPLOAD_DIR / safe_name).exists():
        safe_name = ""

    general_values["background.image"] = safe_name
    if enabled is not None:
        general_values["background.enabled"] = enabled

    all_content["general"] = {
        key: str(general_values.get(key, "")).strip()
        for key in content_field_defaults("general")
    }
    all_content["general"].pop("background.images", None)
    CONTENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CONTENT_FILE.open("w", encoding="utf-8") as file:
        json.dump(all_content, file, ensure_ascii=False, indent=2)

    return all_content["general"]


def allowed_background_file(filename: str) -> bool:
    extension = Path(filename).suffix.lower().lstrip(".")
    return extension in ALLOWED_BACKGROUND_EXTENSIONS


def allowed_favicon_file(filename: str) -> bool:
    extension = Path(filename).suffix.lower().lstrip(".")
    return extension in ALLOWED_FAVICON_EXTENSIONS


def cms_text(page_key: str, field_key: str, fallback: str | None = None) -> str:
    return content_value(page_key, field_key, fallback)


def cms_attrs(page_key: str, field_key: str) -> Markup:
    if not session.get("admin_authenticated") or request.args.get("admin_preview") != "1":
        return Markup("")

    return Markup(
        'data-cms-page="{}" data-cms-key="{}" data-cms-editable="true"'.format(
            escape(page_key),
            escape(field_key),
        )
    )


def admin_is_authenticated() -> bool:
    return bool(session.get("admin_authenticated"))


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not admin_is_authenticated():
            return redirect(url_for("admin_login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def draft_file_for(page_key: str) -> Path:
    return PAGE_EDITS_DIR / f"{page_key}.json"


def load_page_draft(page_key: str) -> dict[str, str]:
    path = draft_file_for(page_key)
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}

    return data if isinstance(data, dict) else {}


def save_page_draft(page_key: str, form_data: dict[str, str]) -> dict[str, str]:
    existing = load_page_draft(page_key)
    now = datetime.now(timezone.utc).isoformat()
    draft = {
        "page": page_key,
        "created_at": existing.get("created_at", now),
        "updated_at": now,
    }
    for field in PAGE_DRAFT_FIELDS:
        draft[field] = form_data.get(field, "").strip()

    PAGE_EDITS_DIR.mkdir(parents=True, exist_ok=True)
    with draft_file_for(page_key).open("w", encoding="utf-8") as file:
        json.dump(draft, file, ensure_ascii=False, indent=2)

    return draft


@app.context_processor
def inject_site_context():
    site_background_urls = background_image_urls()
    return {
        "nav_items": [
            ("home", "nav.home", "home"),
            ("employers", "nav.employers", "employers"),
            ("therapists", "nav.therapists", "therapists"),
            ("about", "nav.about", "about"),
            ("contact", "nav.contact", "contact"),
        ],
        "editable_pages": EDITABLE_PAGES,
        "content_pages": CONTENT_PAGES,
        "cms_text": cms_text,
        "cms_attrs": cms_attrs,
        "admin_is_authenticated": admin_is_authenticated(),
        "site_background_enabled": background_is_enabled() and bool(site_background_urls),
        "site_background_url": site_background_urls[0] if site_background_urls else "",
        "site_background_urls": site_background_urls,
        "site_favicon_url": favicon_url(),
        "first_block_start_height": first_block_start_height(),
    }


@app.after_request
def add_dev_editor_headers(response):
    if should_record_page_view(response):
        event = base_traffic_event("page_view")
        event["status_code"] = response.status_code
        append_traffic_event(event)

    if request.path.startswith("/dev/") or request.path.startswith("/admin") or request.args.get("admin_preview") == "1":
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def home():
    return render_template("index.html", page="home")


@app.get("/employers")
def employers():
    return render_template("employers.html", page="employers")


@app.get("/therapists")
def therapists():
    return render_template("therapists.html", page="therapists")


@app.get("/about")
def about():
    return render_template("about.html", page="about")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        required = ["name", "email", "message"]
        if not all(request.form.get(field, "").strip() for field in required):
            flash(cms_text("contact", "flash.missing"), "error")
            return redirect(url_for("contact"))

        rate_limit_message = submission_rate_limit_message()
        if rate_limit_message:
            flash(rate_limit_message, "error")
            return redirect(url_for("contact"))

        lead_data = request.form.to_dict()
        write_lead(lead_data)
        record_form_submission_event(lead_data)
        notify_lead_email(lead_data)
        notify_lead_whatsapp(lead_data)
        flash(cms_text("contact", "flash.success"), "success")
        return redirect(url_for("contact"))

    audience = request.args.get("audience", "employer")
    return render_template("contact.html", page="contact", audience=audience)


@app.get("/uploads/backgrounds/<path:filename>")
def uploaded_background(filename: str):
    safe_name = secure_filename(Path(filename).name)
    if safe_name != filename:
        abort(404)
    return send_from_directory(BACKGROUND_UPLOAD_DIR, safe_name)


@app.get("/uploads/favicons/<path:filename>")
def uploaded_favicon(filename: str):
    safe_name = secure_filename(Path(filename).name)
    if safe_name != filename:
        abort(404)
    return send_from_directory(FAVICON_UPLOAD_DIR, safe_name)


@app.get("/admin")
def admin_index():
    if admin_is_authenticated():
        return redirect(url_for("admin_content", page_key="home"))
    return redirect(url_for("admin_login"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_authenticated"] = True
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("admin_content", page_key="home"))

        flash("Invalid admin username or password.", "error")

    return render_template("admin_login.html", page="admin-login")


@app.get("/admin/logout")
@admin_required
def admin_logout():
    session.pop("admin_authenticated", None)
    flash("Signed out of the content editor.", "success")
    return redirect(url_for("admin_login"))


@app.get("/admin/content")
@admin_required
def admin_content_index():
    return redirect(url_for("admin_content", page_key="home"))


@app.get("/admin/leads")
@admin_required
def admin_leads():
    leads = read_leads()
    return render_template("admin_leads.html", page="admin-leads", leads=leads)


@app.get("/admin/traffic")
@admin_required
def admin_traffic():
    period = request.args.get("period", "day")
    if period not in {"day", "week"}:
        period = "day"
    try:
        records_page = max(1, int(request.args.get("records_page", "1")))
    except ValueError:
        records_page = 1
    start, end = period_bounds(period)
    summary = summarize_traffic(start, end)
    records_per_page = 20
    recent_groups = summary.get("recent_groups", [])
    total_records = len(recent_groups) if isinstance(recent_groups, list) else 0
    total_pages = max(1, (total_records + records_per_page - 1) // records_per_page)
    records_page = min(records_page, total_pages)
    page_start = (records_page - 1) * records_per_page
    page_end = page_start + records_per_page
    paginated_records = recent_groups[page_start:page_end] if isinstance(recent_groups, list) else []
    report_config = traffic_report_config()
    return render_template(
        "admin_traffic.html",
        page="admin-traffic",
        period=period,
        period_label=traffic_period_label(start, end),
        summary=summary,
        recent_records=paginated_records,
        records_pagination={
            "page": records_page,
            "pages": total_pages,
            "total": total_records,
            "per_page": records_per_page,
            "start": page_start + 1 if total_records else 0,
            "end": min(page_end, total_records),
        },
        report_config=report_config,
    )


@app.post("/admin/api/leads/<lead_id>/conversation")
@admin_required
def admin_update_lead_conversation(lead_id: str):
    payload = request.get_json(silent=True) or {}
    thread = update_lead_thread(
        lead_id=lead_id,
        status=str(payload.get("status", "")),
        next_step=str(payload.get("next_step", "")),
        note=str(payload.get("note", "")),
    )
    return jsonify({"ok": True, "leadId": lead_id, "thread": thread})


@app.get("/admin/content/<page_key>")
@admin_required
def admin_content(page_key: str):
    page_meta = CONTENT_PAGES.get(page_key)
    if page_meta is None:
        abort(404)

    editor_pages = {}
    for content_page_key, content_page_meta in CONTENT_PAGES.items():
        editor_pages[content_page_key] = {
            "label": content_page_meta["label"],
            "fields": content_page_meta["fields"],
            "values": {
                field["key"]: editor_content_value(content_page_key, field["key"], field["default"])
                for field in content_page_meta["fields"]
            },
            "previewUrl": url_for(content_page_meta["endpoint"], admin_preview=1),
            "saveUrl": url_for("admin_save_content", page_key=content_page_key),
            "editorUrl": url_for("admin_content", page_key=content_page_key),
        }

    return render_template(
        "admin_content.html",
        page="admin-content",
        editing_page_key=page_key,
        editing_page=page_meta,
        editor_pages=editor_pages,
        background_upload_url=url_for("admin_upload_background_image"),
        background_delete_url=url_for("admin_delete_background_image"),
        background_config_url=url_for("admin_save_background_config"),
        favicon_upload_url=url_for("admin_upload_favicon"),
        favicon_delete_url=url_for("admin_delete_favicon"),
        traffic_report_test_url=url_for("admin_send_test_traffic_report"),
    )


@app.post("/admin/api/content/<page_key>")
@admin_required
def admin_save_content(page_key: str):
    if page_key not in CONTENT_PAGES:
        abort(404)

    payload = request.get_json(silent=True) or {}
    values = payload.get("values", {})
    if not isinstance(values, dict):
        return jsonify({"ok": False, "message": "Invalid content payload."}), 400

    saved_values = save_content_values(page_key, values)
    return jsonify(
        {
            "ok": True,
            "page": page_key,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "values": saved_values,
        }
    )


@app.post("/admin/api/traffic-report/test")
@admin_required
def admin_send_test_traffic_report():
    report_config = traffic_report_config()
    recipients = email_recipients(report_config["to"])
    if not recipients:
        return jsonify({"ok": False, "message": "Set Traffic report recipient before sending a test report."}), 400

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=24)
    local_start = start.astimezone(SITE_TIMEZONE)
    local_end = end.astimezone(SITE_TIMEZONE)
    period_label = f"{local_start.strftime('%Y-%m-%d %H:%M')} to {local_end.strftime('%Y-%m-%d %H:%M %Z')}"
    report = build_traffic_report(
        "last24",
        start=start,
        end=end,
        period_name="Past 24 hours",
        period_label=period_label,
        subject=f"Test onlyPT traffic report - past 24 hours - {period_label}",
    )
    sent = send_smtp_email(
        report["subject"],
        report["text"],
        report["html"],
        report_config["to"],
        require_enabled=False,
    )
    if not sent:
        return jsonify({"ok": False, "message": "Could not send the test report. Check SMTP settings and recipient."}), 500

    return jsonify(
        {
            "ok": True,
            "message": f"Test traffic report sent to {', '.join(recipients)}.",
            "recipients": recipients,
            "period": period_label,
        }
    )


@app.post("/admin/api/background-image")
@admin_required
def admin_upload_background_image():
    upload = (request.files.getlist("background") or [None])[0]
    if upload is None or not upload.filename:
        return jsonify({"ok": False, "message": "Choose an image to upload."}), 400

    BACKGROUND_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original_name = secure_filename(upload.filename)
    if not original_name or not allowed_background_file(original_name):
        return jsonify({"ok": False, "message": "Use JPG, PNG, WebP, or GIF images."}), 400

    previous_names = set(background_image_names())
    previous_names.update(parse_background_image_names(content_value("general", "background.images", "")))

    extension = Path(original_name).suffix.lower()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    filename = f"site-background-{stamp}{extension}"
    upload.save(BACKGROUND_UPLOAD_DIR / filename)

    saved_general = save_background_config(filename, enabled="on")
    for previous_name in previous_names:
        if previous_name != filename:
            (BACKGROUND_UPLOAD_DIR / previous_name).unlink(missing_ok=True)

    return jsonify(
        {
            "ok": True,
            "filename": filename,
            "url": url_for("uploaded_background", filename=filename),
            "backgroundImage": saved_general.get("background.image", ""),
            "backgroundImages": [saved_general.get("background.image", "")] if saved_general.get("background.image") else [],
            "backgroundEnabled": saved_general.get("background.enabled", "off"),
        }
    )


@app.post("/admin/api/background-image/delete")
@admin_required
def admin_delete_background_image():
    payload = request.get_json(silent=True) or {}
    filename = secure_filename(Path(str(payload.get("filename", ""))).name)
    if not filename:
        return jsonify({"ok": False, "message": "Choose a background image to remove."}), 400

    current_name = background_image_names()[0] if background_image_names() else ""
    saved_general = save_background_config("" if filename == current_name else current_name)
    (BACKGROUND_UPLOAD_DIR / filename).unlink(missing_ok=True)

    return jsonify(
        {
            "ok": True,
            "removed": filename,
            "backgroundImage": saved_general.get("background.image", ""),
            "backgroundImages": [saved_general.get("background.image", "")] if saved_general.get("background.image") else [],
            "backgroundEnabled": saved_general.get("background.enabled", "off"),
        }
    )


@app.post("/admin/api/background-config")
@admin_required
def admin_save_background_config():
    payload = request.get_json(silent=True) or {}
    enabled = "on" if str(payload.get("enabled", "")).lower() == "on" else "off"
    image_name = background_image_names()[0] if background_image_names() else ""
    if "image" in payload:
        image_name = str(payload.get("image") or "")
    elif isinstance(payload.get("images"), list) and payload["images"]:
        image_name = str(payload["images"][0])

    saved_general = save_background_config(image_name, enabled=enabled)
    return jsonify(
        {
            "ok": True,
            "backgroundImage": saved_general.get("background.image", ""),
            "backgroundImages": [saved_general.get("background.image", "")] if saved_general.get("background.image") else [],
            "backgroundEnabled": saved_general.get("background.enabled", "off"),
        }
    )


@app.post("/admin/api/favicon")
@admin_required
def admin_upload_favicon():
    upload = (request.files.getlist("favicon") or [None])[0]
    if upload is None or not upload.filename:
        return jsonify({"ok": False, "message": "Choose an icon to upload."}), 400

    FAVICON_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original_name = secure_filename(upload.filename)
    if not original_name or not allowed_favicon_file(original_name):
        return jsonify({"ok": False, "message": "Use ICO, PNG, SVG, or WebP icons."}), 400

    previous_name = favicon_name()
    extension = Path(original_name).suffix.lower()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    filename = f"site-favicon-{stamp}{extension}"
    upload.save(FAVICON_UPLOAD_DIR / filename)

    saved_general = save_favicon_config(filename)
    if previous_name and previous_name != filename:
        (FAVICON_UPLOAD_DIR / previous_name).unlink(missing_ok=True)

    return jsonify(
        {
            "ok": True,
            "filename": filename,
            "url": url_for("uploaded_favicon", filename=filename),
            "favicon": saved_general.get("site.favicon", ""),
        }
    )


@app.post("/admin/api/favicon/delete")
@admin_required
def admin_delete_favicon():
    payload = request.get_json(silent=True) or {}
    filename = secure_filename(Path(str(payload.get("filename", ""))).name)
    if not filename:
        return jsonify({"ok": False, "message": "Choose an icon to remove."}), 400

    current_name = favicon_name()
    saved_general = save_favicon_config("" if filename == current_name else current_name)
    (FAVICON_UPLOAD_DIR / filename).unlink(missing_ok=True)

    return jsonify(
        {
            "ok": True,
            "removed": filename,
            "favicon": saved_general.get("site.favicon", ""),
        }
    )


@app.get("/dev/edit")
def edit_page_index():
    return redirect(url_for("edit_page", page_key="home"))


@app.route("/dev/edit/<page_key>", methods=["GET", "POST"])
def edit_page(page_key: str):
    page_meta = EDITABLE_PAGES.get(page_key)
    if page_meta is None:
        abort(404)

    if request.method == "POST":
        save_page_draft(page_key, request.form.to_dict())
        flash("Draft saved. The live website was not changed.", "success")
        return redirect(url_for("edit_page", page_key=page_key))

    draft = load_page_draft(page_key)
    return render_template(
        "edit_page.html",
        page="dev-editor",
        draft=draft,
        editing_page_key=page_key,
        editing_page=page_meta,
        live_page_url=url_for(page_meta["endpoint"]),
    )


if __name__ == "__main__":
    app.run(debug=True)
