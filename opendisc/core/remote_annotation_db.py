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

import requests
from traitlets import Bool, Dict, Instance, Unicode, default
from traitlets.config import Configurable, PyFileConfigLoader

import opendisc
from .annotation_db import AnnotationDB


class RemoteAnnotationDB(AnnotationDB, Configurable):
    """ An in-memory annotation database that pulls from a remote server.
    
    This local database pulls the annotation documents from a remote database,
    but supports efficient in-memory queries to avoid repeatedly hitting the
    remote server.
    
    The class contains no Python-specific annotation logic. For that,
    see `opendisc.kernel.trace.annotator`.
    """
    
    # URL of REST API supplying the annotations.
    api_url = Unicode().tag(config=True)
    
    # Private traits.
    _initialized = Bool(False)
    _all_loaded = Bool(False)
    _loaded = Dict()
    
    @classmethod
    def from_library_config(cls):
        """ Create annotation DB from library config file.
        """
        config_path = Path(opendisc.__file__).parent.joinpath("config.py")
        config = PyFileConfigLoader(str(config_path)).load_config()
        return cls(config=config)

    def load_package(self, package):
        """ Load annotations for the given Python package.
        
        If the package has already been loaded or does not exist in the remote
        database, then this method is a no-op (no request is made to the remote
        server). Thus, it is safe to call this method often.
        
        Returns whether annotations were loaded from the server.
        """
        if not self._prepare_load() or self._loaded.get(package, True):
            return False
        
        endpoint = "/annotations/python/{package}".format(package=package)
        self.load_documents(self._api_get(endpoint))
        self._loaded[package] = True
        return True
    
    def load_all_packages(self):
        """ Load annotations for all Python packages.
        
        Similarly to `load_package`, if the annotations have already been 
        loaded, then this method is a no-op.
        
        Returns whether annotations were loaded from the server.
        """
        if not self._prepare_load() or self._all_loaded:
            return False
        
        self.load_documents(self._api_get("/annotations/python"))
        self._all_loaded = True
        return True
    
    # Private interface

    def _api_get(self, endpoint):
        """ Make a GET request to the REST API.

        Returns the JSON response data.
        """
        response = requests.get(self.api_url + endpoint)
        return response.json()
    
    def _initialize(self):
        """ Initialize the annotation database by fetching the list of
        annotated Python packages from the remote server.
        
        Returns whether the annotation database was successfully initialized.
        """
        if not self.api_url:
            return False
        
        self._all_loaded = False
        self._loaded = {}
        for package in self._api_get("/count/annotation/python").keys():
            self._loaded[package] = False

        self._initialized = True
        return True
    
    def _prepare_load(self):
        """ Prepare to load annotations from the remote database.

        Returns whether annotations can be loaded.
        """
        return self._initialized or self._initialize()
