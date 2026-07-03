from __future__ import annotations

import csv
import html
import json
import os
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, getaddresses, make_msgid, parseaddr
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from markupsafe import Markup, escape
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-onlypt-secret")

LEADS_FILE = Path(app.instance_path) / "leads.csv"
NOTIFICATIONS_LOG_FILE = Path(app.instance_path) / "notification_errors.log"
PAGE_EDITS_DIR = Path(app.instance_path) / "page_edits"
CONTENT_FILE = Path(app.instance_path) / "content_overrides.json"
UPLOAD_DIR = Path(app.instance_path) / "uploads"
BACKGROUND_UPLOAD_DIR = UPLOAD_DIR / "backgrounds"
FAVICON_UPLOAD_DIR = UPLOAD_DIR / "favicons"
ADMIN_USERNAME = os.environ.get("ONLYPT_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ONLYPT_ADMIN_PASSWORD", "REDACTED_ADMIN_PASSWORD")
ALLOWED_BACKGROUND_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
ALLOWED_FAVICON_EXTENSIONS = {"ico", "png", "svg", "webp"}
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "").strip()
TWILIO_WHATSAPP_TO = os.environ.get("TWILIO_WHATSAPP_TO", "").strip()

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
        ],
    },
    "email": {
        "label": "Email Notifications",
        "endpoint": "contact",
        "fields": [
            cms_field("lead_email.to", "Admin notification email", "", group="Notification target"),
            cms_field("lead_email.enabled", "Send email lead notifications", "off", "toggle", "Notification target"),
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


def read_leads() -> list[dict[str, str]]:
    if not LEADS_FILE.exists():
        return []

    try:
        with LEADS_FILE.open("r", newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
    except OSError:
        return []

    rows.reverse()
    return rows


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


def notify_lead_email(form_data: dict[str, str]) -> bool:
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
    }


@app.after_request
def add_dev_editor_headers(response):
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

        lead_data = request.form.to_dict()
        write_lead(lead_data)
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
