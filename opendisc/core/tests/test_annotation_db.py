# Copyright 2018 IBM Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import

from pathlib2 import Path
import unittest

from ..annotation_db import AnnotationDB


class TestAnnotationDB(unittest.TestCase):
    """ Test the in-memory annotation database on local annotations.
    """

    @classmethod
    def setUpClass(cls):
        json_path = Path(__file__).parent.joinpath('data', 'annotations.json')
        cls.db = AnnotationDB()
        cls.db.load_file(json_path)
    
    def test_basic_get(self):
        """ Test a simple, single-document query.
        """
        query = {'id': 'foo'}
        note = self.db.get(query)
        self.assertEqual(note['id'], 'foo')
        
        query = {'id': 'XXX'} # No matches
        self.assertEqual(self.db.get(query), None)
        
        query = {'kind': 'object'} # Multiple matches
        with self.assertRaises(LookupError):
            self.db.get(query)
    
    def test_basic_filter(self):
        """ Test a simple, multi-document query.
        """
        query = {'package': 'opendisc', 'id': 'foo'}
        notes = list(self.db.filter(query))
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['id'], 'foo')
    
    def test_or_operator(self):
        """ Tes that the `$or` query operator works.
        """
        query = {'$or': [{'id':'foo'}, {'id':'bar'}]}
        notes = list(self.db.filter(query))
        self.assertEqual(len(notes), 2)
    
    def test_in_operator(self):
        """ Test that the `$in` query operator works.
        """
        query = {'id': {'$in': ['foo', 'bar']}}
        notes = list(self.db.filter(query))
        self.assertEqual(len(notes), 2)


if __name__ == '__main__':
    unittest.main()
