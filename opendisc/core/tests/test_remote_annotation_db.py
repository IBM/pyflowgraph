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

import unittest

from ..remote_annotation_db import RemoteAnnotationDB


class TestRemoteAnnotationDB(unittest.TestCase):
    """ Test the in-memory annotation database connected to a remote database.
    """

    @classmethod
    def setUpClass(cls):
        cls.db = RemoteAnnotationDB.from_library_config()
    
    def test_load_package(self):
        """ Test loading annotations for a single package.
        """
        query = {
            "language": "python",
            "package": "pandas",
        }
        docs = list(self.db.filter(query))
        self.assertEqual(docs, [])
        
        self.assertTrue(self.db.load_package("python", "pandas"))
        docs = list(self.db.filter(query))
        self.assertGreater(len(docs), 0)
        
        ids = [ doc['id'] for doc in docs ]
        self.assertTrue('series' in ids)
        self.assertTrue('data-frame' in ids)
        
        # Don't load twice!
        self.assertFalse(self.db.load_package("python", "pandas"))
    
    def test_load_unannotated_package(self):
        """ Test that no requests are made for unannotated packages.
        """
        self.assertFalse(self.db.load_package("python", "XXX"))
