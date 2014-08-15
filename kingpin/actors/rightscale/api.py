# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Copyright 2014 Nextdoor.com, Inc

"""Base RightScale API Access Object.

This package provides access to the RightScale API via Tornado-style
@gen.coroutine wrapped methods. These methods are, however, just wrappers
for threads that are being fired off in the background to make the API
calls.

In the future, this will get re-factored to use a native Tornado
AsyncHTTPClient object. The methods themselves will stay the same, but the
underlying private methods will change.

The methods in this object are specifically designed to support common
operations that the RightScale Actor objects need to do. Operations like
'find server array', 'launch server array', etc. This is not meant as a pure
one-to-one mapping of the RightScale API, but rather a mapping of conceptual
operations that the Actors need.
"""

import logging
import os

from tornado import gen
import futures

from rightscale import commands
from rightscale import util as rightscale_util
import rightscale


log = logging.getLogger(__name__)

__author__ = 'Matt Wise <matt@nextdoor.com>'


DEFAULT_ENDPOINT='https://my.rightscale.com'
THREADPOOL = futures.ThreadPoolExecutor(10)

@gen.coroutine
def thread_coroutine(func, *args, **kwargs):
    """Simple ThreadPool executor for Tornado.

    This method leverages the back-ported Python futures
    package (https://pypi.python.org/pypi/futures) to spin up
    a ThreadPool and then kick actions off in the thread pool.

    This is a simple and relatively graceful way of handling
    spawning off of synchronous API calls from the RightScale
    client below without having to do a full re-write of anything.

    This should not be used at high volume... but for the
    use case below, its reasonable.

    Example Usage:
        >>> @gen.coroutine
        ... def login(self):
        ...     ret = yield thread_coroutine(self._client.login)
        ...     raise gen.Return(ret)

    Args:
        func: Function reference
    """
    ret = yield THREADPOOL.submit(func, *args, **kwargs)
    raise gen.Return(ret)


class ServerArrayException(Exception):
    """Raised when an operation on or looking for a ServerArray fails"""


class RightScale(object):
    def __init__(self, token, api=DEFAULT_ENDPOINT):
        """Initializes the RightScaleOperator Object for a RightScale Account.

        Args:
            token: A RightScale RefreshToken
            api: API URL Endpoint
        """
        self._token = token
        self._api = api
        self._client = rightscale.RightScale(refresh_token=self._token,
                                             api_endpoint=self._api)
        log.debug('%s initialized (token=<hidden>, api=%s)' %
                  (self.__class__.__name__, api))

    @gen.coroutine
    def login(self):
        ret = yield thread_coroutine(self._client.login)
        raise gen.Return(ret)

    # TODO: Add 'dry' support here
    @gen.coroutine
    def find_server_arrays(self, name, exact=True):
        """Search for a list of RightScale Server Array by name and return the resources.

        Args:
            name: RightScale ServerArray Name
            exact: Return a single exact match, or multiple matching resources.

        Raises:
            gen.Return(rightscale.Resource object(s))
            ServerArrayException()
        """
        log.debug('Searching for ServerArrays matching: %s (exact match: %s)' %
                  (name, exact))

        ret = yield thread_coroutine(rightscale_util.find_by_name,
            self._client.server_arrays, name, exact=exact)

        if not ret:
            err = 'Could not find ServerArray matching name: %s' % name
            log.error(err)
            raise ServerArrayException(err)

        log.debug('Got ServerArray: %s' % ret)

        raise gen.Return(ret)
