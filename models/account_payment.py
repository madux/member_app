import time
from odoo import models, fields, api, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import except_orm, ValidationError
from odoo.tools import misc, DEFAULT_SERVER_DATETIME_FORMAT
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo import http

MAIN_STATES = [
    'green', 'temp', 'induction',
    'hon', 'ord', 'jun','life'
    ]


class account_payment(models.Model):
    _inherit = "account.payment"
    _order = "id desc"
    
    state = fields.Selection([('first_draft', 'Draft'), 
    ('draft', 'In Progress'), ('posted', 'Posted'), 
    ('sent', 'Sent'), 
    ('reconciled', 'Reconciled'),
    ('cancelled', 'Cancelled'),], 
    readonly=True, default='draft', copy=False, string="States")
 
    member_id = fields.Many2one('member.app', string="Payment Ref.")
    filex = fields.Binary("Evidence of Payment")
    file_namex = fields.Char("FileName")
    additional_ref = fields.Char("Additional Reference")
    bank = fields.Many2one(
        'res.bank',
        string='Bank',
        readonly=False)
    
    advance_amount = fields.Float('Advance Amount') 
     
    def get_amount_to_pay(self):
        total_sum = sum([amt.amount_total for amt in self.mapped('invoice_ids')])
        return total_sum

     

    @api.one
    def set_draft_prop(self):
        self.write({'state':"draft"})
        return False

    balances = fields.Float('Balance')#, compute="_compute_difference")
    amount_to_pay = fields.Float('Total Amount To pay')#, compute="_compute_difference")
    narration = fields.Text('Note')
    modes_payment = fields.Selection([
                                    ('POS', 'POS'),
                                    ('Cheque', 'Cheque'),
                                    ('Bank-Draft', 'Bank-Draft'),
                                    ('Transfer', 'Transfer')],
                                    'Mode of Payment',
                                    index=True,
                                    default='POS',
                                    required=False,
                                    readonly=False,
                                    copy=False,
                                    track_visibility='always')

    # @api.one
    @api.onchange('amount')
    def _compute_difference(self):
        if self.amount:
            self.amount_to_pay = self._compute_total_invoices_amount()
            total_sum = self.get_amount_to_pay()

            amount_difference = self.amount - total_sum

            outstanding_amount = self._compute_total_invoices_amount() - self.amount 

            if len(self.invoice_ids) == 0:
                return
            if self.invoice_ids[0].type in ['in_invoice', 'out_refund']: 
                self.balances = outstanding_amount if outstanding_amount >= 0 else 0
                 # 2000 - 3000 = 1000
                self.advance_amount = amount_difference if amount_difference > 0 else 0
            else:
                self.balances = outstanding_amount if outstanding_amount >= 0 else 0 
                self.advance_amount = amount_difference if amount_difference >= 0 else 0

    @api.multi
    def post(self):
        res = super(account_payment, self).post()
        domain_inv = [('invoice_id', 'in', [item.id for item in self.invoice_ids])]
        members_search = self.env['member.app'].search(domain_inv)
        outstanding = self.balances if self.balances >= 0 else 0
        memb_payment = "Member Payments{}".format(self.subscription_period)
        renewal_name = "Subscription Payments for sections on period {}".format(self.subscription_period)
        name = memb_payment if members_search.state not in MAIN_STATES else renewal_name
        if members_search:
            if self.subscription_period:
                total_sum = self.get_amount_to_pay()
                # members_search.cripple_advance_and_outstanding()
                members_search.subscription_payment_lines(name, total_sum, self.amount, self.payment_date, \
                    self.advance_amount, self.balances, self.subscription_period, self.id, True)
                members_search.state_payment_inv(self.amount, self.payment_date) 
                members_search.balance_total = members_search.balance_total + outstanding
                
            else:
                raise ValidationError('Please select period')

        else:
            pass
        domain_sub = [('invoice_id', 'in', [item.id for item in self.invoice_ids])]
        sub_search = self.env['subscription.model'].search(domain_sub)
        if sub_search:
            # raise ValidationError(sub_search.member_id.balance_total + outstanding)
            sub_search.member_id.balance_total = sub_search.member_id.balance_total + outstanding
            sub_search.state_payment_inv(self.amount, self.payment_date, self.id, self.payment_difference)
        else:
            pass

        # domain_guest = [('invoice_id', 'in', [item.id for item in self.invoice_ids])]
        # if not self.communication.startswith('INV') or self.communication.startswith('SO'):
        domain_guest = [('invoice_id', 'in', [item.id for item in self.invoice_ids])]
        guest_search = self.env['register.guest'].search(domain_guest)
        if guest_search:
            guest_search.write({'state': 'wait',
                                'payment_idss': [(4, self.id)]
                                }) # state_payment_inv(self.amount, self.payment_date, guest_search, self.payment_difference)
        else:
            pass
        
        domain_suspend = [('invoice_id', 'in', [item.id for item in self.invoice_ids])]
        suspend_search = self.env['suspension.model'].search(domain_suspend)
        if suspend_search:
            suspend_search.member_id.balance_total = suspend_search.member_id.balance_total + outstanding
            suspend_search.state_payment_inv()
        else:
            pass 
        
        domain_spouse = [('invoice_id', 'in', [item.id for item in self.invoice_ids])]
        spouse_search = self.env['register.spouse.member'].search(domain_spouse)
        if spouse_search:
            spouse_search.button_make_confirm(outstanding)
        else:
            pass

        # domain_policy = [('invoice_id', 'in', [item.id for item in self.invoice_ids])]
        # policy_search = self.env['member.policy.line'].search(domain_policy)
        # if policy_search:
        #     policy_search.button_confirm_member()
        # else:
        #     pass
        return res
    subscription_period = fields.Selection([
        ('Jan-June 2011', 'Jan-June 2011'),
        ('July-Dec 2011', 'July-Dec 2011'),
        ('Jan-June 2012', 'Jan-June 2012'),
        ('July-Dec 2012', 'July-Dec 2012'),
        ('Jan-June 2013', 'Jan-June 2013'),
        ('July-Dec 2013', 'July-Dec 2013'),
        ('Jan-June 2014', 'Jan-June 2014'),
        ('July-Dec 2014', 'July-Dec 2014'),
        ('Jan-June 2015', 'Jan-June 2015'),
        ('July-Dec 2015', 'July-Dec 2015'),
        ('Jan-June 2016', 'Jan-June 2016'),
        ('July-Dec 2016', 'July-Dec 2016'),
        ('Jan-June 2017', 'Jan-June 2017'),
        ('July-Dec 2017', 'July-Dec 2017'),
        ('Jan-June 2018', 'Jan-June 2018'),
        ('July-Dec 2018', 'July-Dec 2018'),
        ('Jan-June 2019', 'Jan-June 2019'),
        ('July-Dec 2019', 'July-Dec 2019'),
        ('Jan-June 2020', 'Jan-June 2020'),
        ('July-Dec 2020', 'July-Dec 2020'),
        ('Jan-June 2021', 'Jan-June 2021'),
        ('July-Dec 2021', 'July-Dec 2021'),
    ], 'Period', index=True, required=False, readonly=False, copy=True, 
                                           track_visibility='always')

    def send_mail_accounts(self):
        email_from = self.env.user.email
        group_user_id2 = self.env.ref('ikoyi_module.account_payable_ikoyi').id
        group_user_id = self.env.ref('account.group_account_manager').id
        group_user_id3 = self.env.ref('ikoyi_module.account_boss_ikoyi').id

        bodyx = "Dear Sir, <br/>A Payment with Ref: {} have been sent to you for approval Kindly validate or refuse the payment to enable us proceed. <br/>\
        Regards".format(self.invoice_ids[0].number if self.invoice_ids else self.communication)
        self.mail_sending(
            email_from,
            group_user_id,
            group_user_id2,
            group_user_id3,
            bodyx)

    def mail_sending(
            self,
            email_from,
            group_user_id,
            group_user_id2,
            group_user_id3,
            bodyx):
        from_browse = self.env.user.name
        groups = self.env['res.groups']
        for order in self:
            group_users = groups.search([('id', '=', group_user_id)])
            group_users2 = groups.search([('id', '=', group_user_id2)])
            group_users3 = groups.search([('id', '=', group_user_id3)])
            group_emails = group_users.users
            group_emails2 = group_users2.users
            group_emails3 = group_users3.users

            append_mails = []
            append_mails_to = []
            append_mails_to3 = []
            for group_mail in group_emails:
                append_mails.append(group_mail.login)

            for group_mail2 in group_emails2:
                append_mails_to.append(group_mail2.login)

            for group_mail3 in group_emails3:
                append_mails_to3.append(group_mail3.login)

            all_mails = append_mails + append_mails_to + append_mails_to3
            print(all_mails)
            email_froms = str(from_browse) + " <" + str(email_from) + ">"
            mail_sender = (', '.join(str(item)for item in all_mails)) 
            subject = "Procurement Notification"
             
            mail_data = {
                'email_from': email_froms,
                'subject': subject,
                'email_to': mail_sender,
                'email_cc': mail_sender,  #  + (','.join(str(extra)),
                'reply_to': email_from,
                'body_html': bodyx
            }
            mail_id = order.env['mail.mail'].create(mail_data)
            order.env['mail.mail'].send(mail_id)

    # @api.multi
    # def print_membership_payment_receipt(self):
    #     report = self.env["ir.actions.report.xml"].search(
    #         [('report_name', '=', 'member_app.receipt_payment_template')], limit=1)
    #     if report:
    #         report.write({'report_type': 'qweb-pdf'})
    #     return self.env['report'].get_action(
    #         self.id, 'member_app.receipt_payment_template')

 
