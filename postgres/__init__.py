import source

Stream = source.Postgres


CONFIG = {
    'title': 'Postgres (deprecated)',
    'icon': 'data:image/png;base64,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',  # noqa
    'params': [
        {
            'name': 'addr',
            'title': 'Host Address',
            'required': True,
            'ip_whitelist': True,
            'placeholder': 'Example: 192.168.0.15:5432/dbname',
            'help': 'The URL or IP address of your database server.' +
                ' We\'ll keep your credentials encrypted'
        },
        {
            'name': 'user',
            'title': 'Username',
            'required': True,
            'placeholder': 'Username',
            'help': 'Also kept encrypted'
        },
        {
            'name': 'password',
            'title': 'Password',
            'required': True,
            'type': 'password',
            'placeholder': 'Password',
            'help': 'Also kept encrypted'
        },
        {
            'name': 'tables',
            'title': 'Tables',
            'required': True,
            'type': 'list',
            'values': lambda s, o: Stream(s, o).get_tables(),
            'dependencies': ['addr', 'user', 'password'],
            'help': 'Select which tables you\'d like to import'
        }
    ],
    'categories': ['DB', 'POPULAR'],
    'keywords': ['db', 'database', 'sql'],
    'createdAt': '2017-07-11',
    'hostProperty': 'addr',
    'advanced': {
        'withIncremental': True
    }
}
