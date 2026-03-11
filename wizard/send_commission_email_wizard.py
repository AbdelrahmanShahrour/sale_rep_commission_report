from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SendCommissionEmailWizard(models.TransientModel):
    """Wizard to send commission emails to selected or all sales reps."""

    _name = 'send.commission.email.wizard'
    _description = 'Send Commission Email Wizard'

    send_to = fields.Selection(
        selection=[
            ('all', 'All Active Sales Representatives'),
            ('selected', 'Selected Representatives'),
        ],
        string='Send To',
        default='all',
        required=True,
    )
    config_ids = fields.Many2many(
        comodel_name='sale.commission.config',
        string='Sales Representatives',
        domain=[('active', '=', True)],
    )
    include_ai_insights = fields.Boolean(
        string='Include AI Insights',
        default=True,
        help='Generate and include AI-powered performance insights in each email.',
    )
    target_month = fields.Date(
        string='Commission Month',
        default=fields.Date.today,
        required=True,
        help='Report will be generated for the month of the selected date.',
    )
    preview_text = fields.Text(
        string='Preview',
        readonly=True,
        compute='_compute_preview_text',
    )

    @api.depends('send_to', 'config_ids')
    def _compute_preview_text(self):
        for rec in self:
            if rec.send_to == 'all':
                count = self.env['sale.commission.config'].search_count([('active', '=', True)])
                rec.preview_text = _('Will send emails to %d sales representative(s).') % count
            else:
                rec.preview_text = _(
                    'Will send emails to %d selected representative(s).'
                ) % len(rec.config_ids)

    def action_send(self):
        """Execute the email sending process."""
        self.ensure_one()

        if self.send_to == 'all':
            configs = self.env['sale.commission.config'].search([('active', '=', True)])
        else:
            if not self.config_ids:
                raise UserError(_('Please select at least one sales representative.'))
            configs = self.config_ids

        target_date = self.target_month
        success = 0
        failed = 0
        failed_names = []

        for config in configs:
            try:
                config._send_single_commission_email(target_date=target_date)
                success += 1
            except Exception as e:
                failed += 1
                failed_names.append(config.user_id.name)

        msg = _('%d email(s) sent successfully.') % success
        if failed:
            msg += _(' %d failed: %s') % (failed, ', '.join(failed_names))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Commission Emails Sent'),
                'message': msg,
                'type': 'success' if not failed else 'warning',
                'sticky': True,
            },
        }
