import logging
import json
from datetime import date
from dateutil.relativedelta import relativedelta

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleCommissionConfig(models.Model):
    """Commission rate configuration per sales representative."""

    _name = 'sale.commission.config'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Sales Representative Commission Configuration'
    _rec_name = 'user_id'
    _order = 'user_id asc'

    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Sales Representative',
        required=True,
        index=True,
        domain=[('share', '=', False)],
    )
    commission_rate = fields.Float(
        string='Commission Rate (%)',
        required=True,
        default=5.0,
        help='Percentage of confirmed sale order totals paid as commission.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Currency',
        readonly=True,
    )
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        (
            'unique_user_company',
            'UNIQUE(user_id, company_id)',
            'A commission configuration already exists for this user in this company.',
        ),
        (
            'positive_rate',
            'CHECK(commission_rate >= 0 AND commission_rate <= 100)',
            'Commission rate must be between 0 and 100.',
        ),
    ]

    # ─── Commission Calculation ───────────────────────────────────────────────

    def _get_month_domain(self, target_date=None):
        """Return date domain for the current (or given) month."""
        if not target_date:
            target_date = date.today()
        month_start = target_date.replace(day=1)
        month_end = (month_start + relativedelta(months=1)) - relativedelta(days=1)
        return month_start, month_end

    def get_commission_data(self, target_date=None):
        """
        Compute commission data for this config's user for a given month.

        Returns a dict with:
          - user_id, user_name, email
          - commission_rate
          - orders: list of order dicts
          - total_sales, commission_amount
          - month_label
          - currency_symbol
        """
        self.ensure_one()
        month_start, month_end = self._get_month_domain(target_date)

        orders = self.env['sale.order'].search([
            ('user_id', '=', self.user_id.id),
            ('state', 'in', ['sale', 'done']),
            ('date_order', '>=', fields.Datetime.to_datetime(month_start)),
            ('date_order', '<=', fields.Datetime.to_datetime(
                month_end.strftime('%Y-%m-%d') + ' 23:59:59'
            )),
            ('company_id', '=', self.company_id.id),
        ])

        order_list = []
        for order in orders:
            order_list.append({
                'name': order.name,
                'partner': order.partner_id.name,
                'date': order.date_order.strftime('%Y-%m-%d'),
                'amount': order.amount_total,
                'state': order.state,
            })

        total_sales = sum(o['amount'] for o in order_list)
        commission_amount = total_sales * (self.commission_rate / 100.0)

        return {
            'user_id': self.user_id.id,
            'user_name': self.user_id.name,
            'email': self.user_id.email or self.user_id.partner_id.email or '',
            'commission_rate': self.commission_rate,
            'orders': order_list,
            'order_count': len(order_list),
            'total_sales': total_sales,
            'commission_amount': commission_amount,
            'month_label': month_start.strftime('%B %Y'),
            'currency_symbol': self.currency_id.symbol or '$',
            'company_name': self.company_id.name,
        }

    # ─── AI Insights ─────────────────────────────────────────────────────────

    def _get_openai_api_key(self):
        """Retrieve OpenAI API key from system parameters."""
        key = self.env['ir.config_parameter'].sudo().get_param(
            'sale_rep_commission_report.openai_api_key'
        )
        if not key:
            raise UserError(_(
                'OpenAI API key is not configured. '
                'Go to Sales > Configuration > Commission Settings to set it.'
            ))
        return key

    def generate_ai_insights(self, commission_data):
        """
        Call OpenAI GPT to generate a personalized performance insight message
        for the sales representative.

        :param commission_data: dict returned by get_commission_data()
        :return: str — AI-generated insights paragraph
        """
        self.ensure_one()

        try:
            api_key = self._get_openai_api_key()
        except UserError as e:
            _logger.warning('AI insights skipped: %s', str(e))
            return _('AI insights not available — API key not configured.')

        prompt = self._build_ai_prompt(commission_data)

        try:
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': 'gpt-4o',
                    'messages': [
                        {
                            'role': 'system',
                            'content': (
                                'You are a professional sales performance coach. '
                                'Write concise, motivating, and constructive commission '
                                'performance summaries for sales representatives. '
                                'Keep the tone positive and actionable. '
                                'Maximum 150 words.'
                            ),
                        },
                        {'role': 'user', 'content': prompt},
                    ],
                    'max_tokens': 300,
                    'temperature': 0.7,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content'].strip()

        except requests.exceptions.Timeout:
            _logger.error('OpenAI API timeout for user %s', self.user_id.name)
            return _('AI insights could not be generated (request timeout).')
        except requests.exceptions.RequestException as e:
            _logger.error('OpenAI API error: %s', str(e))
            return _('AI insights could not be generated.')
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            _logger.error('Unexpected OpenAI response format: %s', str(e))
            return _('AI insights could not be generated (unexpected response).')

    def _build_ai_prompt(self, data):
        """Build the prompt string for the AI model."""
        order_summary = ''
        if data['orders']:
            top_orders = sorted(data['orders'], key=lambda x: x['amount'], reverse=True)[:5]
            order_summary = '\n'.join(
                f"  - {o['name']} ({o['partner']}): {data['currency_symbol']}"
                f"{o['amount']:,.2f} on {o['date']}"
                for o in top_orders
            )
        else:
            order_summary = '  No orders confirmed this month.'

        return (
            f"Sales Representative: {data['user_name']}\n"
            f"Month: {data['month_label']}\n"
            f"Company: {data['company_name']}\n"
            f"Total Confirmed Orders: {data['order_count']}\n"
            f"Total Sales Amount: {data['currency_symbol']}{data['total_sales']:,.2f}\n"
            f"Commission Rate: {data['commission_rate']}%\n"
            f"Commission Earned: {data['currency_symbol']}{data['commission_amount']:,.2f}\n"
            f"Top Orders This Month:\n{order_summary}\n\n"
            "Please write a personalized performance summary and motivational message "
            "for this sales representative about their commission results this month. "
            "Include one concrete tip for next month."
        )

    # ─── Email Actions ────────────────────────────────────────────────────────

    def action_send_commission_email(self):
        """Send commission email to this sales rep (single record)."""
        self.ensure_one()
        self._send_single_commission_email()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Email Sent'),
                'message': _('Commission email sent to %s.') % self.user_id.name,
                'type': 'success',
                'sticky': False,
            },
        }

    def _send_single_commission_email(self, target_date=None):
        """Core email sending logic for one commission config record."""
        self.ensure_one()

        commission_data = self.get_commission_data(target_date)
        ai_insights = self.generate_ai_insights(commission_data)
        commission_data['ai_insights'] = ai_insights

        template = self.env.ref(
            'sale_rep_commission_report.email_template_commission_report',
            raise_if_not_found=False,
        )

        email_to = commission_data['email']
        if not email_to:
            _logger.warning(
                'No email address for sales rep %s — skipping.',
                self.user_id.name,
            )
            return False

        if template:
            template.with_context(commission_data=commission_data).send_mail(
                self.id,
                force_send=True,
                email_values={
                    'email_to': email_to,
                    'subject': _(
                        'Your Commission Report — %s'
                    ) % commission_data['month_label'],
                },
            )
        else:
            # Fallback: compose mail directly
            body = self.env['ir.qweb']._render(
                'sale_rep_commission_report.commission_email_body',
                commission_data,
            )
            mail = self.env['mail.mail'].create({
                'subject': _('Your Commission Report — %s') % commission_data['month_label'],
                'email_to': email_to,
                'body_html': body,
                'auto_delete': True,
            })
            mail.send()

        _logger.info(
            'Commission email sent to %s (%s) for %s',
            self.user_id.name,
            email_to,
            commission_data['month_label'],
        )
        return True

    @api.model
    def action_send_all_commissions_cron(self):
        """Cron-callable: send commission emails to ALL active reps."""
        configs = self.search([('active', '=', True)])
        success_count = 0
        for config in configs:
            try:
                sent = config._send_single_commission_email()
                if sent:
                    success_count += 1
            except Exception as e:
                _logger.error(
                    'Failed to send commission email for %s: %s',
                    config.user_id.name, str(e),
                )
        _logger.info('Commission emails sent: %d / %d', success_count, len(configs))
