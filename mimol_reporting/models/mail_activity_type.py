# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models


class MailActivityType(models.Model):
    """Aktivite tipi = süreç sınıfı. Raporlama Merkezi aktiviteleri tipin
    "Raporlama Türü"ne göre Onay / Görev / Bilgi olarak ayırır; kod yok, ayar var.
    Odoo 17'nin standart "Keep Done" (keep_done) alanı tamamlanan aktivitelerin
    silinmek yerine arşivlenmesini sağlar; geçmiş raporları ona dayanır."""
    _inherit = 'mail.activity.type'

    reporting_kind = fields.Selection(
        [('approval', 'Onay'), ('task', 'Görev'), ('info', 'Bilgi')],
        string='Raporlama Türü', default='task', required=True,
        help='Raporlama Merkezinde bu tipteki aktiviteler hangi bölümde görünür: '
             'Onay (Onaylarım), Görev (Görevlerim) ya da Bilgi (yalnız bilgilendirme).',
    )
    reporting_exclude = fields.Boolean(
        string='Raporlama Merkezinde Gizle', default=False,
        help='İşaretliyse bu tipteki aktiviteler Raporlama Merkezi listelerinde ve '
             'raporlarında gösterilmez (örn. otomatik vade hatırlatmaları).',
    )

    # Yeni kurulan modüllerin onay tipleri elle ayar gerektirmesin (kurulum kancasıyla aynı kural)
    APPROVAL_NAME_RX = re.compile(r'onay|approv', re.IGNORECASE)

    @api.model_create_multi
    def create(self, vals_list):
        # Ayar açıksa yeni tipler de geçmişi saklar; adı onay/approval içerenler "Onay" türü olur
        keep = self.env['ir.config_parameter'].sudo().get_param(
            'mimol_reporting.keep_done_default', 'True') == 'True'
        for vals in vals_list:
            if keep and 'keep_done' not in vals:
                vals['keep_done'] = True
            name = vals.get('name')
            if 'reporting_kind' not in vals and isinstance(name, str) \
                    and self.APPROVAL_NAME_RX.search(name.replace('İ', 'i')):
                vals['reporting_kind'] = 'approval'
        return super().create(vals_list)

    def action_reporting_keep_done_all(self):
        """Ayarlar butonu: tüm tiplerde geçmişi sakla."""
        self.with_context(active_test=False).search([]).write({'keep_done': True})
        return True
