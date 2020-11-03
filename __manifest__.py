# -*- coding: utf-8 -*-
{
    'name': 'TPN - Third-party notifications',

    'summary': """
        A simple collection of methods for handling error notifications
        trought Sendinblue and/or Slack. Use it in your modules to send
        message using company object
        """,

    'description': """
        A simple collection of methods for handling error notifications trought
        Sendinblue and/or Slack. If you want to use it within your modules,
        remember to depend on him.
        """,

    'author': 'Giuseppe Checchia',
    'website': 'https://www.ordinatamente.com',

    'category': 'Utility',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    'external_dependencies': {
        'python': ['sib-api-v3-sdk', 'mysql-connector'],
    },

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/res_company_views_ext.xml'
    ],
}
