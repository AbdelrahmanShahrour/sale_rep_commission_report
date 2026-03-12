# Sales Rep Commission Report with AI

**Version:** 19.0.1.0.0
**Author:** Abdalrahman Shahrour
**License:** LGPL-3
**Category:** Sales / Sales
**Odoo Version:** 19.0

---

## Overview

This module adds a full commission management workflow to Odoo Sales. It calculates monthly commissions per sales representative, displays them in a live web dashboard, generates AI-powered performance insights via the Hugging Face Router API, and delivers personalised commission summaries by email — automatically or on demand.

---

## Features

| Feature | Description |
|---|---|
| **Commission configuration** | Set a commission rate (%) per sales representative and company |
| **Automatic calculation** | Pulls confirmed sale orders for the current month and computes totals |
| **Web dashboard** | Live report at `/sales/commission/report` — managers see all reps; reps see their own |
| **AI insights** | Generates a personalised coaching paragraph using Hugging Face chat models |
| **Email reports** | Send individual or bulk commission emails from the backend or from the web report |
| **Wizard** | Batch-send emails with a configurable target month, AI toggle, and per-rep selection |
| **Chatter** | Full message thread and activity support on every commission config record |
| **Cron-ready** | `action_send_all_commissions_cron()` can be wired to a scheduled action |
| **Multi-company** | Commission configs are scoped to a company; the dashboard filters by the active company |
| **Security** | Managers have full access; internal users can only read their own config |

---

## Dependencies

- `sale` — sale orders and sales team groups
- `mail` — chatter, email templates, and `mail.mail`
- `base_setup` — General Settings page integration

---

## Installation

1. Copy the `sale_rep_commission_report` folder into your Odoo addons path.
2. Restart the Odoo server.
3. Go to **Settings → Apps**, click **Update Apps List**.
4. Search for **Sales Rep Commission Report with AI** and click **Install**.

---

## Configuration

### Step 1 — Hugging Face API Token

The AI insights feature requires a Hugging Face account with an API token that has the **Inference Providers** permission.

1. Go to **Settings → General Settings**.
2. Scroll to the **Sales Commission Report (AI)** section.
3. Paste your token into **Hugging Face API Token**.
4. Optionally update the **Hugging Face Model** field (default: `Qwen/Qwen2.5-7B-Instruct`).
5. Click **Save**.

> **Getting a token**
> Log in at [huggingface.co](https://huggingface.co), open **Settings → Access Tokens**, create a new token, and enable the **Inference Providers** scope.

### Step 2 — Default Commission Rate

In the same settings section, set a **Default Commission Rate (%)** that will be pre-filled when creating new commission configurations (factory default: 5 %).

### Step 3 — Commission Configurations

A commission record must exist for each sales representative before any report or email can be generated.

1. Go to **Sales → Commission → Commission Config**.
2. Click **New**.
3. **Sales Representative** — select an internal Odoo user.
4. **Commission Rate (%)** — enter the percentage to apply to confirmed order totals.
5. **Company** — defaults to the current company (visible in multi-company mode).
6. **Active** — leave checked.
7. Add optional **Notes** for context.
8. Click **Save**.

> One configuration per user per company is enforced. Attempting to create a duplicate returns a validation error.

---

## Usage

### Commission Config List

**Sales → Commission → Commission Config**

Displays all configured representatives. From here you can:

- Create, edit, or archive configurations.
- Click the **envelope icon** on any row to immediately send that rep's current-month commission email.

---

### Web Report — Manager Dashboard

**Sales → Commission → Web Report (Dashboard)**
Direct URL: `http://<your-odoo>/sales/commission/report`

Accessible only to **Sales Managers** and **Administrators**.

The page shows:

- **Summary stats** — total reps, total revenue, total commissions, total orders for the current month.
- **Representatives table** — one row per rep with order count, total sales, commission rate, and commission amount.
  - **View** — opens the rep's full detail report.
  - **Email** — sends that rep's commission email immediately via AJAX (no page reload).
- **Send All Emails** button — dispatches emails to every active rep in a single click.

---

### Web Report — Detail Page (Per Rep)

**URL:** `/sales/commission/report/<config_id>`
**My report:** `/sales/commission/report/my`

Any logged-in internal user can access their own report. Managers can access any rep's report.

The detail page shows:

| Section | Content |
|---|---|
| **Stats row** | Confirmed orders, total sales, commission rate, commission earned |
| **AI Performance Insights** | Coaching paragraph from the Hugging Face model (hidden if no token is configured) |
| **Orders table** | Every confirmed sale order for the month with amount and per-order commission |
| **Send Email to Rep** button | Managers only — sends the commission email immediately |

> AI insights are generated live on each page load. If the API token is missing or the model fails, a plain-text fallback message is shown; the rest of the page still loads normally.

---

### My Report (Sales Reps)

Reps do not need access to the manager dashboard. They can navigate directly to:

```
/sales/commission/report/my
```

This redirects to their own detail report. If no commission config exists for their account they see a friendly message instructing them to contact their Sales Manager.

The **My Report** link is also available in the navbar on every report page.

---

### Send Commission Emails Wizard

**Sales → Commission → Send Commission Emails**

A dialog for controlled bulk sending:

| Field | Description |
|---|---|
| **Send To** | *All Active Sales Representatives* or *Selected Representatives* |
| **Sales Representatives** | Multi-select (visible only when *Selected* is chosen) |
| **Commission Month** | Any past or current month — defaults to today |
| **Include AI Insights** | Toggle AI paragraph generation per email (default: on) |
| **Preview** | Live summary of how many emails will be sent |

Click **Send Emails**. A notification reports how many succeeded and lists any that failed by name.

---

### Automated Monthly Emails (Cron)

To send commission emails automatically at month-end:

1. Enable **developer mode** (Settings → General Settings → Developer Tools → Activate).
2. Go to **Settings → Technical → Automation → Scheduled Actions**.
3. Click **New** and fill in:
   - **Name:** `Send Monthly Commission Emails`
   - **Model:** `sale.commission.config`
   - **Execute Every:** 1 month (set to run on the last day of each month)
   - **Action:** Execute Python Code
     ```python
     model.action_send_all_commissions_cron()
     ```
4. Save and enable the scheduled action.

---

## Email Template

The module ships a QWeb template (`commission_email_body`) with inline styles for broad email-client compatibility. Each email contains:

1. A gradient header banner with the report month.
2. A personalised greeting using the rep's name.
3. Three stat boxes — orders, total sales, commission earned.
4. An AI insights paragraph (only when available).
5. A full order breakdown table.
6. A footer with the company name.

---

## Security

| Role | Access |
|---|---|
| **Sales Manager** (`sales_team.group_sale_manager`) | Full CRUD on commission configs and wizard; access to all web routes and email actions |
| **Internal User** (`base.group_user`) | Read-only on their own commission config; can view `/sales/commission/report/my` |
| **Other / portal / public** | No access — web routes return 404 |

Record-level rules prevent internal users from browsing other reps' config records. Managers see all records scoped to their company.

---

## Technical Reference

### Models

#### `sale.commission.config`

| Field | Type | Description |
|---|---|---|
| `user_id` | Many2one (`res.users`) | The sales representative |
| `commission_rate` | Float | Percentage applied to confirmed order totals (0–100) |
| `company_id` | Many2one (`res.company`) | Scoping company |
| `currency_id` | Many2one (related) | Derived from the company |
| `active` | Boolean | Archive / restore |
| `notes` | Text | Free-form notes |

Key methods:

| Method | Description |
|---|---|
| `get_commission_data(target_date)` | Returns a dict with orders, totals, and metadata for the given month |
| `generate_ai_insights(commission_data)` | Calls the Hugging Face Router API; returns plain-text insight or a fallback string |
| `action_send_commission_email()` | Button action — sends email to this rep and shows a success notification |
| `_send_single_commission_email(target_date)` | Core send logic; falls back to `mail.mail` if the email template is missing |
| `action_send_all_commissions_cron()` | `@api.model` — sends to all active reps; suitable for `ir.cron` |

#### `res.config.settings` (inherited)

| Field | `ir.config_parameter` key |
|---|---|
| `huggingface_api_key` | `sale_rep_commission_report.huggingface_api_key` |
| `huggingface_model` | `sale_rep_commission_report.huggingface_model` |
| `commission_default_rate` | `sale_rep_commission_report.default_commission_rate` |

#### `send.commission.email.wizard` (transient)

Wizard for the bulk-send dialog. Supports sending to all active configs or a selected subset, with a configurable target month and AI toggle.

### HTTP Controller

| Route | Method | Auth required | Description |
|---|---|---|---|
| `/sales/commission/report` | GET | Sales Manager | All-reps dashboard |
| `/sales/commission/report/<id>` | GET | Own rep or manager | Detail page |
| `/sales/commission/report/my` | GET | Any internal user | Redirects to own detail page |
| `/sales/commission/send-email/<id>` | POST (JSON) | Sales Manager | AJAX — send one email |
| `/sales/commission/send-all-emails` | POST (JSON) | Sales Manager | AJAX — send all emails |

### QWeb Templates

| Template ID | Description |
|---|---|
| `commission_layout` | Shared Bootstrap 5 navbar and page wrapper |
| `report_commission_index` | All-reps dashboard |
| `report_commission_detail` | Single-rep detail page |
| `report_commission_no_config` | Shown when a rep has no config record |
| `commission_email_body` | HTML email body (inline styles, email-client safe) |

---

## Changelog

### 19.0.1.0.0
- Initial release for Odoo 19.
- Commission config model with chatter and multi-company support.
- Web dashboard and per-rep detail report.
- AI insights via Hugging Face Router API (chat completions, fallback model support).
- Bulk-send wizard with target-month and AI-toggle options.
- Automated cron support via `action_send_all_commissions_cron`.
- Settings page using the Odoo 19 `<app>` / `<block>` / `<setting>` structure.

---

## Author

**Abdalrahman Shahrour** — Odoo Developer & Consultant
[github.com/abdalrahmanshahrour](https://github.com/abdalrahmanshahrour)
