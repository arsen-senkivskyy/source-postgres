import backoff
import psycopg2.extras
import sys
import uuid
from copy import copy
from dal.queries.query_builder import get_query, get_max_value_query
from . keystrategy import KEY_STRATEGY
from dal.queries.consts import *
from .utils import *
from collections import OrderedDict


def _log_backoff(details):
    err = sys.exc_info()[1]
    print('Retrying (attempt %s) in %d seconds, after error %s: %s' % (
        details['tries'],
        details['wait'],
        err.pgcode or '',
        err.message
    ))


# Used for testing - this constant is overriden durring tests so that we don't
# actually have to wait for the retry
def _get_connect_timeout():
    return CONNECT_TIMEOUT


class Postgres(panoply.DataSource):

    def __init__(self, source, options):
        super(Postgres, self).__init__(source, options)
# TODO: break everything to 2 objects: conf and state
        self.source['destination'] = source.get('destination', DESTINATION)

        self.batch_size = source.get('__batchSize', BATCH_SIZE)
        tables = source.get('tables', [])
        self.tables = tables[:]
        self.index = 0
        self.connector = None
        self.state_id = None
        self.saved_state = {}
        self.current_keys = None
        self.inckey = source.get('inckey', '')
        self.incval = source.get('incval', '')

        state = source.get('state', {})
        self.index = state.get('last_index', 0)
        self.max_value = None

        # Remove the state object from the source definition
        # since it does not need to be saved on the source.
        self.source.pop('state', None)

    @backoff.on_exception(backoff.expo,
                          psycopg2.DatabaseError,
                          max_tries=MAX_RETRIES,
                          on_backoff=_log_backoff,
                          base=_get_connect_timeout)
    def read(self, batch_size=None):
        batch_size = batch_size or self.batch_size
        total = len(self.tables)
        if self.index >= total:
            return None  # no tables left, we're done

        schema, table = self.tables[self.index]['value'].split('.', 1)

        msg = 'Reading table {} ({}) out of {}'\
              .format(self.index + 1, table, total)
        self.progress(self.index + 1, total, msg)

        if not self.cursor:
            self.connector = connect(self.source)
            state = self.saved_state.get('last_value', None)

            if not self.current_keys:
                self.current_keys = self.get_table_metadata(
                    SQL_GET_KEYS,
                    schema,
                    table
                )

            if not self.current_keys:
                # Select first column if no pk, indexes found
                self.current_keys = self.get_table_metadata(
                    SQL_GET_COLUMNS,
                    schema,
                    table
                )[:1]

            self.current_keys = key_strategy(self.current_keys)

            if not self.max_value:
                self.max_value = self.get_max_value(schema, table, self.inckey)
            query_opts = self.get_query_opts(schema, table, state,
                                             self.max_value)

            q = get_query(**query_opts)
            self.execute('DECLARE cur CURSOR FOR {}'.format(q))

        # read n(=BATCH_SIZE) records from the table
        self.execute('FETCH FORWARD {} FROM cur'.format(batch_size))
        result = self.cursor.fetchall()

        self.state_id = str(uuid.uuid4())
        # Add __schemaname and __tablename to each row so it would be available
        # as `destination` parameter if needed and also in case multiple tables
        # are pulled into the same destination table.
        # state_id is also added in order to support checkpoints
        internals = dict(
            __tablename=table,
            __schemaname=schema,
            __state=self.state_id
        )
        result = [dict(r, **internals) for r in result]
        self.loaded += len(result)

        # no more rows for this table, clear and proceed to next table
        if not result:
            close_connection(self.connector)
            self.index += 1
            self.current_keys = None
            self.saved_state = {}
            self.max_value = None
        else:
            last_row = result[-1]
            self._save_last_values(last_row)
            self._report_state(self.index)

        return result

    def execute(self, query):
        self.log(query, "Loaded: %s" % self.loaded)
        try:
            self.cursor.execute(query)
        except psycopg2.DatabaseError as e:
            # We're ensuring that there is no connection or cursor objects
            # after an exception so that when we retry,
            # a new connection will be created.

            # Since we got an error, it will trigger backoff expo
            # We want the source to continue where it left off
            self.reset()
            print('Raise error {}'.format(e.message))
            raise e
        self.log("DONE", query)

    def get_query_opts(self, schema, table, state, max_value=None):
        query_opts = {
            'schema': schema,
            'table': table,
            'inckey': self.inckey,
            'incval': self.incval,
            'keys': self.current_keys,
            'state': state,
            'max_value': max_value
        }

        return query_opts

    def get_max_value(self, schema, table, column):
        if not column:
            return None

        query = get_max_value_query(column, schema, table)
        self.execute(query)

        return self.cursor.fetchall()[0]['max']

    def get_table_metadata(self, sql, schema, table):
        search_path = '"{}"."{}"'.format(schema, table)
        sql = sql.format(search_path)
        self.log(sql)
        self.execute(sql)

        return self.cursor.fetchall()

    def _save_last_values(self, last_row):
        keys = map(lambda x: x.get('attname'), self.current_keys)
        last_value = [(key, last_row.get(key)) for key in keys]
        last_value = OrderedDict(last_value)

        self.saved_state = {
            'last_value': last_value
        }

    def _report_state(self, current_index):
        state = {
            'last_index': current_index
        }
        self.state(self.state_id, state)


def key_strategy(keys):
    keys_copy = copy(keys)

    for strategy in KEY_STRATEGY:
        results = strategy(keys_copy)

        if results:
            return results

    return keys
