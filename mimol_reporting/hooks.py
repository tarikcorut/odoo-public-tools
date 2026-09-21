# -*- coding: utf-8 -*-
import re

from odoo import SUPERUSER_ID, api


def post_init_hook(env_or_cr, registry=None):
    """Kurulumda:
    - tüm aktivite tiplerinde geçmişi sakla (Odoo 17 keep_done),
    - adı onay/approval içeren tipleri "Onay" türü olarak işaretle (ayardan değiştirilebilir),
    - sistemdeki mevcut panoları kayıt defterine tara."""
    env = env_or_cr if isinstance(env_or_cr, api.Environment) else api.Environment(env_or_cr, SUPERUSER_ID, {})
    types = env['mail.activity.type'].with_context(active_test=False).search([])
    types.write({'keep_done': True})
    approval_rx = re.compile(r'onay|approv', re.IGNORECASE)
    approvals = types.filtered(lambda t: approval_rx.search((t.name or '').replace('İ', 'i')))
    if approvals:
        approvals.write({'reporting_kind': 'approval'})
    env['reporting.dashboard'].action_scan_menus()
