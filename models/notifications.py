#!/usr/bin/python

# Standard
import os
import codecs
import socket
import requests
import logging

# mysql library
import mysql.connector as mysql

from odoo import models, fields, api
from datetime import datetime

# others
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

_logger = logging.getLogger(__name__)

for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
    if not ip.startswith('127.'):
        local_id = ip
        break
else:
    for sock in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]:
        sock.connect(('8.8.8.8', 53))
        local_ip = sock.getsockname()[0]
        sock.close()
        break
    else:
        local_ip = False

default_body = '{}@{}'.format(
    local_ip,
    os.getcwd()
)


class ResCompanyNotification(models.Model):
    """ Add in company class sendinblue log function (to be called everywhere)
    """
    _inherit = 'res.company'

    # Extra columns:
    sib_api_key = fields.Char('SIB API Key (v3)')
    slack_webhook_url = fields.Char('Slack Webhook URL')
    slack_users = fields.Char('Slack users for mentions')
    debug_on_file_filepath = fields.Char('Debug on the fly log filepath')

    sendinblue_to_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='company_sendinblue_to_rel',
        string='Sendinblue TO',
        required=True,
        domain="[('email', '!=', False)]",
    )
    sendinblue_cc_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='company_sendinblue_cc_rel',
        string='Sendinblue CC',
        domain="[('email', '!=', False)]",
    )

    sendinblue_to_ids_administration = fields.Many2many(
        comodel_name='res.partner',
        relation='company_sendinblue_to_administration_rel',
        string='Sendinblue TO Administration',
        required=True,
        domain="[('email', '!=', False)]",
    )
    sendinblue_cc_ids_administration = fields.Many2many(
        comodel_name='res.partner',
        relation='company_sendinblue_cc_administration_rel',
        string='Sendinblue CC Administration',
        domain="[('email', '!=', False)]",
    )

    sendinblue_sender_id = fields.Many2one(
        comodel_name='res.partner',
        string='Sendinblue sender',
        default=1,
        required=True,
        domain="[('email', '!=', False)]",
    )
    sendinblue_subject_version = fields.Char(
        string='Sendinblue subject version',
        default='0.1',
        required=True,
    )

    def get_email_from_group(self, group_xml_id):
        """ Check users belong to group_xml_id and return partner list
        """
        # Pool used:
        model_pool = self.env['ir.model.data']

        group_part = group_xml_id.split('.')
        if len(group_part) != 2:
            error = 'ODOO Group (check the code) not in correct syntax ' \
                    'module.group: {}'.format(group_xml_id)
            return _logger.error(error)
            # raise exceptions.Error(error)

        group = model_pool.get_object(*group_part)
        return [user.partner_id for user in group.users]

    # -------------------------------------------------------------------------
    # Button events:
    # -------------------------------------------------------------------------

    def test_sib(self):
        """ SIB Test button
        """
        return self.notify(
            'Test button pressed', 'DEV',
            'This is a dev test, please ignore the message.', 'sendinblue')

    def test_slack(self):
        """ SLACK Test button
        """
        return self.notify(
            'Test button pressed', 'DEV',
            'This is a dev test, please ignore the message.', 'slack')

    def test_debug_on_file(self):
        """ LOG ON FILE Test button
        """
        return self.debug_on_file(
            'DEV', 'This is a dev test, please ignore the message.\n')

    def test_all(self):
        """ TRY ALL EM ALL
        """
        return self.notify(
            'Test button pressed', 'DEV',
            'This is a dev test, please ignore the message.', 'all')

    # -------------------------------------------------------------------------
    # Entry function:
    # -------------------------------------------------------------------------
    @api.model
    def notify(self, error, error_type='NOTICE', body=default_body,
               channel='sendinblue', recipients_kind='DEV'):
        """ Notify master procedure
            error: subject of the error
            error_type: Sendinblue type: NOTICE,
            body: error body message
            channel: notify channels are: sendinblue, slack, all
            recipents_kind: 2 mode parameter
                 - odoo group xml_id: module_name.group_xml_id
                 - shortcut like: 'DEV', 'ADMINISTRATION'
        """
        company = self.env.company

        # ---------------------------------------------------------------------
        #                       Mandatory parameter check:
        # ---------------------------------------------------------------------
        # Sendiblue basic check
        if not company.sib_api_key:
            _logger.error('SIB API Key is a mandatory field')
            return False

        # Slack basic check
        if channel == 'slack' and not company.slack_webhook_url:
            _logger.error('No Slack Webhook defined on company settings')
            return False

        # All basic check
        if channel == 'all' and not company.slack_webhook_url:
            _logger.error('No Slack Webhook defined on company settings: '
                          'proceeding by sending the email only')
            self.sendinblue(error, error_type, body, recipients_kind)
            return False

        # ---------------------------------------------------------------------
        #                    Manage selected channel:
        # ---------------------------------------------------------------------
        # If I would to send an email
        if channel == 'sendinblue':
            self.sendinblue(error, error_type, body, recipients_kind)
        # If I would to send a Slack message
        elif channel == 'slack':
            self.slack(error, error_type, body)
        # If I would to send both an email and a Slack message
        elif channel == 'all':
            self.sendinblue(error, error_type, body, recipients_kind)
            self.slack(error, error_type, body)
        # If something weird happened, the system doing fallback on sendinblue
        else:
            self.sendinblue(error, error_type, body, recipients_kind)

    # -------------------------------------------------------------------------
    # Google Cloud pub/sub call:
    # -------------------------------------------------------------------------
    @api.model
    def cloud_notify(self, error, error_type='NOTICE', body=default_body,
                     channel='sendinblue', delay='0'):
        # TODO here we'll put methods to call our external notification system
        #  on Google Cloud
        pass

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    @api.model
    def sendinblue(self, error, error_type, body, recipients_kind):
        """ Send log message via Sendinblue API message
        """
        def get_recipients_list(partner_list):
            """ Extract from company many2many partner list the list of dict
                used in sendinblue send operation
            """
            recipients = []
            for partner in partner_list:
                partner_name = partner.name
                partner_email = partner.email

                if not partner_email:
                    _logger.error('Partner {0} without email, not used'.format(
                        partner_name))
                    continue
                recipients.append({
                    'name': partner_name,
                    'email': partner_email,
                })
            return recipients

        company = self.env.company

        # Configure API key authorization: api-key
        configuration = sib_api_v3_sdk.Configuration()

        configuration.api_key['api-key'] = company.sib_api_key

        params = {  # For API call:
            'subject': '[ODOO/{}][{}] {}'.format(
                company.sendinblue_subject_version,
                error_type,
                error),
            'html_content': body,
            # template_id='11',
            # params='{'FNAME':'Joe', 'LNAME':'Doe'}'
        }

        # create an instance of the API class
        api_instance = sib_api_v3_sdk.SMTPApi(
            sib_api_v3_sdk.ApiClient(configuration))
        # SendSmtpEmail | Values to send a transactional email

        if recipients_kind == 'DEV':
            params['to'] = get_recipients_list(company.sendinblue_to_ids)
            cc_recipients = get_recipients_list(company.sendinblue_cc_ids)
        elif recipients_kind == 'ADMINISTRATION':
            params['to'] = get_recipients_list(
                company.sendinblue_to_ids_administration)
            cc_recipients = get_recipients_list(
                company.sendinblue_cc_ids_administration)
        else:
            # Extract user partner ID from group:
            params['to'] = get_recipients_list(
                self.get_email_from_group(recipients_kind))
            cc_recipients = False
            if not params['to']:  # Empty also if no user
                _logger.error('Wrong kind of recipients. It should be '
                              '"DEV" or "ADMINISTRATION" or '
                              'ODOO Group: "module.xml_id" '
                              '(needs users with mail in it)')

        params['sender'] = get_recipients_list(
            [company.sendinblue_sender_id])[0]
        if not all((params['to'], params['sender'])):
            _logger.error('Missed some recipients, check email in company '
                          'parameters or in group XML ID used in code! '
                          'No notifications are sent.')
            return False

        if cc_recipients:  # CC not mandatory:
            params['cc'] = cc_recipients
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(**params)

        try:
            # Send a transactional email
            api_response = api_instance.send_transac_email(send_smtp_email)
            _logger.debug(api_response)
        except ApiException as e:
            _logger.debug(
                'Exception when calling SMTPApi->send_transac_email: {0}'
                '\n'.format(e))

    @api.model
    def slack(self, error, error_type='NOTICE', body=default_body):
        """ Raise log message in Slack
        """
        company = self.env.company

        if not company.slack_users:
            mention = "\n<!everyone>"
        else:
            mention = "\n{}".format(company.slack_users)

        text = '\n\n*[{}][{}]*\n{}{}'.format(
            error_type,
            error,
            body,
            mention
        )

        payload = '{{"type": "mrkdwn","text":"{}"}}'.format(text)
        headers = {'content-type': 'application/json'}
        r = requests.post(
            company.slack_webhook_url,
            data=payload.encode('utf-8'),
            headers=headers)
        _logger.debug(r)

    @api.model
    def debug_on_console(self, error):
        """ Write on debug console / ODOO log file
        """
        try:
            _logger.debug(error)
            return True
        except ModuleNotFoundError as e:
            _logger.debug(e)
            return False

    @api.model
    def debug_on_file(self, error_type, error):
        """ Write on log file
        """
        company = self.env.company

        if not company.debug_on_file_filepath:
            _logger.error('Debug on-the-fly log filepath '
                          '(debug_on_file_filepath) is a mandatory field to '
                          'use this method ')
            return False

        now = datetime.now()
        dt_string = now.strftime('%Y-%m-%d %H:%M:%S')

        try:
            file_object = codecs.open(
                company.debug_on_file_filepath, 'a', 'utf-8')
            file_object.write('[{}][{}] {}'.format(
                dt_string,
                error_type,
                error,
            ))
            file_object.close()
            _logger.debug(error)
            return True
        except ModuleNotFoundError as e:
            _logger.debug(e)
            return False
