import sqlite3

class Config:
    def __init__(self, config_dict, logger):
        self.config_dict = config_dict
        self.log = logger

        # verify safety of db table names
        self._scrub(self.config_dict['t_list'])
        self._scrub(self.config_dict['t_membership'])
        self._scrub(self.config_dict['t_owner'])
        self._scrub(self.config_dict['t_confirm'])

        self.db_conn = sqlite3.connect(self.db_file)
        self.log.debug("Connected to DB: %s" % self.db_file)

    def _scrub(self, string):
        """ Make sure the string is alphanumeric. We do this to sanitize our
        table names (since DB-API parameter substitution doesn't work for table
        names). """
        if not string.isalnum():
            raise ValueError("Table name cannot include non-alphanumerics.")
        return string

    @property
    def allow_list_creation(self):
        return self.config_dict['allow_list_creation'] is True

    @property
    def t_list(self):
        return self._scrub(self.config_dict['t_list'])

    @property
    def t_membership(self):
        return self._scrub(self.config_dict['t_membership'])

    @property
    def t_owner(self):
        return self._scrub(self.config_dict['t_owner'])

    @property
    def t_confirm(self):
        return self._scrub(self.config_dict['t_confirm'])

    @property
    def t_name(self):
        return self._scrub(self.config_dict['t_name'])

    @property
    def sender_type(self):
        return self.config_dict['sender_type']

    @property
    def db_file(self):
        return self.config_dict['db_file']

    @property
    def cmd_char(self):
        return self.config_dict['command_char']

    @property
    def app_number(self):
        return self.config_dict['app_number']

    @property
    def min_shortcode(self):
        return self.config_dict['min_shortcode']

    @property
    def max_shortcode(self):
        return self.config_dict['max_shortcode']
