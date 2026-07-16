# onlyPT Recruiting

[中文说明](README.zh-CN.md) | [Live example](https://onlypt.rosebeg.com/)

onlyPT Recruiting is a Flask website and admin CMS for a focused recruiting
site. The current public content is written for Physical Therapy recruiting, but
the same code can be adapted for other small service businesses that need
editable pages, lead capture, admin review, email notifications, and simple
deployment.

![onlyPT Recruiting homepage preview](static/img/readme-preview.png)

## Project Scope

This is a small CMS-backed business website, not a large general-purpose CMS.
It is best suited for focused service websites such as:

- Recruiting agencies collecting employer and candidate inquiries.
- Healthcare, legal, finance, education, or B2B service firms that need a premium marketing site.
- Consultants and boutique operators who want editable pages without a large CMS.
- Lead-generation websites that need contact submissions saved, reviewed, and emailed.
- Single-brand or single-service sites that need consistent visual design across several pages.

The default copy, navigation, and labels are for `onlyPT`, but almost all visible text can be changed from the admin editor.

## Live Example

The production example is available at [https://onlypt.rosebeg.com/](https://onlypt.rosebeg.com/).

Use it to preview:

- Public marketing pages.
- Responsive desktop and mobile layout.
- The persistent global background experience.
- Contact form flow and animated feedback modal.
- The general visual direction of the project.

## Core Features

- Public pages for Home, Employers, Therapists, About, and Contact.
- Admin content editor for page copy, navigation text, footer text, metadata, and contact-page messaging.
- Live admin preview iframe while editing content.
- Editable global site background image.
- Editable favicon / browser tab icon.
- Adjustable first-section vertical offset from the admin panel.
- Contact form with animated success/error feedback modal.
- Lead storage in `instance/leads.csv`.
- Admin lead inbox at `/admin/leads`.
- Per-lead conversation tracking: status, next step, notes, and timestamps.
- SMTP email lead notifications through Zoho or another configured SMTP provider.
- Email notification queue with global send-rate control.
- Contact submission limits:
  - Same IP: maximum 3 submissions per 10 minutes.
  - Same email address: maximum 5 submissions per hour.
  - Global email sending: maximum 2 emails per minute, with overflow queued.
- Optional Twilio WhatsApp lead notifications.
- Persistent same-origin navigation so the shared background does not reload on every page change.
- Runtime uploads and content overrides stored outside Git in `instance/`.

## Reusing It For Other Websites

This project is suitable for any website with the same general shape:

1. A public marketing site with 4-6 core pages.
2. A contact or lead form.
3. A private admin panel for content edits and lead review.
4. Email notification delivery.
5. A consistent brand visual system.

To adapt it for another business:

1. Change public copy in the admin content editor.
2. Replace the background image and favicon in `General`.
3. Update nav labels, footer labels, metadata, and contact method text.
4. Configure SMTP notification settings under `Email Notifications`.
5. Update templates only if the new business needs different page structure, not just different wording.

For most same-type service websites, you should not need to rewrite the application. The admin CMS fields and templates are enough for brand/content changes.

## Technology Stack

- Python + Flask.
- Jinja templates.
- Vanilla CSS and JavaScript.
- CSV/JSON file storage under `instance/`.
- SMTP email notifications using Python `smtplib`.
- Optional Twilio WhatsApp API.

There is no database requirement. This keeps the project easy to deploy on VPS hosting, PaaS, or panel-based Linux servers.

## Local Development

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Environment Variables

The app works locally without environment variables, but production should set secure values.

```text
SECRET_KEY=replace-with-a-long-random-secret
ONLYPT_ADMIN_USERNAME=admin
ONLYPT_ADMIN_PASSWORD=replace-with-a-strong-password
```

Optional WhatsApp notification variables:

```text
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+15551234567
```

## Admin Panel

Open:

```text
/admin/login
```

After login:

- `/admin/content/home` edits site content.
- `/admin/leads` reviews submitted leads.
- `General -> Background` manages the global background.
- `General -> Page Tab` manages the favicon.
- `General -> Layout` controls the first-section starting offset.
- `Email Notifications` manages SMTP settings.

Default development credentials are defined in `app.py`, but production should override them with environment variables.

## Email Notifications

Contact submissions are saved first, then notification delivery is attempted.

Email settings are managed in the admin panel:

- Notification recipient.
- Enable/disable email notifications.
- Sender email and sender display name.
- SMTP host, port, security mode, username, and password.

The current production configuration uses Zoho SMTP. Other SMTP providers can be used if they support authenticated SMTP.

### Rate Control And Queue

To avoid SMTP rate-limit blocks:

- The site sends at most 2 notification emails per minute.
- Extra notifications are written to `instance/email_queue.json`.
- A cron job or other scheduled worker should call `process_email_queue()` every minute.
- Failed queued messages retry with backoff and eventually mark as failed after repeated attempts.

Example cron command:

```cron
* * * * * cd /path/to/project && flock -n /tmp/onlypt-email-queue.lock /path/to/venv/bin/python -c "from app import process_email_queue; process_email_queue()" >> /path/to/instance/email_queue_cron.log 2>&1
```

## Contact Form Limits

The contact form includes server-side limits:

- Same IP: 3 submissions per 10 minutes.
- Same email: 5 submissions per hour.

When a visitor exceeds a limit, the site shows an animated error modal and does not save another duplicate lead.

## Runtime Data

Runtime files are stored in `instance/` and should not be committed:

```text
instance/content_overrides.json    CMS content overrides
instance/leads.csv                 Contact form submissions
instance/lead_threads.json         Lead status and notes
instance/submission_limits.json    Contact submission rate state
instance/email_rate.json           Email send-rate state
instance/email_queue.json          Queued notification emails
instance/notification_errors.log   Email/Twilio delivery errors
instance/uploads/                  Background and favicon uploads
```

## Project Layout

```text
app.py                 Flask app, routes, CMS helpers, lead logic, email queue
templates/            Public pages and admin templates
static/css/           Public and admin styles
static/js/            Public navigation/interactions and admin editor logic
static/img/           Static image assets
instance/             Runtime data, uploads, content overrides, leads
requirements.txt      Python dependencies
```

## Deployment Notes

Recommended production setup:

1. Run behind Nginx or another reverse proxy.
2. Serve Flask with Gunicorn or another WSGI server.
3. Deploy the application into one fixed project directory, such as `/www/wwwroot/onlypt.rosebeg.com/current`.
4. Use Git in that fixed directory for code version control, updates, and rollbacks (`git pull`, `git reset`, or checked commits).
5. Keep `instance/` persistent and outside normal source commits. It can be a real directory or a symlink to a shared data directory.
6. If using a hosting panel such as BaoTa, point the panel project root directly at the fixed directory instead of a `current -> releases/...` symlink, so process status detection and start/stop actions match the real running service.
7. Set strong admin credentials through environment variables.
8. Configure SMTP in the admin panel.
9. Add a scheduled queue worker for `process_email_queue()`.
10. Back up `instance/` regularly.

The project no longer requires release-directory deployment. Git remains the source-code version control system; runtime data remains in `instance/`.

Do not commit:

- `instance/`
- `.env`
- virtual environments
- deployment archives or temporary server backups
- uploaded user assets

## Customization Guide

Most changes can be made without code:

- Brand name and subtitle: Admin -> General.
- Navigation and footer labels: Admin -> General.
- Page copy: Admin -> Home / Employers / Therapists / About / Contact.
- Background image: Admin -> General -> Background.
- Favicon: Admin -> General -> Page Tab.
- Contact notification email: Admin -> Email Notifications.

Code changes are only needed when:

- You need new page sections.
- You want different form fields.
- You need a different lead workflow.
- You want database-backed storage instead of CSV/JSON.
- You need to integrate a CRM or external automation platform.

## License / Ownership

This repository is source-available, not open source. Commercial use, resale, SaaS hosting, and closed-source derivatives require prior written permission from the repository owner.
