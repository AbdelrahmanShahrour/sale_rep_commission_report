{
    'name': 'Sales Rep Commission Report with AI',
    'version': '19.0.1.0.0',
    'summary': 'Sales rep commission reporting with AI insights and automated email notifications',
    'description': """
        This module provides:
        - Monthly commission calculation per sales representative
        - Web-based commission report via HTTP controller
        - AI-powered performance insights using OpenAI GPT
        - Automated email notifications to sales reps with commission details
        - Commission rate configuration per user
    """,
    'author': 'Abdalrahman Shahrour',
    'website': 'https://github.com/abdalrahmanshahrour',
    'category': 'Sales/Sales',
    'depends': [
        'sale',
        'mail',
        'base_setup',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/email_template.xml',
        'views/sale_commission_config_views.xml',
        'views/report_commission_web.xml',
        'views/wizard_send_email_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
