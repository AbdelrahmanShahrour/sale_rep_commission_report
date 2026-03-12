from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    huggingface_api_key = fields.Char(
        string='Hugging Face API Token',
        config_parameter='sale_rep_commission_report.huggingface_api_key',
        help='API token for Hugging Face Inference API used to generate commission AI insights.',
    )
    huggingface_model = fields.Char(
        string='Hugging Face Model',
        config_parameter='sale_rep_commission_report.huggingface_model',
        default='Qwen/Qwen2.5-7B-Instruct',
        help='Chat model repo ID used by the Hugging Face Router API.',
    )
    commission_default_rate = fields.Float(
        string='Default Commission Rate (%)',
        config_parameter='sale_rep_commission_report.default_commission_rate',
        default=5.0,
        help='Default commission percentage applied to new sales rep configurations.',
    )
