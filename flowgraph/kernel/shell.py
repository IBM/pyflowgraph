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

from IPython.core.interactiveshell import InteractiveShellABC
from ipykernel.zmqshell import ZMQInteractiveShell


class FlowGraphIPythonShell(ZMQInteractiveShell):
    """ InteractiveShell for use with FlowGraphIPythonKernel.
    
    Not intended for standalone use.
    """
    
    # `InteractiveShell` interface
    
    def run_code(self, code_obj, result=None):        
        # Delay tracing as long as possible. This is the method in the shell
        # that actually calls `exec()` on user code.
        if self.kernel._trace_flag:
            with self.kernel._tracer:
                return super(FlowGraphIPythonShell, self).run_code(
                    code_obj, result)
        else:
            return super(FlowGraphIPythonShell, self).run_code(
                code_obj, result)

    
InteractiveShellABC.register(FlowGraphIPythonShell)
