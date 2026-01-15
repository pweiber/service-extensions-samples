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
import multiprocessing

from grpc import ServicerContext
from envoy.service.ext_proc.v3 import external_processor_pb2 as service_pb2
from extproc.service import callout_server
from extproc.service import callout_tools


class CalloutServerExample(callout_server.CalloutServer):
  """Example callout server showing how to add text to a callout body.

  For request body callouts we return a mutation to append '-added-body' to
  the body. For response body callouts we send a mutation to replace the body
  with 'new-body'.
  """

  def on_request_body(
      self, body: service_pb2.HttpBody, context: ServicerContext
  ) -> service_pb2.BodyResponse:
    """Custom processor on the request body.

    Args:
      body (service_pb2.BodyResponse): The HTTP body received in the request.
      context (ServicerContext): The context object for the gRPC service.

    Returns:
      service_pb2.BodyResponse: The response containing the mutations to be applied
      to the request body.
    """
    return callout_tools.add_body_mutation(
        body.body.decode('utf-8') + '-added-request-body')

  def on_response_body(
      self, body: service_pb2.HttpBody, context: ServicerContext
  ) -> service_pb2.BodyResponse:
    """Custom processor on the response body.

        Args:
          body (service_pb2.BodyResponse): The HTTP body received in the response.
          context (ServicerContext): The context object for the gRPC service.

        Returns:
          service_pb2.BodyResponse: The response containing the mutations to be applied
          to the response body.
        """
    return callout_tools.add_body_mutation('new-body')


if __name__ == '__main__':
  # Required for multiprocessing, especially on Windows if frozen.
  multiprocessing.freeze_support()

  # Your original logging setup
  logging.basicConfig(level=logging.DEBUG)

  # Instantiate your server.
  # The base CalloutServer now handles parameters for ports, processes, and threads.
  # You can specify them or let the base class use its defaults.
  # For example, to run with default number of processes (CPU count on Linux/macOS, 1 on Windows)
  # and default gRPC threads per process (2), and specify ports:
  server = CalloutServerExample(
    plaintext_port=10001,  # Example: gRPC service on port 10001
    health_check_port=8088,  # Example: Health check on port 8088
    num_processes=1,       # Defaults to os.cpu_count() or 1 on Windows
    # server_thread_count=None  # Defaults to 2
  )

  # The run() method now triggers the multiprocessing logic from the base class.
  server.run()
