# Copyright 2013 Red Hat, Inc.
# Copyright 2013 New Dream Network, LLC (DreamHost)
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import eventlet
from eventlet import greenpool
import greenlet

from oslo.config import cfg

from oslo.messaging._executors import base
from oslo.messaging.openstack.common import excutils

_eventlet_opts = [
    cfg.IntOpt('rpc_thread_pool_size',
               default=64,
               help='Size of RPC greenthread pool'),
]


class EventletExecutor(base.ExecutorBase):

    """A message exector which integrates with eventlet.

    This is an executor which polls for incoming messages from a greenthread
    and dispatches each message in its own greenthread.

    The stop() method kills the message polling greenthread and the wait()
    method waits for all message dispatch greenthreads to complete.
    """

    def __init__(self, conf, listener, callback):
        super(EventletExecutor, self).__init__(conf, listener, callback)
        self.conf.register_opts(_eventlet_opts)
        self._thread = None
        self._greenpool = greenpool.GreenPool(self.conf.rpc_thread_pool_size)

    def start(self):
        if self._thread is not None:
            return

        @excutils.forever_retry_uncaught_exceptions
        def _executor_thread():
            try:
                while True:
                    incoming = self.listener.poll()
                    self._greenpool.spawn_n(self._dispatch, incoming)
            except greenlet.GreenletExit:
                return

        self._thread = eventlet.spawn(_executor_thread)

    def stop(self):
        if self._thread is None:
            return
        self._thread.kill()

    def wait(self):
        if self._thread is None:
            return
        self._greenpool.waitall()
        try:
            self._thread.wait()
        except greenlet.GreenletExit:
            pass
        self._thread = None
