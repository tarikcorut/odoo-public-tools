# -*- coding: utf-8 -*-
"""Yükseltme: tüm aktivite tiplerinde geçmişi sakla; adı onay/approval içeren
tipleri "Onay" türü olarak işaretle (kurulum kancası yalnız ilk kurulumda çalışır)."""
import re

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    types = env['mail.activity.type'].with_context(active_test=False).search([])
    types.write({'keep_done': True})
    rx = re.compile(r'onay|approv', re.IGNORECASE)
    approvals = types.filtered(lambda t: rx.search((t.name or '').replace('İ', 'i')))
    if approvals:
        approvals.write({'reporting_kind': 'approval'})
