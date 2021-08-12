#!/usr/bin/python
###############################################################################
# Copyleft (K) 2020-2022
# Developer: Giuseppe Checchia @eldoleo (<https://github.com/giuseppechecchia>)
###############################################################################

# Standard
import os
import codecs
import socket
import requests
import logging

from odoo import models, fields, api
from datetime import datetime, timedelta


# others
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

# -------------------------------------------------------------
# Monkey Patching to disable mail_message for some jobs - START
# -------------------------------------------------------------
from odoo.addons.queue_job.models.queue_job import QueueJob

tracking_remove = [
    ('model.name', 'method_name'),
]


def _message_post_on_failure_new(self):
    # subscribe the users now to avoid to subscribe them
    # at every job creation

    domain = self._subscribe_users_domain()
    users = self.env["res.users"].search(domain)
    self.message_subscribe(partner_ids=users.mapped("partner_id").ids)
    for record in self:
        msg = record._message_failed_job()
        if msg:
            send = True
            for removed in tracking_remove:
                if self.model_name in removed[0] \
                        and self.method_name == removed[1]:
                    send = False
                    break
            send = False  # <-----
            if send:
                record.message_post(
                    body=msg, subtype="queue_job.mt_job_failed")


QueueJob._message_post_on_failure = _message_post_on_failure_new
# -----------------------------------------------------------
# Monkey Patching to disable mail_message for some jobs - END
# -----------------------------------------------------------


_logger = logging.getLogger(__name__)

# -------------------------------------------------------------
# Casting something to be used later - START
# -------------------------------------------------------------
for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
    if not ip.startswith('127.'):
        local_ip = ip
        break
else:
    for sock in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]:
        sock.connect(('8.8.8.8', 53))
        local_ip = sock.getsockname()[0]
        sock.close()
        break
    else:
        local_ip = False

DEFAULT_BODY = '{}@{}'.format(
    local_ip,
    os.getcwd()
)
# -------------------------------------------------------------
# Casting something to be used later - END
# -------------------------------------------------------------


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
    def notify(self, error, error_type='NOTICE', body=DEFAULT_BODY,
               channel='sendinblue', recipients_kind='DEV', verbose=False):
        """ Notify master procedure
            error: subject of the error
            error_type: Sendinblue type: NOTICE,
            body: error body message
            channel: notify channels are: sendinblue, slack, all
            recipients_kind: 2 mode parameter
                - 'DEV'
                - 'ADMINISTRATION'
                - odoo group xml_id: module_name.group_xml_id
                - a single mail address: robo@gmail.com
                - comma separated mail addresses: robo@gmail.com,coso@gmail.com
            verbose: normal log in odoo
        """
        company = self.env.company

        # ODOO log system:
        if verbose:
            _logger.warning(body)

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
        # If I would like to send an email
        if channel == 'sendinblue':
            self.sendinblue(error, error_type, body, recipients_kind)
        # If I would like to send a Slack message
        elif channel == 'slack':
            self.slack(error, error_type, body)
        # If I would like to send both an email and a Slack message
        elif channel == 'all':
            self.sendinblue(error, error_type, body, recipients_kind)
            self.slack(error, error_type, body)
        # If something weird happened, the system is doing fallback
        # on sendinblue
        else:
            self.sendinblue(error, error_type, body, recipients_kind)

    # -------------------------------------------------------------------------
    # Google Cloud pub/sub call:
    # -------------------------------------------------------------------------
    @api.model
    def cloud_notify(self, error, error_type='NOTICE', body=DEFAULT_BODY,
                     channel='sendinblue', delay='0'):
        # TODO here we'll put methods to call our external notification system
        # on Google Cloud
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

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
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
            cc_recipients = False
            if "." in recipients_kind and "@" not in recipients_kind:
                # Extract user partner ID from group:
                params['to'] = get_recipients_list(
                    self.get_email_from_group(recipients_kind))
            elif '@' in recipients_kind:
                if "," in recipients_kind.replace(";", ","):
                    all_addresses = recipients_kind.split(",")
                else:
                    all_addresses = [recipients_kind]
                params['to'] = list()
                for recipient in all_addresses:
                    recipient.strip()
                    at_sign_position = recipient.index('@')
                    name_to = recipient[0:at_sign_position]
                    params['to'].append({
                        'name': name_to,
                        'email': recipient,
                    })

            if not params['to']:  # Empty also if no user
                _logger.error('Wrong kind of recipients. It should be: '
                              '"DEV", "ADMINISTRATION", '
                              'ODOO Group "module.xml_id" (needs '
                              'users with mail in it), a single '
                              'mail address or comma separated ones')

        params['sender'] = get_recipients_list(
            [company.sendinblue_sender_id])[0]
        if not all((params['to'], params['sender'])):

            _logger.error('Missed some recipients, check email in company '
                          'parameters, in group XML ID used in code or the '
                          'mail address/addresses! No notifications are sent.')
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
    def slack(self, error, error_type='NOTICE', body=DEFAULT_BODY):
        """ Raise log message in Slack
        """
        company = self.env.company

        if not company.slack_users:
            mention = "\n<!everyone>"
        else:
            mention = "\n{}".format(company.slack_users)

        text = f'\n\n*[{error_type}][{error}]*\n{body}{mention}'

        payload = '{{"type": "mrkdwn","text":"{}"}}'.format(text)
        headers = {'content-type': 'application/json'}

        r = requests.post(
            company.slack_webhook_url,
            data=payload.encode('utf-8'),
            headers=headers)

        _logger.info(r.status_code)

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

    def debug_on_file(self,
                      error_type,
                      error,
                      different_filepath=None,
                      filemode='a',
                      raw_error=False,
                      ):
        """ Write on log file
        """
        company = self.env.company
        filemode_list = ('a', 'w', 'w+', 'a+')
        if different_filepath:
            path = different_filepath
        else:
            path = company.debug_on_file_filepath
        if not path:
            _logger.error('Debug on-the-fly log filepath '
                          '(debug_on_file_filepath) is a mandatory field to '
                          'use this method, I am using /home/odoo/dev_log.log')
            path = '/home/odoo/dev_log.log'

        if filemode not in filemode_list:
            _logger.error("Unknown filemode, it should be one of the "
                          "following: {}".format(filemode_list))

        now = datetime.now()
        dt_string = now.strftime('%Y-%m-%d %H:%M:%S')

        try:
            file_object = codecs.open(path, filemode, 'utf-8')
            if not raw_error:
                file_object.write(f'[{dt_string}][{error_type}] {error}')
            else:
                file_object.write(f'{error}')

            file_object.close()
            return True
        except ModuleNotFoundError as e:
            _logger.debug(e)
            return False

    class QueueJob(models.Model):
        _inherit = 'queue.job'

        def failed_jobs_scheduled(self, minutes=60):
            """ Scheduled method which sends a digest of failed queue_jobs.
                TODO evaluate this
                |
                V
                The only jobs considered are those included in the class
                attribute tracking_remove. This because for those not included
                a notification was already sent
            """
            comparison_date = datetime.now() - timedelta(hours=minutes / 60)
            queue_job_obj = self.env['queue.job'].search(
                [
                    ('state', '=', 'failed'),
                    ('date_created', '>', comparison_date)
                ]
            )
            jobs = list()
            if queue_job_obj:
                for queue_job in queue_job_obj:
                    job_data = {'name': queue_job.name,
                                'model_name': queue_job.model_name,
                                'method_name': queue_job.method_name
                                }
                    jobs.append(job_data)

                unique_jobs = list()

                for job_ in jobs:
                    if job_ not in unique_jobs:
                        unique_jobs.append(job_)

                msg_body = ''
                for data in unique_jobs:
                    msg_body += \
                        "Job '{}' del modello '{}' che richiama il metodo " \
                        "'{}'\n".format(
                            data['name'],
                            data['model_name'],
                            data['method_name']
                        )
                msg_body = \
                    "Riepilogo dei job falliti negli ultimi {} " \
                    "minuti (controllare modello queue.job): " \
                    "\n{}".format(minutes, msg_body)

                self.env.company.notify('Riepilogo job errati ultima ora',
                                        'INFO',
                                        msg_body,
                                        'slack'
                                        )
