# -*- coding: utf-8 -*-
{
    'name': 'A very simple notifications module',

    'summary': """
        A simple collection of methods for handling error notifications
        Use it in custom modules to send messages trought company object
        """,

    'description': """
        A simple collection of methods for handling error notifications.
        If you want to use it within your modules, remember to depend on him.
        """,

    'author': 'Giuseppe Checchia',
    'website': 'https://www.pausacaffe.live/',

    'category': 'Utility',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'queue_job'],

    'external_dependencies': {
        'python': ['sib-api-v3-sdk'],
    },

    # TODO add requirements if there's some extra dept to install before

    # always loaded
    'data': [
        'data/notification_data.xml',
        'security/ir.model.access.csv',
        'views/res_company_views_ext.xml'
    ],
}
