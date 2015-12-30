# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

from sqlalchemy import (
        Table, Column, MetaData,
        Text, TEXT, Integer, INTEGER, Float, FLOAT, Boolean, BOOLEAN)
from sqlalchemy.sql import select
from jsontableschema.model import SchemaModel


# Module API

class Storage(object):

    # Public

    def __init__(self, engine, dbschema=None, prefix=''):

        # Set attributes
        self.__engine = engine
        self.__dbschema = dbschema
        self.__prefix = prefix
        self.__tables = None

    def __repr__(self):

        # Template and format
        template = 'Storage <{engine}/{dbschema}>'
        text = template.format(
                engine=self.__engine,
                dbschema=self.__dbschema)

        return text

    @property
    def tables(self):

        if self.__tables is None:

            # Collect
            tables = []
            for table in self.__engine.table_names(schema=self.__dbschema):
                if table.startswith(self.__prefix):
                    table = table.replace(self.__prefix, '', 1)
                    tables.append(table)

            # Save
            self.__tables = tables

        return self.__tables

    def check(self, table):
        return table in self.tables

    def create(self, table, schema):
        """Create table by schema.

        Parameters
        ----------
        schema: dict
            BigQuery schema descriptor.

        Raises
        ------
        RuntimeError
            If table is already existent.

        """

        # Check not existent
        if self.check(table):
            message = 'Table "%s" is already existent.' % table
            raise RuntimeError(message)

        # Convert jts schema
        columns = self.__convert_schema(schema)

        # Create table
        name = self.__prefix + table
        dbtable = Table(name, MetaData(), *columns, schema=self.__dbschema)
        dbtable.create(self.__engine)

        # Remove tables cache
        self.__tables = None

    def delete(self, table):
        """Delete table.

        Raises
        ------
        RuntimeError
            If table is not existent.

        """

        # Check existent
        if not self.check(table):
            message = 'Table "%s" is not existent.' % self
            raise RuntimeError(message)

        # Drop table
        name = self.__prefix + table
        dbtable = Table(name, MetaData(), schema=self.__dbschema)
        dbtable.drop(self.__engine)

        # Remove tables cache
        self.__tables = None

    def describe(self, table):

        # Add prefix
        table = self.__prefix + table

        dbtable = Table(
                table, MetaData(),
                autoload=True, autoload_with=self.__engine,
                schema=self.__dbschema)

        # Get schema
        schema = self.__restore_schema(dbtable)

        return schema

    def read(self, table):

        # Add prefix
        table = self.__prefix + table

        table = Table(
                table, MetaData(),
                autoload=True, autoload_with=self.__engine,
                schema=self.__dbschema)

        conn = self.__engine.connect()
        result = conn.execute(select([table]))

        return list(result)

    def write(self, table, data):

        # Get model and data
        model = SchemaModel(self.describe(table))
        cdata = []
        for row in data:
            rdata = {}
            row = tuple(model.convert_row(*row))
            for index, field in enumerate(model.fields):
                rdata[field['name']] = row[index]
            cdata.append(rdata)

        # Add prefix
        table = self.__prefix + table

        table = Table(
                table, MetaData(),
                autoload=True, autoload_with=self.__engine,
                schema=self.__dbschema)

        ins = table.insert()
        conn = self.__engine.connect()
        conn.execute(ins, cdata)

    # Private

    def __convert_schema(self, schema):
        """Convert JSONTableSchema schema to SQLAlchemy columns.
        """

        # Mapping
        mapping = {
            'string': Text(),
            'integer': Integer(),
            'number': Float(),
            'boolean': Boolean(),
        }

        # Convert
        columns = []
        for field in schema['fields']:
            try:
                column_type = mapping[field['type']]
            except KeyError:
                message = 'Type %s is not supported' % field['type']
                raise TypeError(message)
            column = Column(field['name'], column_type)
            columns.append(column)

        return columns

    def __restore_schema(self, dbtable):
        """Convert SQLAlchemy table reflection to JSONTableSchema schema.
        """

        # Mapping
        mapping = {
            TEXT: 'string',
            INTEGER: 'integer',
            FLOAT: 'number',
            BOOLEAN: 'boolean',
        }

        # Convert
        fields = []
        for column in dbtable.columns:
            try:
                field_type = mapping[column.type.__class__]
            except KeyError:
                message = 'Type %s is not supported' % column.type
                raise TypeError(message)
            field = {'name': column.name, 'type': field_type}
            fields.append(field)
        schema = {'fields': fields}

        return schema