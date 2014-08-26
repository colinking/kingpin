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

"""Misc Actor objects"""

import logging
import os

from tornado import gen
from tornado import httpclient

from kingpin.actors import base
from kingpin.actors import exceptions

log = logging.getLogger(__name__)

__author__ = 'Matt Wise <matt@nextdoor.com>'


API_CONTENT_TYPE = 'application/json'
API_URL = 'https://api.hipchat.com/v1'
API_MESSAGE_PATH = '%s/rooms/message' % API_URL

TOKEN = os.getenv('HIPCHAT_TOKEN', None)
NAME = os.getenv('HIPCHAT_NAME', 'Kingpin')


class Message(base.HTTPBaseActor):
    """Simple Hipchat Message sending actor."""

    def __init__(self, *args, **kwargs):
        """Initializes the Actor.

        Args:
            desc: String description of the action being executed.
            options: Dictionary with the following settings:
              { 'room': <hipchat room name>,
                'message': <string of message to send>' }
        """
        super(Message, self).__init__(*args, **kwargs)

        if not TOKEN:
            raise exceptions.InvalidCredentials(
                'Missing the "HIPCHAT_TOKEN" environment variable.')

        for opt in ['room', 'message']:
            if opt not in self._options:
                raise exceptions.InvalidOptions('Missing "%s" option.' % opt)

        self._room = self._options['room']
        self._message = self._options['message']
        self._token = TOKEN
        self._name = self._validate_from_name(NAME)

    def _validate_from_name(self, name):
        """Parses and validates the FROM name.

        The username must be between 1 and 15 characters. If its not,
        we return a partial name to ensure that the push still works.

        Args:
            name: (Str) Proposed Hipchat message 'from' name

        Returns:
            A potentially modified string name thats valid.
        """
        return name[:15]

    def _build_potential_args(self, potential_args):
        """Builds a full set of arguments to pass to Hipchat.

        Appends the authentication token and a few other bits to the
        arguments supplied.

        Args:
            potential_Args: A hash of potential arguments.

        Returns:
            A larger hash of arguments.
        """
        potential_args['auth_token'] = self._token
        potential_args['from'] = self._name

        # If we're in 'dry run' mode, add the auth_test parameter
        if self._dry:
            potential_args['auth_test'] = True

        return potential_args

    @gen.coroutine
    def _fetch_wrapper(self, *args, **kwargs):
        """Wrap the superclass _fetch method to catch known Hipchat errors."""
        try:
            res = yield self._fetch(*args, **kwargs)
        except httpclient.HTTPError as e:
            if e.code == 401:
                # "The authentication you provided is invalid."
                raise exceptions.InvalidCredentials(
                    'The "HIPCHAT_TOKEN" supplied is invalid.')
            if e.code == 403:
                # "You have exceeded the rate limit"
                #
                # TODO: Build a retry mechanism in here with a sleep timer.
                self._log(logging.ERROR,
                          'Hit the HipChat API Rate Limit. Try again later.')
                raise
            raise

        raise gen.Return(res)

    @gen.coroutine
    def _execute(self):
        """Executes an actor and yields the results when its finished.

        raises: gen.Return(True)
        """
        self._log(logging.INFO, 'Sending message "%s" to Hipchat room "%s"' %
                  (self._message, self._room))
        res = yield self._post_message(self._room, self._message)

        # If we got here, the result is supposed to include 'success' as a key
        # and inside that key we can dig for the actual message. If the
        # response code is 202, we know that we didn't actually execute the
        # message send, but just validated the API token against the API.
        if 'success' in res:
            if res['success']['code'] == 202:
                self._log(logging.INFO, 'API Token Validated: %s' %
                          res['success']['message'])

        raise gen.Return(True)

    @gen.coroutine
    def _post_message(self, room_id, message,
                      message_format='html', notify=0,
                      color='yellow'):
        """Posts a message to Hipchat.

        https://www.hipchat.com/docs/api/method/rooms/message

        Args:
            room_id: (Str/Int) Name or ID of the room to post to.
            message: (Str) Required. The message body. 10,000 characters max.
            message_format: (Str) 'html' or 'text'.
            notify: (0/1) Whether or not this message should trigger a
                    notification for people in the room.
            color: (Str): Background color for message. One of "yellow", "red",
                          "green", "purple", "gray", or "random".

        Raises:
            gen.Return(<Dictionary of the response from Hipchat>)
        """
        args = self._build_potential_args({
            'room_id': room_id,
            'message': message,
            'message_format': message_format,
            'notify': notify,
            'color': color,
            'format': 'json',
        })
        url = self._generate_escaped_url(API_MESSAGE_PATH, args)
        res = yield self._fetch_wrapper(url)
        raise gen.Return(res)