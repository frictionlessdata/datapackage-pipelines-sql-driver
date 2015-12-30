# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import os
import io
import six
import sys
import json
import runpy
import tempfile
import unittest

from examples.resource import run


class TestResource(unittest.TestCase):

    # Helpers

    def setUp(self):

        # Export files
        _, self.export_schema = tempfile.mkstemp()
        _, self.export_data = tempfile.mkstemp()

        # Python version
        self.version = '%s_%s' % (sys.version_info.major, sys.version_info.minor)

    def tearDown(self):

        # Delete temp files
        try:
            os.remove(self.export_schema)
            os.remove(self.export_data)
        except Exception:
            pass

    # Tests

    def test(self):

        # Run example
        scope = run(
            table='resource_test_%s' % self.version,
            export_schema=self.export_schema,
            export_data=self.export_data)

        # Assert schema
        actual = json.load(io.open(self.export_schema, encoding='utf-8'))
        expected = json.load(io.open(scope['import_schema'], encoding='utf-8'))
        assert actual == expected

        # Assert data
        # TODO: parse csv
        actual = io.open(self.export_data, encoding='utf-8').read()
        expected = io.open(scope['import_data'], encoding='utf-8').read()
        assert actual == expected