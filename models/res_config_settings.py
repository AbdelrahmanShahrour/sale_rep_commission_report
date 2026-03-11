from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    openai_api_key = fields.Char(
        string='OpenAI API Key',
        config_parameter='sale_rep_commission_report.openai_api_key',
        help='API key for OpenAI GPT used to generate commission AI insights.',
    )
    commission_default_rate = fields.Float(
        string='Default Commission Rate (%)',
        config_parameter='sale_rep_commission_report.default_commission_rate',
        default=5.0,
        help='Default commission percentage applied to new sales rep configurations.',
    )
