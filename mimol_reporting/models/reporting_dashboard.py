# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class ReportingDashboardCategory(models.Model):
    _name = 'reporting.dashboard.category'
    _description = 'Pano Kategorisi'
    _order = 'sequence, id'

    name = fields.Char(string='Kategori', required=True, translate=True)
    sequence = fields.Integer(default=10)
    dashboard_ids = fields.One2many('reporting.dashboard', 'category_id', string='Panolar')
    dashboard_count = fields.Integer(compute='_compute_dashboard_count')
    menu_id = fields.Many2one('ir.ui.menu', string='Üretilen Menü', readonly=True, copy=False, ondelete='set null')

    @api.depends('dashboard_ids')
    def _compute_dashboard_count(self):
        for rec in self:
            rec.dashboard_count = len(rec.dashboard_ids)

    def _ensure_menu(self):
        """Raporlama Merkezi / Panolar altında kategori menüsü."""
        parent = self.env.ref('mimol_reporting.menu_reporting_dashboards', raise_if_not_found=False)
        Menu = self.env['ir.ui.menu'].sudo()
        for rec in self:
            if not parent:
                continue
            if rec.menu_id and rec.menu_id.exists():
                if rec.menu_id.name != rec.name or rec.menu_id.sequence != rec.sequence:
                    rec.menu_id.write({'name': rec.name, 'sequence': rec.sequence})
                continue
            rec.menu_id = Menu.create({
                'name': rec.name, 'parent_id': parent.id, 'sequence': rec.sequence,
            })

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._ensure_menu()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if 'name' in vals or 'sequence' in vals:
            self._ensure_menu()
        return res

    def unlink(self):
        menus = self.mapped('menu_id')
        res = super().unlink()
        menus.sudo().unlink()
        return res


class ReportingDashboard(models.Model):
    """Pano kayıt defteri: sistemdeki mevcut bir panonun (menü + aksiyon)
    Raporlama Merkezinde görünmesi için kayıt. Görünürlük panonun KENDİ
    menüsünün görünürlüğüdür: kullanıcı o menüyü modülünde görebiliyorsa
    burada da görür, göremiyorsa görmez. Yetki kopyalanmaz, kod yazılmaz."""
    _name = 'reporting.dashboard'
    _description = 'Pano Kaydı'
    _order = 'category_id, sequence, id'

    name = fields.Char(string='Pano', required=True, translate=True)
    category_id = fields.Many2one('reporting.dashboard.category', string='Kategori', required=True, ondelete='restrict')
    description = fields.Text(string='Açıklama', translate=True)
    icon = fields.Char(string='İkon', default='fa-tachometer', help='Font Awesome ikon adı, örn. fa-bar-chart')
    color = fields.Integer(string='Renk')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    menu_id = fields.Many2one(
        'ir.ui.menu', string='Kaynak Menü', required=True, ondelete='cascade',
        domain="[('action', '!=', False)]",
        help='Panonun kendi modülündeki menüsü. Görünürlük ve açılan sayfa bu menüden gelir.',
    )
    menu_complete_name = fields.Char(related='menu_id.complete_name', string='Menü Yolu')
    action_ref = fields.Reference(
        selection=[('ir.actions.act_window', 'Pencere Aksiyonu'), ('ir.actions.client', 'İstemci Aksiyonu'),
                   ('ir.actions.server', 'Sunucu Aksiyonu'), ('ir.actions.report', 'Rapor'),
                   ('ir.actions.act_url', 'URL')],
        string='Aksiyon', compute='_compute_action_ref',
    )
    source_module = fields.Char(string='Modül', compute='_compute_source_module', store=True)
    generated_menu_id = fields.Many2one('ir.ui.menu', string='Üretilen Menü', readonly=True, copy=False, ondelete='set null')
    is_visible = fields.Boolean(
        string='Görebilirim', compute='_compute_is_visible', search='_search_is_visible',
        help='Giriş yapan kullanıcı panonun kaynak menüsünü görebiliyor mu?',
    )

    _sql_constraints = [
        ('menu_uniq', 'unique(menu_id)', 'Bu menü zaten bir pano kaydına bağlı.'),
    ]

    # ------------------------------------------------------------------
    @api.depends('menu_id', 'menu_id.action')
    def _compute_action_ref(self):
        for rec in self:
            act = rec.menu_id.action
            rec.action_ref = '%s,%s' % (act._name, act.id) if act else False

    @api.depends('menu_id')
    def _compute_source_module(self):
        Data = self.env['ir.model.data'].sudo()
        for rec in self:
            module = False
            if rec.menu_id:
                data = Data.search([('model', '=', 'ir.ui.menu'), ('res_id', '=', rec.menu_id.id)], limit=1)
                module = data.module if data else False
            rec.source_module = module

    @api.model
    def _visible_menu_ids(self):
        return set(self.env['ir.ui.menu']._visible_menu_ids())

    @api.depends_context('uid')
    def _compute_is_visible(self):
        visible = self._visible_menu_ids()
        for rec in self:
            rec.is_visible = bool(rec.menu_id and rec.menu_id.id in visible)

    def _search_is_visible(self, operator, value):
        visible = list(self._visible_menu_ids())
        positive = (operator == '=' and value) or (operator == '!=' and not value)
        return [('menu_id', 'in' if positive else 'not in', visible)]

    # ------------------------------------------------------------------
    # Üretilen menü (ERP Merkezi / Panolar / Kategori / Pano) — aynı aksiyon
    # ------------------------------------------------------------------
    def _source_groups(self):
        """Kaynak menünün ve üstlerinin grupları; üretilen menü aynı gruplarla
        kısıtlanır (yetkisi olmayan menüyü görmez)."""
        self.ensure_one()
        groups = self.env['res.groups']
        menu = self.menu_id.sudo()
        while menu:
            groups |= menu.groups_id
            menu = menu.parent_id
        return groups

    def _sync_generated_menu(self):
        Menu = self.env['ir.ui.menu'].sudo()
        for rec in self:
            rec.category_id._ensure_menu()
            act = rec.menu_id.sudo().action
            if not rec.active or not act or not rec.category_id.menu_id:
                if rec.generated_menu_id:
                    rec.generated_menu_id.sudo().unlink()
                continue
            vals = {
                'name': rec.name,
                'parent_id': rec.category_id.menu_id.id,
                'sequence': rec.sequence,
                'action': '%s,%s' % (act._name, act.id),
                'groups_id': [(6, 0, rec._source_groups().ids)],
            }
            if rec.generated_menu_id and rec.generated_menu_id.exists():
                rec.generated_menu_id.write(vals)
            else:
                rec.generated_menu_id = Menu.create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._sync_generated_menu()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in ('name', 'category_id', 'sequence', 'active', 'menu_id')):
            self._sync_generated_menu()
        return res

    def unlink(self):
        menus = self.mapped('generated_menu_id')
        res = super().unlink()
        menus.sudo().unlink()
        return res

    # ------------------------------------------------------------------
    def action_open(self):
        """Panoyu kendi aksiyonuyla aç; kaynak menüyü göremeyen kullanıcıya hata."""
        self.ensure_one()
        if not self.is_visible:
            raise AccessError(_('"%s" panosuna erişim yetkiniz yok (%s).') % (self.name, self.menu_complete_name))
        act = self.menu_id.sudo().action
        if not act:
            raise UserError(_('"%s" menüsünün aksiyonu yok.') % self.menu_id.name)
        return act.sudo()._get_action_dict()

    # ------------------------------------------------------------------
    # Tarama: sistemdeki panoları bul ve kayıt defterine ekle
    # ------------------------------------------------------------------
    NAME_PATTERN = r'dashboard|pano|panel|anasayfa|genel bakış|overview|cockpit'
    # Sıra önemli: yardım masası panoları (İK/Finans/Satınalma) "Talepler"e girer
    CATEGORY_RULES = [
        ('Talepler', r'helpdesk|yardım|talep|ticket'),
        ('İnşaat', r'hakediş|hakedis|inşaat|insaat|şantiye|construction|proje'),
        ('İhale / Satınalma', r'ihale|satınalma|satinalma|tender|purchase|procurement'),
        ('Finans', r'nakit|kredi|çek|senet|fon|muhasebe|banka|finans|loan|cash|bank|account'),
    ]

    @staticmethod
    def _tr_lower(text):
        """Türkçe duyarlı küçük harf: İ→i, I→ı (Python lower() İ için nokta bırakır)."""
        return (text or '').replace('İ', 'i').replace('I', 'ı').lower()

    @api.model
    def _scan_candidate_menus(self):
        root = self.env.ref('mimol_reporting.menu_reporting_root', raise_if_not_found=False)
        Menu = self.env['ir.ui.menu'].sudo().with_context(active_test=True)
        menus = Menu.search([('action', '!=', False)])
        pattern = re.compile(self.NAME_PATTERN)
        found = Menu
        seen_actions = set()
        # Kök menüler en sona: aynı aksiyon alt menüde de varsa alt menü kazanır
        for menu in menus.sorted(key=lambda m: (not m.parent_id, m.id)):
            if root and menu.complete_name.startswith(root.complete_name):
                continue
            act = menu.action
            if not act:
                continue
            key = (act._name, act.id)
            if key in seen_actions:
                continue
            name_hit = bool(pattern.search(self._tr_lower(menu.name)))
            tag_hit = act._name == 'ir.actions.client' and 'dashboard' in (act.tag or '').lower()
            if name_hit or tag_hit:
                found |= menu
                seen_actions.add(key)
        return found

    @api.model
    def _guess_category(self, menu):
        text = self._tr_lower(menu.complete_name)
        Category = self.env['reporting.dashboard.category']
        for cat_name, rx in self.CATEGORY_RULES:
            if re.search(rx, text):
                cat = Category.search([('name', '=', cat_name)], limit=1)
                if not cat:
                    cat = Category.create({'name': cat_name})
                return cat
        cat = Category.search([('name', '=', 'Diğer')], limit=1)
        return cat or Category.create({'name': 'Diğer', 'sequence': 99})

    @api.model
    def action_scan_menus(self):
        """Ayarlar butonu ve kurulum kancası: yeni panoları kayıt defterine ekle.
        Menü adları kullanıcının dilinde (context lang yoksa kaynak dil olan
        İngilizce dönerdi) okunur."""
        lang = self.env.context.get('lang') or self.env.user.lang or 'en_US'
        self = self.with_context(lang=lang)
        existing = set(self.with_context(active_test=False).search([]).mapped('menu_id').ids)
        created = self.browse()
        for menu in self._scan_candidate_menus():
            if menu.id in existing:
                continue
            parent = menu.parent_id.sudo()
            app = parent.name if parent else ''
            while parent and parent.parent_id:
                parent = parent.parent_id
                app = parent.name
            name = menu.name if not app or app.lower() in (menu.name or '').lower() else '%s — %s' % (app, menu.name)
            created |= self.create({
                'name': name,
                'category_id': self._guess_category(menu).id,
                'description': _('%s menüsü') % menu.complete_name,
                'menu_id': menu.id,
            })
        if created:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Pano taraması'), 'type': 'success',
                           'message': _('%d yeni pano eklendi.') % len(created), 'next': {'type': 'ir.actions.client', 'tag': 'reload'}},
            }
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': _('Pano taraması'), 'type': 'info', 'message': _('Yeni pano bulunmadı.')},
        }
