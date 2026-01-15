// Copyright 2025 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <grpcpp/grpcpp.h>

#include <boost/asio.hpp>
#include <boost/beast.hpp>

#include "absl/flags/flag.h"
#include "absl/flags/parse.h"
#include "absl/log/log.h"
#include "callout_server.h"
#include "custom_callout_server.h"

ABSL_FLAG(std::string, server_address, "0.0.0.0:443",
          "The gRPC server address, like '0.0.0.0:443'");
ABSL_FLAG(std::string, plaintext_address, "0.0.0.0:8080",
          "The plaintext gRPC server address, like '0.0.0.0:8080'");
ABSL_FLAG(bool, disable_plaintext, false,
          "Whether to disable plaintext gRPC server");
ABSL_FLAG(uint16_t, health_check_port, 80,
          "The HTTP health check server port");
ABSL_FLAG(std::string, private_key_path, "ssl_creds/privatekey.pem",
          "The SSL private key file path");
ABSL_FLAG(std::string, cert_chain_path, "ssl_creds/chain.pem",
          "The SSL certificate file path");
ABSL_FLAG(bool, disable_tls, true,
          "Whether to disable secure TLS gRPC server");

void StartHttpHealthCheckServer(uint16_t port) {
  namespace beast = boost::beast;
  namespace http = beast::http;
  namespace asio = boost::asio;
  using tcp = asio::ip::tcp;

  asio::io_context io_context;
  tcp::acceptor acceptor(io_context, {tcp::v4(), port});

  LOG(INFO) << "Health check service started on port: " << port;

  while (true) {
    try {
      tcp::socket socket(io_context);
      acceptor.accept(socket);

      beast::flat_buffer buffer;
      http::request<http::string_body> request;

      beast::error_code ec;
      http::read(socket, buffer, request, ec);

      if (ec) {
        LOG(WARNING) << "Error reading HTTP request: " << ec.message();
        continue;
      }

      http::response<http::string_body> response;
      response.version(request.version());
      response.result(http::status::ok);
      response.set(http::field::content_type, "text/plain");
      response.body() = "OK";
      response.prepare_payload();

      http::write(socket, response, ec);
      if (ec) {
        LOG(WARNING) << "Error writing HTTP response: " << ec.message();
      }

      socket.shutdown(tcp::socket::shutdown_send, ec);
      if (ec) {
        LOG(WARNING) << "Error shutting down socket: " << ec.message();
      }
    } catch (const std::exception& e) {
      LOG(ERROR) << "Exception in health check server: " << e.what();
    }
  }
}

int main(int argc, char** argv) {
  absl::ParseCommandLine(argc, argv);

  auto config = CalloutServer::DefaultConfig();
  config.secure_address = absl::GetFlag(FLAGS_server_address);
  config.private_key_path = absl::GetFlag(FLAGS_private_key_path);
  config.cert_chain_path = absl::GetFlag(FLAGS_cert_chain_path);

  // Set plaintext configuration
  config.disable_plaintext = absl::GetFlag(FLAGS_disable_plaintext);
  config.plaintext_address = absl::GetFlag(FLAGS_plaintext_address);

  // Set TLS configuration
  config.disable_tls = absl::GetFlag(FLAGS_disable_tls);

  if (config.disable_plaintext && config.disable_tls) {
    LOG(ERROR) << "No valid configuration: at least one of plaintext "
                  "or TLS must be enabled";
    return 1;
  }

  std::thread health_check_thread(StartHttpHealthCheckServer,
                                  absl::GetFlag(FLAGS_health_check_port));

  CalloutServer::RunServers<CustomCalloutServer>(config);

  boost::asio::io_context io_context;
  boost::asio::signal_set signals(io_context, SIGINT, SIGTERM);
  signals.async_wait([&](auto, auto) {
    CalloutServer::Shutdown();
    io_context.stop();
  });

  io_context.run();

  CalloutServer::WaitForCompletion();
  health_check_thread.join();

  return 0;
}