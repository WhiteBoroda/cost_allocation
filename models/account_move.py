from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    # ИСПРАВЛЕНО: Добавлена связь с подпиской для автоматического выставления счетов
    subscription_id = fields.Many2one('client.service.subscription', string='Subscription',
                                      help='Source subscription for this invoice')


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # ИСПРАВЛЕНО: Добавлена связь с линией подписки
    subscription_line_id = fields.Many2one('client.service.subscription.line',
                                           string='Subscription Line',
                                           help='Source subscription line for this invoice line')