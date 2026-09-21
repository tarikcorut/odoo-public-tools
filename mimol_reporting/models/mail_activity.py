# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MailActivity(models.Model):
    """Raporlama Merkezi aktiviteyi tek kaynak olarak kullanır.

    Odoo 17'de tipi "Keep Done" olan aktiviteler tamamlanınca silinmez,
    arşivlenir (active=False, date_done). Buraya eklenenler:
    - reporting_kind / res_model_name: Onay-Görev-Bilgi ve uygulama bazında gruplama
    - deadline_state: Geciken / Bugün / Planlanan / Tamamlandı (saklı; gece cron'u tazeler)
    - done_user_id, date_done_dt, done_result, done_feedback: kim, ne zaman, ne sonuçla kapattı
    - duration_days, was_late: geçmiş raporları için süre ve gecikme
    Süreç modülleri sonucu context ile bildirebilir:
        activity.with_context(activity_done_result='refused').action_feedback(feedback='...')
    """
    _inherit = 'mail.activity'

    reporting_kind = fields.Selection(
        related='activity_type_id.reporting_kind', string='Raporlama Türü', store=True, readonly=True,
    )
    res_model_name = fields.Char(
        related='res_model_id.name', string='Uygulama', store=True, readonly=True,
    )
    deadline_state = fields.Selection(
        [('overdue', 'Geciken'), ('today', 'Bugün'), ('planned', 'Planlanan'), ('done', 'Tamamlandı')],
        string='Durum', compute='_compute_deadline_state', store=True, index=True,
    )
    done_user_id = fields.Many2one('res.users', string='Tamamlayan', readonly=True, index=True)
    date_done_dt = fields.Datetime(string='Tamamlanma Zamanı', readonly=True)
    done_result = fields.Selection(
        [('done', 'Tamamlandı'), ('refused', 'Reddedildi'), ('cancelled', 'İptal')],
        string='Sonuç', readonly=True,
    )
    done_feedback = fields.Text(string='Geri Bildirim', readonly=True)
    duration_days = fields.Float(
        string='Süre (gün)', compute='_compute_duration', store=True, digits=(16, 1),
        help='Aktivitenin açılışından tamamlanmasına kadar geçen süre.',
    )
    was_late = fields.Boolean(
        string='Gecikmeli', compute='_compute_duration', store=True,
        help='Tamamlanma günü son tarihten sonraysa işaretli.',
    )

    # ------------------------------------------------------------------
    # Hesaplamalar
    # ------------------------------------------------------------------
    @api.depends('active', 'date_deadline', 'user_id')
    def _compute_deadline_state(self):
        for rec in self:
            if not rec.active:
                rec.deadline_state = 'done'
                continue
            if not rec.date_deadline:
                rec.deadline_state = 'planned'
                continue
            tz = rec.user_id.sudo().tz or 'UTC'
            today = fields.Date.context_today(rec.with_context(tz=tz))
            if rec.date_deadline < today:
                rec.deadline_state = 'overdue'
            elif rec.date_deadline == today:
                rec.deadline_state = 'today'
            else:
                rec.deadline_state = 'planned'

    @api.depends('create_date', 'date_done_dt', 'date_deadline')
    def _compute_duration(self):
        for rec in self:
            if rec.date_done_dt and rec.create_date:
                rec.duration_days = round((rec.date_done_dt - rec.create_date).total_seconds() / 86400.0, 1)
                rec.was_late = bool(rec.date_deadline and rec.date_done_dt.date() > rec.date_deadline)
            else:
                rec.duration_days = 0.0
                rec.was_late = False

    @api.model
    def _cron_refresh_deadline_state(self):
        """Gün değişince Planlanan → Bugün → Geciken geçişlerini tazele.
        Yalnız durumu değişebilecek açık aktiviteler yeniden hesaplanır."""
        today = fields.Date.today()
        stale = self.search([
            ('active', '=', True),
            '|', '|',
            '&', ('deadline_state', '=', 'planned'), ('date_deadline', '<=', today + timedelta(days=1)),
            '&', ('deadline_state', '=', 'today'), ('date_deadline', '!=', today),
            '&', ('deadline_state', '=', 'overdue'), ('date_deadline', '>=', today),
        ])
        if stale:
            # date_deadline değişmiş gibi işaretle: bağımlı saklı alan yeniden hesaplanır
            stale.modified(['date_deadline'])
            stale.flush_recordset(['deadline_state'])
        return True

    # ------------------------------------------------------------------
    # Tamamlama / iptal: geçmişi doldur
    # ------------------------------------------------------------------
    def _action_done(self, feedback=False, attachment_ids=None):
        result = self.env.context.get('activity_done_result') or 'done'
        ids = self.ids
        messages, next_activities = super()._action_done(feedback=feedback, attachment_ids=attachment_ids)
        # keep_done tipler arşivlendi (active=False); diğerleri silindi
        kept = self.browse(ids).exists().filtered(lambda a: not a.active)
        if kept:
            kept.sudo().write({
                'done_user_id': self.env.uid,
                'date_done_dt': fields.Datetime.now(),
                'done_result': result if result in ('done', 'refused', 'cancelled') else 'done',
                'done_feedback': feedback or False,
            })
        return messages, next_activities

    def unlink(self):
        """Süreç kodu aktiviteyi red / iptal nedeniyle kaldırıyorsa
        (context activity_done_result='refused' | 'cancelled') ve tip geçmişi
        saklıyorsa silmek yerine arşivle; geçmişte 'Reddedildi / İptal' görünsün."""
        result = self.env.context.get('activity_done_result')
        if result in ('refused', 'cancelled') and not self.env.context.get('mail_activity_force_unlink'):
            keep = self.filtered(lambda a: a.active and a.activity_type_id.keep_done)
            if keep:
                keep.sudo().write({
                    'active': False,
                    'done_user_id': self.env.uid,
                    'date_done_dt': fields.Datetime.now(),
                    'done_result': result,
                    'done_feedback': self.env.context.get('activity_done_feedback') or False,
                })
            return super(MailActivity, self - keep).unlink()
        return super().unlink()

    # ------------------------------------------------------------------
    # Raporlama Merkezi aksiyonları (menüler sunucu aksiyonuyla çağırır)
    # ------------------------------------------------------------------
    @api.model
    def _reporting_base_domain(self):
        """Gizlenen tipler ve modeller dışarıda."""
        domain = [('activity_type_id.reporting_exclude', '=', False)]
        param = self.env['ir.config_parameter'].sudo().get_param('mimol_reporting.excluded_models', '')
        models_ = [m.strip() for m in param.split(',') if m.strip()]
        if models_:
            domain.append(('res_model', 'not in', models_))
        return domain

    @api.model
    def action_reporting_open(self, mode='my_work'):
        """mode: my_work | my_approvals | my_tasks | my_history |
                 all_open | all_history | reports"""
        ref = self.env.ref
        views_open = [
            (ref('mimol_reporting.mail_activity_view_kanban_reporting').id, 'kanban'),
            (ref('mimol_reporting.mail_activity_view_tree_reporting').id, 'tree'),
            (ref('mimol_reporting.mail_activity_view_pivot_reporting').id, 'pivot'),
            (ref('mimol_reporting.mail_activity_view_graph_reporting').id, 'graph'),
        ]
        views_history = [
            (ref('mimol_reporting.mail_activity_view_tree_history').id, 'tree'),
            (ref('mimol_reporting.mail_activity_view_pivot_reporting').id, 'pivot'),
            (ref('mimol_reporting.mail_activity_view_graph_reporting').id, 'graph'),
        ]
        domain = self._reporting_base_domain()
        context = {'search_default_group_kind': 0}
        name = _('Benim İşlerim')
        views = views_open
        if mode == 'my_work':
            domain += [('user_id', '=', self.env.uid), ('active', '=', True)]
        elif mode == 'my_approvals':
            name = _('Onaylarım')
            domain += [('user_id', '=', self.env.uid), ('active', '=', True), ('reporting_kind', '=', 'approval')]
        elif mode == 'my_tasks':
            name = _('Görevlerim')
            domain += [('user_id', '=', self.env.uid), ('active', '=', True), ('reporting_kind', '=', 'task')]
        elif mode == 'my_history':
            name = _('Geçmişim')
            views = views_history
            domain += [('active', '=', False), '|', ('user_id', '=', self.env.uid), ('done_user_id', '=', self.env.uid)]
            context = {'active_test': False, 'search_default_group_month': 1}
        elif mode == 'all_open':
            name = _('Tüm Açık İşler')
            domain += [('active', '=', True)]
            context = {'search_default_group_user': 1}
        elif mode == 'all_history':
            name = _('Onay ve İş Geçmişi')
            views = views_history
            domain += [('active', '=', False)]
            context = {'active_test': False, 'search_default_group_app': 1}
        elif mode == 'reports':
            name = _('Raporlar')
            views = [
                (ref('mimol_reporting.mail_activity_view_pivot_reporting').id, 'pivot'),
                (ref('mimol_reporting.mail_activity_view_graph_reporting').id, 'graph'),
                (ref('mimol_reporting.mail_activity_view_tree_history').id, 'tree'),
            ]
            context = {'active_test': False, 'search_default_filter_done': 1}
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'mail.activity',
            'view_mode': ','.join(v[1] for v in views),
            'views': views,
            'search_view_id': ref('mimol_reporting.mail_activity_view_search_reporting').id,
            'domain': domain,
            'context': context,
            'help': _('<p class="o_view_nocontent_smiling_face">Bekleyen işiniz yok.</p>'
                      '<p>Onay ve görevler size aktivite olarak düştüğünde burada görünür.</p>'),
        }

    def action_reporting_mark_done(self):
        """Kanban / liste butonu: görevi tamamla (onaylar belge üzerinden verilir)."""
        self.filtered(lambda a: a.reporting_kind != 'approval').action_feedback(feedback=False)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_open_document(self):
        """Standart metodun üstüne: belge silinmişse açık hata."""
        self.ensure_one()
        if self.res_model and self.res_id:
            record = self.env[self.res_model].browse(self.res_id).exists()
            if not record:
                raise UserError(_('Bu aktivitenin belgesi (%s) silinmiş.') % (self.res_name or self.res_model))
        return super().action_open_document()
