#!/Users/mendon.kissling/Documents/GitHub/langflow/testenv/lf-nightly/bin/python3

import datetime
import os
import sys
from getpass import getpass
from optparse import OptionParser

from peewee import *
from peewee import print_
from peewee import __version__ as peewee_version
from playhouse.cockroachdb import CockroachDatabase
from playhouse.reflection import *


HEADER = """from peewee import *%s

database = %s('%s'%s)
"""

BASE_MODEL = """\
class BaseModel(Model):
    class Meta:
        database = database
"""

UNKNOWN_FIELD = """\
class UnknownField(object):
    def __init__(self, *_, **__): pass
"""

DATABASE_ALIASES = {
    CockroachDatabase: ['cockroach', 'cockroachdb', 'crdb'],
    MySQLDatabase: ['mysql', 'mysqldb'],
    PostgresqlDatabase: ['postgres', 'postgresql'],
    SqliteDatabase: ['sqlite', 'sqlite3'],
}

DATABASE_MAP = dict((value, key)
                    for key in DATABASE_ALIASES
                    for value in DATABASE_ALIASES[key])

def make_introspector(database_type, database_name, **kwargs):
    if database_type not in DATABASE_MAP:
        err('Unrecognized database, must be one of: %s' %
            ', '.join(DATABASE_MAP.keys()))
        sys.exit(1)

    schema = kwargs.pop('schema', None)
    DatabaseClass = DATABASE_MAP[database_type]
    db = DatabaseClass(database_name, **kwargs)
    return Introspector.from_database(db, schema=schema)

def print_models(introspector, tables=None, preserve_order=False,
                 include_views=False, ignore_unknown=False, snake_case=True):
    database = introspector.introspect(table_names=tables,
                                       include_views=include_views,
                                       snake_case=snake_case)

    db_kwargs = introspector.get_database_kwargs()
    header = HEADER % (
        introspector.get_additional_imports(),
        introspector.get_database_class().__name__,
        introspector.get_database_name(),
        ', **%s' % repr(db_kwargs) if db_kwargs else '')
    print_(header)

    if not ignore_unknown:
        print_(UNKNOWN_FIELD)

    print_(BASE_MODEL)

    def _print_table(table, seen, accum=None):
        accum = accum or []
        foreign_keys = database.foreign_keys[table]
        for foreign_key in foreign_keys:
            dest = foreign_key.dest_table

            # In the event the destination table has already been pushed
            # for printing, then we have a reference cycle.
            if dest in accum and table not in accum:
                print_('# Possible reference cycle: %s' % dest)

            # If this is not a self-referential foreign key, and we have
            # not already processed the destination table, do so now.
            if dest not in seen and dest not in accum:
                seen.add(dest)
                if dest != table:
                    _print_table(dest, seen, accum + [table])

        print_('class %s(BaseModel):' % database.model_names[table])
        columns = database.columns[table].items()
        if not preserve_order:
            columns = sorted(columns)
        primary_keys = database.primary_keys[table]
        for name, column in columns:
            skip = all([
                name in primary_keys,
                name == 'id',
                len(primary_keys) == 1,
                column.field_class in introspector.pk_classes])
            if skip:
                continue
            if column.primary_key and len(primary_keys) > 1:
                # If we have a CompositeKey, then we do not want to explicitly
                # mark the columns as being primary keys.
                column.primary_key = False

            is_unknown = column.field_class is UnknownField
            if is_unknown and ignore_unknown:
                disp = '%s - %s' % (column.name, column.raw_column_type or '?')
                print_('    # %s' % disp)
            else:
                print_('    %s' % column.get_field())

        print_('')
        print_('    class Meta:')
        print_('        table_name = \'%s\'' % table)
        multi_column_indexes = database.multi_column_indexes(table)
        if multi_column_indexes:
            print_('        indexes = (')
            for fields, unique in sorted(multi_column_indexes):
                print_('            ((%s), %s),' % (
                    ', '.join("'%s'" % field for field in fields),
                    unique,
                ))
            print_('        )')

        if introspector.schema:
            print_('        schema = \'%s\'' % introspector.schema)
        if len(primary_keys) > 1:
            pk_field_names = sorted([
                field.name for col, field in columns
                if col in primary_keys])
            pk_list = ', '.join("'%s'" % pk for pk in pk_field_names)
            print_('        primary_key = CompositeKey(%s)' % pk_list)
        elif not primary_keys:
            print_('        primary_key = False')
        print_('')

        seen.add(table)

    seen = set()
    for table in sorted(database.model_names.keys()):
        if table not in seen:
            if not tables or table in tables:
                _print_table(table, seen)

def print_header(cmd_line, introspector):
    timestamp = datetime.datetime.now()
    print_('# Code generated by:')
    print_('# python -m pwiz %s' % cmd_line)
    print_('# Date: %s' % timestamp.strftime('%B %d, %Y %I:%M%p'))
    print_('# Database: %s' % introspector.get_database_name())
    print_('# Peewee version: %s' % peewee_version)
    print_('')


def err(msg):
    sys.stderr.write('\033[91m%s\033[0m\n' % msg)
    sys.stderr.flush()

def get_option_parser():
    parser = OptionParser(usage='usage: %prog [options] database_name')
    ao = parser.add_option
    ao('-H', '--host', dest='host')
    ao('-p', '--port', dest='port', type='int')
    ao('-u', '--user', dest='user')
    ao('-P', '--password', dest='password', action='store_true')
    engines = sorted(DATABASE_MAP)
    ao('-e', '--engine', dest='engine', choices=engines,
       help=('Database type, e.g. sqlite, mysql, postgresql or cockroachdb. '
             'Default is "postgresql".'))
    ao('-s', '--schema', dest='schema')
    ao('-t', '--tables', dest='tables',
       help=('Only generate the specified tables. Multiple table names should '
             'be separated by commas.'))
    ao('-v', '--views', dest='views', action='store_true',
       help='Generate model classes for VIEWs in addition to tables.')
    ao('-i', '--info', dest='info', action='store_true',
       help=('Add database information and other metadata to top of the '
             'generated file.'))
    ao('-o', '--preserve-order', action='store_true', dest='preserve_order',
       help='Model definition column ordering matches source table.')
    ao('-I', '--ignore-unknown', action='store_true', dest='ignore_unknown',
       help='Ignore fields whose type cannot be determined.')
    ao('-L', '--legacy-naming', action='store_true', dest='legacy_naming',
       help='Use legacy table- and column-name generation.')
    return parser

def get_connect_kwargs(options):
    ops = ('host', 'port', 'user', 'schema')
    kwargs = dict((o, getattr(options, o)) for o in ops if getattr(options, o))
    if options.password:
        kwargs['password'] = getpass()
    return kwargs


if __name__ == '__main__':
    raw_argv = sys.argv

    parser = get_option_parser()
    options, args = parser.parse_args()

    if len(args) < 1:
        err('Missing required parameter "database"')
        parser.print_help()
        sys.exit(1)

    connect = get_connect_kwargs(options)
    database = args[-1]

    tables = None
    if options.tables:
        tables = [table.strip() for table in options.tables.split(',')
                  if table.strip()]

    engine = options.engine
    if engine is None:
        engine = 'sqlite' if os.path.exists(database) else 'postgresql'

    introspector = make_introspector(engine, database, **connect)
    if options.info:
        cmd_line = ' '.join(raw_argv[1:])
        print_header(cmd_line, introspector)

    print_models(introspector, tables, options.preserve_order, options.views,
                 options.ignore_unknown, not options.legacy_naming)
