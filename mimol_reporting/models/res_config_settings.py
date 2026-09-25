# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    reporting_warning_days = fields.Integer(
        string='Uyarı Eşiği (gün)', config_parameter='mimol_reporting.warning_days', default=3,
        help='Bu kadar gündür bekleyen açık iş "uyarı" sayılır.',
    )
    reporting_critical_days = fields.Integer(
        string='Kritik Eşik (gün)', config_parameter='mimol_reporting.critical_days', default=7,
        help='Bu kadar gündür bekleyen açık iş "kritik" sayılır.',
    )
    reporting_keep_done_default = fields.Boolean(
        string='Yeni aktivite tipleri geçmişi saklasın', config_parameter='mimol_reporting.keep_done_default',
        default=True,
    )
    # İlişki tablosu açıkça adlandırılır: `res.config.settings` üzerinde
    # `ir.model`'e bakan başka bir Many2many daha var (attachment_google_drive)
    # ve adı verilmeyen iki alan aynı tabloyu türetip kurulumu düşürüyor.
    reporting_excluded_model_ids = fields.Many2many(
        'ir.model', relation='res_config_settings_reporting_excl_model_rel',
        column1='config_id', column2='model_id',
        string='Merkezde gizlenecek modeller',
        help='Bu modellerin aktiviteleri Raporlama Merkezinde gösterilmez (örn. otomatik çek vade hatırlatmaları).',
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        param = self.env['ir.config_parameter'].sudo().get_param('mimol_reporting.excluded_models', '')
        names = [m.strip() for m in param.split(',') if m.strip()]
        models_ = self.env['ir.model'].sudo().search([('model', 'in', names)]) if names else self.env['ir.model']
        res['reporting_excluded_model_ids'] = [(6, 0, models_.ids)]
        return res

    def set_values(self):
        super().set_values()
        names = ','.join(self.reporting_excluded_model_ids.mapped('model'))
        self.env['ir.config_parameter'].sudo().set_param('mimol_reporting.excluded_models', names)

    def action_reporting_keep_done_all(self):
        return self.env['mail.activity.type'].action_reporting_keep_done_all()

    def action_reporting_scan_dashboards(self):
        return self.env['reporting.dashboard'].action_scan_menus()
