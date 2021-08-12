#!/usr/bin/python
###############################################################################
# Copyleft (K) 2020-2022
# Developer: Giuseppe Checchia @eldoleo (<https://github.com/giuseppechecchia>)
###############################################################################

from odoo import http
from odoo.http import request

import logging

_logger = logging.getLogger(__name__)


class ActionExecute(http.Controller):

    @http.route(
        '/NotificationQueue/message_receiver',
        auth='user',
        website=True,
        type="json",
        csrf=False,
        methods=['POST']
    )
    def message_receiver(self):

        mandatory_fields = [
            'to_email',
            'to_name',
            'body',
            'subject',
            'severity'
        ]

        if http.request.params:
            k = 0
            for x in http.request.params.keys():
                if x in mandatory_fields:
                    k += 1

            m_f_string = ', '.join(mandatory_fields)
            if k < 5:
                return f"Something missing. Mandatory fields are: {m_f_string}"

            my_env = request.env['fr.notification.queue']
            result = my_env.sudo().message_receiver(
                http.request.params
            )

            return result
