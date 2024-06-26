# Copyright 2024 Google LLC.
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

import logging
from google.auth import compute_engine
import google.cloud.logging

from grpc import ServicerContext
from envoy.service.ext_proc.v3 import external_processor_pb2 as service_pb2
from extproc.service import callout_server
from extproc.service import callout_tools


class CalloutServerExample(callout_server.CalloutServer):
  """Example callout server.

  For request header callouts we check the content of the request and
  authorize the request or reject the request.
  The content being checked is if the header has the header 'header-check'.
  The decision is logged to Cloud Logging.

  For request body callouts we check the content of the request and
  authorize the request or reject the request.
  The content being checked is if the body contains the body 'body-check'.
  The decision is logged to Cloud Logging.
  """

  def on_request_headers(
    self, headers: service_pb2.HttpHeaders, context: ServicerContext
  ) -> service_pb2.HeadersResponse:
    """Custom processor on request headers.

    Args:
      headers (service_pb2.HttpHeaders): The HTTP headers received in the request.
      context (ServicerContext): The context object for the gRPC service.

    Returns:
      service_pb2.HeadersResponse: The response containing the mutations to be applied
      to the request headers.
    """
    if not callout_tools.header_contains(headers, 'header-check'):
      callout_tools.deny_callout(
        context, '"header-check" not found within the request headers'
      )
    return callout_tools.add_header_mutation(
      add=[('header-request', 'request')], clear_route_cache=True
    )

  def on_request_body(
    self, body: service_pb2.HttpBody, context: ServicerContext
  ) -> service_pb2.BodyResponse:
    """Custom processor on the request body.

    Args:
      body (service_pb2.HttpBody): The HTTP body received in the request.
      context (ServicerContext): The context object for the gRPC service.

    Returns:
      service_pb2.BodyResponse: The response containing the mutations to be applied
      to the response body.
    """
    if not callout_tools.body_contains(body, 'body-check'):
      callout_tools.deny_callout(
        context, '"body-check" not found within the request body'
      )
    return callout_tools.add_body_mutation(body='replaced-body')

if __name__ == '__main__':
  """Sets up Google Cloud Logging for the cloud_log example"""
  # Local logging settings.
  logging.basicConfig(level=logging.DEBUG)
  # Example logging setup, not intended for production.
  # Please see https://google-auth.readthedocs.io/en/latest/.
  client = google.cloud.logging.Client(
    project='test-project', credentials=compute_engine.Credentials()
  )
  client.setup_logging()
  # Run the gRPC service
  CalloutServerExample().run()
