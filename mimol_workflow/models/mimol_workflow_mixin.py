from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MimolWorkflowMixin(models.AbstractModel):
    _name = "mimol.workflow.mixin"
    _description = "Workflow Engine Mixin"

    first_state_name = fields.Char("First State Name")#should be overriden
    activity_name = fields.Char("Activity Name")#should be overriden
    user_name = fields.Char("User Name")#should be overriden
    state = fields.Selection([('draft','Draft'),
                              ('completed', 'Completed'),
                              ('rejected', 'Rejected'),
                              ], string="State")#should be overriden, draft, completed and rejected states are mandatory

    #should override(2nd parameter)
    next_approver_ids = fields.Many2many('res.users',
                                         "mimol_workflow_next_approvers_rel",#should be overriden
                                         string='Kaydı onaylayabilen kullanıcılar', store=True,
                                         compute='compute_next_approver_ids')

    # should override(2nd parameter)
    secondary_approver_ids = fields.Many2many('res.users',
                                         "mimol_workflow_secondary_approvers_rel",#should be overriden
                                         string='Kaydı onaylayabilen ikincil kullanıcılar',
                                         store=True,
                                         compute='compute_secondary_approver_ids')

    can_confirm_or_reject = fields.Boolean('Onaylanabilir', store=False, compute='_compute_can_confirm')
    state_color = fields.Char('Color', store=False, compute='compute_state_color')

    reject_reason = fields.Char("Red Nedeni", tracking=True)

    def _compute_can_confirm(self):
        for rec in self:
            ret = False
            for rec2 in rec.next_approver_ids:
                if rec2.id == self.env.uid:
                    ret = True
            if not ret:
                for rec2 in rec.secondary_approver_ids:
                    if rec2.id == self.env.uid:
                        ret = True
            rec.can_confirm_or_reject = ret

    def action_convert_draft(self):
        for rec in self:
            if rec.state == 'rejected' or rec.state==rec.first_state_name:
                rec.write({
                    'state': 'draft',
                    'reject_reason': False
                })
                rec.refresh_approvers()
            else:
                raise UserError('Yanlızca reddedilen tutanak ve iş emirleri taslağa geri çevrilebilir.')
            rec.activity_update()

    def refresh_approvers(self):
        for rec in self:
            rec.compute_next_approver_ids()
            rec.compute_secondary_approver_ids()
            print(rec._name)
            rec.set_followers(rec._name)

    def compute_state_color(self):
        for record in self:
            if record.state == 'rejected':
                record['state_color'] = '1'
            elif record.state == 'draft':
                record['state_color'] = '2'
            elif record.state == 'completed':
                record['state_color'] = '7'
            else:
                record['state_color'] = '4'

    def set_followers(self, model_name):
        for rec in self.next_approver_ids:
            if not self.env['mail.followers'].search(
                    [('res_id', '=', self.id),
                     ('res_model', '=', model_name),
                     ('partner_id', '=', rec.partner_id.id)]):
                if self.id and rec.partner_id.id:
                    self.env['mail.followers'].sudo().create({
                        "res_id": self.id,
                        "res_model": model_name,
                        "partner_id": rec.partner_id.id
                    })

    def action_confirm(self):
        for rec in self:
            if rec.can_confirm_or_reject:
                template1 = False
                if rec.state == 'completed':
                    raise UserError('Bu işlemi gerçekleştiremezsiniz')
                elif rec.state == 'rejected':
                    raise UserError('Bu işlemi gerçekleştiremezsiniz')
                else:
                    if self.env.uid not in rec.next_approver_ids.ids:
                        raise UserError('Bu işlemi ' + rec.next_approver_ids[0].name + ' kullanıcısı gerçekleştirebilir')
                    rec.write({
                        'state': rec.get_next_state_name()
                    })
                    rec.refresh_approvers()
                rec.activity_update()
            else:
                raise UserError('Bu işlemi gerçekleştiremezsiniz')

    def action_reject(self):
        if self.can_confirm_or_reject:
            self.write({
                'state': 'rejected'
            })
            self.cancel_all_activities()

    def action_delete(self):
        if self.can_confirm_or_reject:
            self.cancel_all_activities()
            self.unlink()
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        else:
            raise UserError('Bu işlemi gerçekleştiremezsiniz')

    def unlink(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError('Yanlızca taslak statüsündeki kayıtları silebilirsiniz')
        return super(MimolWorkflowMixin, self).unlink()

    def activity_update(self):
        for rec in self:

            note = rec.user_name + """  kullanıcısının girmiş olduğu """+str(rec.id) + """ numaralı """+rec._description+""" onayınızı beklemektedir. """

            if rec.state == 'draft':
                rec.cancel_all_activities()
                for approver in rec.next_approver_ids:
                    rec.activity_schedule(
                        rec.activity_name,
                        note=str(rec.id) + " nolu "+self._description+"'ni onaya göndermeniz beklenmektedir.",
                        user_id=approver.id)
            elif rec.state == 'completed':
                rec.complete_all_activities()
            elif rec.state == 'rejected':
                rec.cancel_all_activities()
            else:
                rec.complete_all_activities()
                for approver in rec.next_approver_ids:
                    rec.activity_schedule(
                        rec.activity_name,
                        note=note,
                        user_id=approver.id)

    def complete_all_activities(self):
        try:
            print("aktivite:")
            print(self.activity_name)
            self.activity_feedback([self.activity_name])
        except Exception as e:
            print(e)

    def cancel_all_activities(self):
        try:
            self.activity_unlink([self.activity_name])
        except Exception as e:
            print(e)

    #these 3 functions should be overriden
    def get_next_state_name(self):
        return False

    @api.depends('state')
    def compute_next_approver_ids(self):
        self.next_approver_ids = False

    def compute_secondary_approver_ids(self):
        self.secondary_approver_ids = False





