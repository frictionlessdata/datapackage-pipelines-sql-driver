# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import os
import io
import json
import pytest
from copy import deepcopy
from tabulator import Stream
from tableschema import Schema
from sqlalchemy import create_engine
from tableschema_sql import Storage
from dotenv import load_dotenv; load_dotenv('.env')


# Tests

def test_storage():

    # Get resources
    articles_descriptor = json.load(io.open('data/articles.json', encoding='utf-8'))
    comments_descriptor = json.load(io.open('data/comments.json', encoding='utf-8'))
    articles_rows = Stream('data/articles.csv', headers=1).open().read()
    comments_rows = Stream('data/comments.csv', headers=1).open().read()

    # Engine
    engine = create_engine(os.environ['POSTGRES_URL'])

    # Storage
    storage = Storage(engine=engine, prefix='test_storage_')

    # Delete buckets
    storage.delete()

    # Create buckets
    storage.create(
            ['articles', 'comments'],
            [articles_descriptor, comments_descriptor],
            indexes_fields=[[['rating'], ['name'], ['created_datetime']], []])

    # Recreate bucket
    storage.create('comments', comments_descriptor, force=True)

    # Write data to buckets
    storage.write('articles', articles_rows)
    gen = storage.write('comments', comments_rows, as_generator=True)
    lst = list(gen)
    assert len(lst) == 1

    # Create new storage to use reflection only
    storage = Storage(engine=engine, prefix='test_storage_')

    # Create existent bucket
    with pytest.raises(RuntimeError):
        storage.create('articles', articles_descriptor)

    # Assert representation
    assert repr(storage).startswith('Storage')

    # Assert buckets
    assert storage.buckets == ['articles', 'comments']

    # Assert descriptors
    assert storage.describe('articles') == sync_descriptor(articles_descriptor)
    assert storage.describe('comments') == sync_descriptor(comments_descriptor)

    # Assert rows
    assert list(storage.read('articles')) == sync_rows(articles_descriptor, articles_rows)
    assert list(storage.read('comments')) == sync_rows(comments_descriptor, comments_rows)

    # Delete non existent bucket
    with pytest.raises(RuntimeError):
        storage.delete('non_existent')


    # Delete buckets
    storage.delete()


def test_storage_update():


    # Get resources
    descriptor = json.load(io.open('data/original.json', encoding='utf-8'))
    original_rows = Stream('data/original.csv', headers=1).open().read()
    update_rows = Stream('data/update.csv', headers=1).open().read()
    update_keys = ['person_id', 'name']

    # Engine
    engine = create_engine(os.environ['POSTGRES_URL'])

    # Storage
    storage = Storage(engine=engine, prefix='test_update_', autoincrement='__id')

    # Delete buckets
    storage.delete()

    # Create buckets
    storage.create('colors', descriptor)


    # Write data to buckets
    storage.write('colors', original_rows, update_keys=update_keys)

    gen = storage.write('colors', update_rows, update_keys=update_keys, as_generator=True)
    gen = list(gen)
    assert len(gen) == 5
    assert len(list(filter(lambda i: i.updated, gen))) == 3
    assert list(map(lambda i: i.updated_id, gen)) == [5, 3, 6, 4, 5]

    storage = Storage(engine=engine, prefix='test_update_', autoincrement='__id')
    gen = storage.write('colors', update_rows, update_keys=update_keys, as_generator=True)
    gen = list(gen)
    assert len(gen) == 5
    assert len(list(filter(lambda i: i.updated, gen))) == 5
    assert list(map(lambda i: i.updated_id, gen)) == [5, 3, 6, 4, 5]

    # Create new storage to use reflection only
    storage = Storage(engine=engine, prefix='test_update_')

    rows = list(storage.iter('colors'))

    assert len(rows) == 6
    color_by_person = dict(
        (row[1], row[3])
        for row in rows
    )
    assert color_by_person == {
        1: 'blue',
        2: 'green',
        3: 'magenta',
        4: 'sunshine',
        5: 'peach',
        6: 'grey'
    }

    # Storage without autoincrement
    storage = Storage(engine=engine, prefix='test_update_')
    storage.delete()
    storage.create('colors', descriptor)

    storage.write('colors', original_rows, update_keys=update_keys)
    gen = storage.write('colors', update_rows, update_keys=update_keys, as_generator=True)
    gen = list(gen)
    assert len(gen) == 5
    assert len(list(filter(lambda i: i.updated, gen))) == 3
    assert list(map(lambda i: i.updated_id, gen)) == [None, None, None, None, None]


def test_storage_bad_type():

    # Engine
    engine = create_engine(os.environ['POSTGRES_URL'])

    # Storage
    storage = Storage(engine=engine, prefix='test_bad_type_')
    with pytest.raises(TypeError):
        storage.create('bad_type', {
            'fields': [
                {
                    'name': 'bad_field',
                    'type': 'any'
                }
            ]
        })


def test_storage_only_parameter():
    # Check the 'only' parameter

    # Get resources
    simple_descriptor = json.load(io.open('data/simple.json', encoding='utf-8'))

    # Engine
    engine = create_engine(os.environ['POSTGRES_URL'], echo=True)

    # Storage
    storage = Storage(engine=engine, prefix='test_only_')

    # Delete buckets
    storage.delete()

    # Create buckets
    storage.create(
            'names',
            simple_descriptor,
            indexes_fields=[['person_id']])

    def only(table):
        ret = 'name' not in table
        return ret
    engine = create_engine(os.environ['POSTGRES_URL'], echo=True)
    storage = Storage(engine=engine, prefix='test_only_', reflect_only=only)
    # Delete non existent bucket
    with pytest.raises(RuntimeError):
        storage.delete('names')


def test_storage_bigdata():

    # Generate schema/data
    descriptor = {'fields': [{'name': 'id', 'type': 'integer'}]}
    rows = [{'id': value} for value in range(0, 2500)]

    # Push rows
    engine = create_engine(os.environ['POSTGRES_URL'])
    storage = Storage(engine=engine, prefix='test_storage_bigdata_')
    storage.create('bucket', descriptor, force=True)
    storage.write('bucket', rows, keyed=True)

    # Pull rows
    assert list(storage.read('bucket')) == list(map(lambda x: [x['id']], rows))


def test_storage_bigdata_rollback():

    # Generate schema/data
    descriptor = {'fields': [{'name': 'id', 'type': 'integer'}]}
    rows = [(value,) for value in range(0, 2500)] + [('bad-value',)]

    # Push rows
    engine = create_engine(os.environ['POSTGRES_URL'])
    storage = Storage(engine=engine, prefix='test_storage_bigdata_rollback_')
    storage.create('bucket', descriptor, force=True)
    try:
        storage.write('bucket', rows)
    except Exception:
        pass

    # Pull rows
    assert list(storage.read('bucket')) == []


# Helpers

def sync_descriptor(descriptor):
    descriptor = deepcopy(descriptor)
    for field in descriptor['fields']:
        if field['type'] in ['array', 'geojson']:
            field['type'] = 'object'
        if 'format' in field:
            del field['format']
    return descriptor


def sync_rows(descriptor, rows):
    result = []
    schema = Schema(descriptor)
    for row in rows:
        result.append(schema.cast_row(row))
    return result
