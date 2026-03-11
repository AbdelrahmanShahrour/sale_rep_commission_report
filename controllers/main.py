import logging
from datetime import date

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class SaleRepCommissionController(http.Controller):
    """HTTP Controller for Sales Rep Commission Web Reports."""

    # ─── Report Routes ────────────────────────────────────────────────────────

    @http.route(
        '/sales/commission/report',
        auth='user',
        type='http',
        methods=['GET'],
        website=False,
    )
    def commission_report_index(self, **kwargs):
        """
        Dashboard listing all sales reps with their current month commission summary.
        Accessible by Sales Managers only.
        """
        env = request.env

        # Access check — only Sales Manager or Admin
        if not env.user.has_group('sales_team.group_sale_manager') \
                and not env.user.has_group('base.group_system'):
            return request.not_found()

        configs = env['sale.commission.config'].sudo().search([
            ('active', '=', True),
            ('company_id', '=', env.company.id),
        ])

        summaries = []
        for cfg in configs:
            data = cfg.get_commission_data()
            summaries.append(data)

        # Sort by commission amount desc
        summaries.sort(key=lambda x: x['commission_amount'], reverse=True)

        values = {
            'summaries': summaries,
            'month_label': date.today().strftime('%B %Y'),
            'company': env.company,
            'page_title': _('Sales Commission Report — %s') % date.today().strftime('%B %Y'),
        }
        return request.render(
            'sale_rep_commission_report.report_commission_index',
            values,
        )

    @http.route(
        '/sales/commission/report/<int:config_id>',
        auth='user',
        type='http',
        methods=['GET'],
        website=False,
    )
    def commission_report_detail(self, config_id, **kwargs):
        """
        Detailed commission report for a single sales representative.
        The rep can view their own report; managers can view any.
        """
        env = request.env

        config = env['sale.commission.config'].sudo().browse(config_id)
        if not config.exists():
            return request.not_found()

        is_manager = (
            env.user.has_group('sales_team.group_sale_manager')
            or env.user.has_group('base.group_system')
        )
        is_own = (config.user_id.id == env.user.id)

        if not is_manager and not is_own:
            return request.not_found()

        commission_data = config.get_commission_data()

        # Generate AI insights on demand
        include_ai = kwargs.get('ai', '1') == '1'
        ai_insights = ''
        if include_ai:
            ai_insights = config.generate_ai_insights(commission_data)

        commission_data['ai_insights'] = ai_insights
        commission_data['config_id'] = config_id
        commission_data['is_manager'] = is_manager
        commission_data['page_title'] = _(
            'Commission Report — %s — %s'
        ) % (commission_data['user_name'], commission_data['month_label'])

        return request.render(
            'sale_rep_commission_report.report_commission_detail',
            commission_data,
        )

    @http.route(
        '/sales/commission/report/my',
        auth='user',
        type='http',
        methods=['GET'],
        website=False,
    )
    def commission_report_my(self, **kwargs):
        """Redirect current user to their own commission report."""
        env = request.env

        config = env['sale.commission.config'].sudo().search([
            ('user_id', '=', env.user.id),
            ('company_id', '=', env.company.id),
            ('active', '=', True),
        ], limit=1)

        if not config:
            values = {
                'page_title': _('My Commission Report'),
                'message': _(
                    'No commission configuration found for your account. '
                    'Please contact your Sales Manager.'
                ),
            }
            return request.render(
                'sale_rep_commission_report.report_commission_no_config',
                values,
            )

        return request.redirect(
            f'/sales/commission/report/{config.id}'
        )

    # ─── AJAX / Action Routes ─────────────────────────────────────────────────

    @http.route(
        '/sales/commission/send-email/<int:config_id>',
        auth='user',
        type='json',
        methods=['POST'],
    )
    def send_commission_email_ajax(self, config_id, **kwargs):
        """
        Send commission email to a specific sales rep via AJAX.
        Returns JSON status.
        """
        env = request.env

        if not env.user.has_group('sales_team.group_sale_manager') \
                and not env.user.has_group('base.group_system'):
            return {'success': False, 'error': _('Access denied.')}

        config = env['sale.commission.config'].sudo().browse(config_id)
        if not config.exists():
            return {'success': False, 'error': _('Configuration not found.')}

        try:
            config._send_single_commission_email()
            return {
                'success': True,
                'message': _('Email sent to %s.') % config.user_id.name,
            }
        except Exception as e:
            _logger.error('Error sending commission email: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route(
        '/sales/commission/send-all-emails',
        auth='user',
        type='json',
        methods=['POST'],
    )
    def send_all_commission_emails_ajax(self, **kwargs):
        """Send commission emails to ALL active sales reps."""
        env = request.env

        if not env.user.has_group('sales_team.group_sale_manager') \
                and not env.user.has_group('base.group_system'):
            return {'success': False, 'error': _('Access denied.')}

        try:
            env['sale.commission.config'].sudo().action_send_all_commissions_cron()
            return {'success': True, 'message': _('All commission emails have been queued.')}
        except Exception as e:
            _logger.error('Error sending all commission emails: %s', str(e))
            return {'success': False, 'error': str(e)}
