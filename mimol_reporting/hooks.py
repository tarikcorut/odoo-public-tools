# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def post_init_hook(env_or_cr, registry=None):
    """Kurulumda: tüm aktivite tiplerinde geçmişi sakla (Odoo 17 keep_done) ve
    sistemdeki mevcut panoları kayıt defterine tara."""
    env = env_or_cr if isinstance(env_or_cr, api.Environment) else api.Environment(env_or_cr, SUPERUSER_ID, {})
    env['mail.activity.type'].with_context(active_test=False).search([]).write({'keep_done': True})
    env['reporting.dashboard'].action_scan_menus()
