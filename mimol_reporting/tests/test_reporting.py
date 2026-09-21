# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReportingCenter(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Raporlama Test Cari'})
        cls.act_type = cls.env['mail.activity.type'].create({
            'name': 'Test Onay', 'reporting_kind': 'approval', 'keep_done': True,
        })
        cls.task_type = cls.env['mail.activity.type'].create({
            'name': 'Test Gorev', 'reporting_kind': 'task', 'keep_done': True,
        })

    def _schedule(self, act_type, **kw):
        return self.partner.activity_schedule(activity_type_id=act_type.id, user_id=self.env.uid, **kw)

    def test_done_is_archived_with_history(self):
        act = self._schedule(self.act_type, summary='Onay bekleniyor')
        self.assertEqual(act.reporting_kind, 'approval')
        self.assertIn(act.deadline_state, ('today', 'planned', 'overdue'))
        act_id = act.id
        act.action_feedback(feedback='Onaylandi')
        archived = self.env['mail.activity'].with_context(active_test=False).browse(act_id)
        self.assertTrue(archived.exists(), 'keep_done tipte aktivite silinmemeli')
        self.assertFalse(archived.active)
        self.assertEqual(archived.deadline_state, 'done')
        self.assertEqual(archived.done_result, 'done')
        self.assertEqual(archived.done_user_id, self.env.user)
        self.assertTrue(archived.date_done_dt)
        self.assertEqual(archived.done_feedback, 'Onaylandi')

    def test_refused_via_context_unlink(self):
        act = self._schedule(self.act_type)
        act_id = act.id
        act.with_context(activity_done_result='refused', activity_done_feedback='Butce yok').unlink()
        archived = self.env['mail.activity'].with_context(active_test=False).browse(act_id)
        self.assertTrue(archived.exists())
        self.assertEqual(archived.done_result, 'refused')
        self.assertEqual(archived.done_feedback, 'Butce yok')

    def test_plain_unlink_still_deletes(self):
        act = self._schedule(self.task_type)
        act_id = act.id
        act.unlink()
        self.assertFalse(self.env['mail.activity'].with_context(active_test=False).browse(act_id).exists())

    def test_open_action_domains(self):
        Activity = self.env['mail.activity']
        for mode in ('my_work', 'my_approvals', 'my_tasks', 'my_history', 'all_open', 'all_history', 'reports'):
            action = Activity.action_reporting_open(mode)
            self.assertEqual(action['res_model'], 'mail.activity')
            self.assertTrue(action['views'])

    def test_dashboard_registry_visibility(self):
        menu = self.env.ref('mimol_reporting.menu_reporting_my_work')
        Dashboard = self.env['reporting.dashboard']
        dash = Dashboard.create({
            'name': 'Test Pano', 'menu_id': menu.id,
            'category_id': self.env.ref('mimol_reporting.dashboard_category_other').id,
        })
        self.assertTrue(dash.generated_menu_id, 'kayıt Raporlama Merkezi / Panolar altında menü üretmeli')
        self.assertTrue(dash.is_visible)
        visible = Dashboard.search([('is_visible', '=', True)])
        self.assertIn(dash, visible)
        action = dash.action_open()
        self.assertEqual(action.get('type'), 'ir.actions.server')

    def test_scan_menus_runs(self):
        result = self.env['reporting.dashboard'].action_scan_menus()
        self.assertEqual(result.get('type'), 'ir.actions.client')
