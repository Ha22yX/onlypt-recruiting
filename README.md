# onlyPT Recruiting

Flask website for onlyPT Recruiting, a focused Physical Therapy recruiting site for healthcare employers and PT professionals.

[中文说明](README.zh-CN.md) | [Live example](https://onlypt.rosebeg.com/)

![onlyPT Recruiting homepage preview](static/img/readme-preview.png)

## Live Example

The project is deployed as an example site at [https://onlypt.rosebeg.com/](https://onlypt.rosebeg.com/). Use it to preview the public pages, responsive layout, and the recruiting-focused content experience.

## Features

- Responsive marketing pages for Home, Employers, Therapists, About, and Contact.
- Admin content editor for page copy and general site text.
- Single fixed site background image managed from the admin panel.
- Contact form submissions saved locally to `instance/leads.csv`.
- Uploads and runtime content stored in `instance/`, outside source control.

## Local Development

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Admin

Open `/admin/login`, sign in, then use `/admin/content/home`.

The background editor is under `General -> Background`. Uploading a new background image automatically replaces the previous one. The live site uses that one fixed image across every page.

## WhatsApp Lead Notifications

Contact form submissions are saved to `instance/leads.csv`. The app can also send a WhatsApp notification through Twilio when these environment variables are configured:

```text
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+15551234567
```

`TWILIO_WHATSAPP_FROM` must be a Twilio WhatsApp-enabled sender. For Sandbox testing, use Twilio's sandbox sender and make sure the receiving number has joined the sandbox.

## Project Layout

```text
app.py                 Flask routes, CMS helpers, upload handling
templates/            Public and admin templates
static/css/           Public and admin styles
static/js/            Public interactions and admin editor logic
instance/             Runtime data, uploads, content overrides, leads
```

## Deployment Notes

The production deployment keeps runtime data in a shared `instance/` directory and deploys source code as releases. Do not commit `instance/`, `.env`, virtual environments, or deployment archives.
