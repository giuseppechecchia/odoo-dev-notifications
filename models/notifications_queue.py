#!/usr/bin/python
###############################################################################
# Copyleft (K) 2020-2022
# Developer: Giuseppe Checchia @eldoleo (<https://github.com/giuseppechecchia>)
###############################################################################

from odoo import models, fields

import logging

_logger = logging.getLogger(__name__)


class ResCompanyNotificationQueue(models.Model):
    """
    A simple iterative SIB messagge Queue
    """

    _name = 'fr.notification.queue'
    _description = 'Coda per le notifiche'

    to_email = fields.Char(
        'Indirizzo destinatario',
        required=True,
    )
    to_name = fields.Char(
        'Nome destinatario',
        required=True,
    )
    cc_email = fields.Char('Indirizzo destinatario secondario')
    cc_name = fields.Char('Nome destinatario secondario')
    id_sb_template = fields.Char(
        'ID Template SendinBlue',
        default='11'
    )
    body = fields.Char('Corpo HTML del messaggio')
    subject = fields.Char(
        'Oggetto del messaggio',
    )
    severity = fields.Selection(
        string="Gravità del messaggio",
        selection=[('info', 'INFO'),
                   ('warning', 'WARNING'),
                   ('error', 'ERROR'),
                   ('critical', 'CRITICAL')
                   ],
        default="info",
    )

    sent = fields.Boolean(
        'Già inviato',
        default=False,
        index=True,
    )

    def message_receiver(self, params):

        from datetime import datetime, timedelta
        d = datetime.today() - timedelta(days=1)

        if params['to_email'] == '':
            return "to_email can't be empty"

        if params['to_name'] == '':
            return "to_name can't be empty"

        if params['body'] == '':
            return "body can't be empty"

        if params['subject'] == '':
            return "subject can't be empty"

        if 'cc_email' not in params.keys():
            params['cc_email'] = ''

        if 'cc_name' not in params.keys():
            params['cc_name'] = ''

        if 'id_sb_template' not in params.keys():
            params['id_sb_template'] = '11'

        severity_list = [
            'info',
            'warning',
            'error',
            'critical'
        ]
        sev = ', '.join(severity_list)
        if params['severity'] not in severity_list:
            return f'severity must be {sev} - not empty or a custom value'

        result = self.search(
            [
                ('to_email', '=', params['to_email']),
                ('to_name', '=', params['to_name']),
                ('subject', '=', params['subject']),
                ('body', '=', params['body']),
                ('sent', '=', False),
                ('write_date', '>', d)
            ]
        )

        if len(result) > 0:
            return f'Same message just placed, try again!'
        else:
            self.create({
                'to_email': params['to_email'],
                'to_name': params['to_name'],
                'cc_email': params['cc_email'],
                'cc_name': params['cc_name'],
                'id_sb_template': params['id_sb_template'],
                'body': params['body'],
                'subject': params['subject'],
                'severity': params['severity']
            })

    def send_the_mail(self):

        # TODO: actually the template id is not used
        # but will be if we pass it trought method

        result = self.sudo().search(
            [
                ('sent', '=', False),
            ]
        )

        if len(result) <= 0:
            _logger.info("no messages need to be sent")
        else:
            for x in result:
                recipients = x.to_email
                self.env['res.company'].sudo().notify(
                    x.subject,
                    f"{x.severity.upper()}",
                    x.body,
                    channel='all',
                    recipients_kind=recipients
                )
                self._cr.execute(f"""
                    update fr_notification_queue q
                    set sent = true
                    where id = {x.id}
                    """)
                self.env.cr.commit()
