# Sales Rep Commission Report with AI

**Version**: 19.0.1.0.0 | **Author**: Abdalrahman Shahrour | **License**: LGPL-3

---

## Overview

This module provides a complete sales representative commission reporting system for Odoo 19, featuring:

- **Per-rep commission configuration** with flexible percentage rates
- **Web-based commission dashboard** accessible via HTTP (no PDF dependency)
- **Detailed per-rep web report** with order breakdown and totals
- **AI-powered performance insights** via OpenAI GPT-4o
- **Automated email notifications** with beautiful HTML reports sent to each sales rep
- **Wizard-based bulk email sending** from the Odoo backend

---

## Features

- Commission calculated from confirmed (`sale`, `done`) sale orders per month
- Real-time web report at `/sales/commission/report`
- Each rep can view their own report at `/sales/commission/report/my`
- AI insights generated on demand per rep (calls GPT-4o)
- Email template with full order table + AI insights
- Manager dashboard with summary stats and one-click email sending
- Multi-company support
- Cron-ready bulk email method

---

## Installation

1. Copy the `sale_rep_commission_report` folder to your Odoo addons directory
2. Restart Odoo
3. Go to **Apps** → update apps list
4. Search for **"Sales Rep Commission Report"** and click **Install**

---

## Configuration

### 1. Set your OpenAI API Key

Go to **Settings → General Settings → Sales Commission Report (AI)**

- Paste your OpenAI API key (get one at https://platform.openai.com/api-keys)
- Set your default commission rate
- Click **Save**

### 2. Configure Commission per Sales Rep

Go to **Sales → Commission → Commission Config**

- Click **New**
- Select the **Sales Representative** (internal user)
- Set their **Commission Rate (%)**
- Save

Repeat for each sales rep.

---

## How to Use

### View the Web Dashboard (Managers)

1. Go to **Sales → Commission → Web Report (Dashboard)**
2. A browser tab opens at `/sales/commission/report`
3. You see all reps, their order counts, total sales, and commission amounts for the current month
4. Click **View** to see a rep's detailed report with AI insights
5. Click **Email** to send the commission email to that rep
6. Click **Send All Emails** to email all reps at once

### View Your Own Report (Sales Reps)

Visit `/sales/commission/report/my` — you'll see your own commission report for the current month, including AI-generated insights about your performance.

### Send Commission Emails via Wizard

1. Go to **Sales → Commission → Send Commission Emails**
2. Choose to send to **All Active Reps** or select specific reps
3. Choose the **Commission Month**
4. Toggle **Include AI Insights** (recommended)
5. Click **Send Emails**

---

## Technical Notes

### Dependencies
- `sale` — Sale Orders
- `mail` — Email sending
- `base_setup` — Settings page integration

### Models Added
| Model | Description |
|---|---|
| `sale.commission.config` | Per-user commission rate configuration |
| `send.commission.email.wizard` | Transient wizard for bulk email sending |

### HTTP Routes
| Route | Auth | Description |
|---|---|---|
| `GET /sales/commission/report` | user (manager) | Dashboard — all reps |
| `GET /sales/commission/report/<id>` | user | Detail report for one rep |
| `GET /sales/commission/report/my` | user | Current user's own report |
| `POST /sales/commission/send-email/<id>` | user (manager) | Send email (JSON-RPC) |
| `POST /sales/commission/send-all-emails` | user (manager) | Send all emails (JSON-RPC) |

### AI Integration
- Uses OpenAI Chat Completions API (`gpt-4o`)
- API key stored in `ir.config_parameter` (key: `sale_rep_commission_report.openai_api_key`)
- Falls back gracefully if key is not configured or API times out
- Max 300 tokens per insight; temperature 0.7

### Cron Usage
Call `sale.commission.config.action_send_all_commissions_cron()` from an `ir.cron` record to automate monthly email dispatch.

---

## Changelog

| Version | Date | Description |
|---|---|---|
| 19.0.1.0.0 | 2025-03-11 | Initial release |

---

## Author

**Abdalrahman Shahrour** — Odoo Developer & Consultant
