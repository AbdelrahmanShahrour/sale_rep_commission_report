import logging
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
            'config_id': self.id,
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

    def _get_huggingface_api_token(self):
        """Retrieve Hugging Face API token from system parameters."""
        token = self.env['ir.config_parameter'].sudo().get_param(
            'sale_rep_commission_report.huggingface_api_key'
        )
        if not token:
            raise UserError(_(
                'Hugging Face API token is not configured. '
                'Go to Sales > Configuration > Commission Settings to set it.'
            ))
        return token

    def _get_huggingface_model(self):
        """Retrieve Hugging Face chat model repo ID from system parameters."""
        return (
            self.env['ir.config_parameter'].sudo().get_param(
                'sale_rep_commission_report.huggingface_model'
            ) or 'Qwen/Qwen2.5-7B-Instruct'
        )

    @staticmethod
    def _extract_huggingface_text(payload):
        """Extract generated text from Hugging Face response payload."""
        # OpenAI-compatible chat completions payload.
        if isinstance(payload, dict):
            choices = payload.get('choices')
            if isinstance(choices, list) and choices:
                first_choice = choices[0] if isinstance(choices[0], dict) else {}
                message = first_choice.get('message') if isinstance(first_choice, dict) else {}
                if isinstance(message, dict):
                    content = message.get('content')
                    if isinstance(content, str) and content.strip():
                        return content.strip()
                    if isinstance(content, list):
                        content_parts = []
                        for part in content:
                            if isinstance(part, dict) and isinstance(part.get('text'), str):
                                content_parts.append(part['text'])
                        if content_parts:
                            return ''.join(content_parts).strip()

        # Legacy text-generation payload shapes.
        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, dict):
                return (
                    first.get('generated_text')
                    or first.get('summary_text')
                    or first.get('text')
                    or ''
                ).strip()
            if isinstance(first, str):
                return first.strip()
        if isinstance(payload, dict):
            return (
                payload.get('generated_text')
                or payload.get('summary_text')
                or payload.get('text')
                or ''
            ).strip()
        return ''

    def _request_huggingface_chat_completion(self, api_token, model, prompt):
        """Call Hugging Face Router chat completions API and return JSON payload."""
        response = requests.post(
            'https://router.huggingface.co/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_token}',
                'Content-Type': 'application/json',
            },
            json={
                'model': model,
                'messages': [
                    {'role': 'user', 'content': prompt},
                ],
                'max_tokens': 220,
                'temperature': 0.7,
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def generate_ai_insights(self, commission_data):
        """
        Call Hugging Face Router API to generate a personalized
        performance insight message
        for the sales representative.

        :param commission_data: dict returned by get_commission_data()
        :return: str — AI-generated insights paragraph
        """
        self.ensure_one()

        try:
            api_token = self._get_huggingface_api_token()
        except UserError as e:
            _logger.warning('AI insights skipped: %s', str(e))
            return _('AI insights not available — API key not configured.')

        prompt = self._build_ai_prompt(commission_data)
        model = self._get_huggingface_model()
        full_prompt = (
            'You are a professional sales performance coach. '
            'Write concise, motivating, and constructive commission '
            'performance summaries for sales representatives. '
            'Keep the tone positive and actionable. '
            'Maximum 150 words.\n\n'
            f'{prompt}'
        )
        fallback_model = 'Qwen/Qwen2.5-7B-Instruct'

        try:
            data = self._request_huggingface_chat_completion(api_token, model, full_prompt)

            text = self._extract_huggingface_text(data)
            if not text and model != fallback_model:
                _logger.warning(
                    'Hugging Face model %s returned empty assistant content. '
                    'Retrying with fallback model %s.',
                    model,
                    fallback_model,
                )
                data = self._request_huggingface_chat_completion(
                    api_token,
                    fallback_model,
                    full_prompt,
                )
                text = self._extract_huggingface_text(data)

            if not text:
                if isinstance(data, dict) and data.get('error'):
                    raise KeyError(data['error'])
                return _(
                    'AI insights could not be generated: selected model did not return final '
                    'assistant text. Try Qwen/Qwen2.5-7B-Instruct or openai/gpt-oss-20b.'
                )
            return text.strip()

        except requests.exceptions.HTTPError as e:
            response = e.response
            status_code = response.status_code if response is not None else None
            error_message = ''
            try:
                payload = response.json() if response is not None else {}
                if isinstance(payload, dict):
                    error_message = payload.get('error') or payload.get('message') or ''
            except ValueError:
                pass

            _logger.error(
                'Hugging Face API HTTP error %s for user %s: %s',
                status_code,
                self.user_id.name,
                error_message or 'HTTP error from Hugging Face API',
            )

            if status_code == 429:
                return _('AI insights could not be generated: Hugging Face rate limit exceeded.')
            if status_code in (401, 403):
                if 'inference providers' in error_message.lower() or 'sufficient permissions' in error_message.lower():
                    return _(
                        'AI insights could not be generated: Hugging Face token is missing '
                        'Inference Providers permission. Update token scopes in '
                        'huggingface.co/settings/tokens.'
                    )
                return _(
                    'AI insights could not be generated: invalid or unauthorized Hugging Face API token.'
                )
            if status_code == 404:
                return _(
                    'AI insights could not be generated: configured Hugging Face model was not found.'
                )
            if status_code == 400 and 'not a chat model' in error_message.lower():
                return _(
                    'AI insights could not be generated: selected model is not compatible with '
                    'chat completions. Please choose a chat model '
                    '(for example Qwen/Qwen2.5-7B-Instruct).'
                )
            if status_code == 503:
                return _(
                    'AI insights could not be generated: selected Hugging Face model is loading. '
                    'Please retry in a moment.'
                )
            if error_message:
                return _('AI insights could not be generated: %s') % error_message.split('\n')[0]
            return _('AI insights could not be generated (Hugging Face API error).')
        except requests.exceptions.Timeout:
            _logger.error('Hugging Face API timeout for user %s', self.user_id.name)
            return _('AI insights could not be generated (request timeout).')
        except requests.exceptions.RequestException as e:
            _logger.error('Hugging Face API error: %s', str(e))
            return _('AI insights could not be generated (network or Hugging Face API unreachable).')
        except (KeyError, IndexError, TypeError, ValueError) as e:
            _logger.error('Unexpected Hugging Face response format: %s', str(e))
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
