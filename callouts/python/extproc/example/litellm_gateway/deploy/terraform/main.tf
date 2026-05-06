# Copyright 2026 Google LLC.
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

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.15.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = ">= 4.0.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "project" {
  project_id = var.project_id
}

# ===================================================================
# ENABLE REQUIRED APIS
# ===================================================================

resource "google_project_service" "apis" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "networkservices.googleapis.com",
    "run.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}

# ===================================================================
# SERVICE ACCOUNT — CALLOUT (fetches Vertex AI Bearer tokens via ADC)
# ===================================================================
#
# The Python callout calls the GCE metadata server to mint short-lived
# OAuth tokens, then injects them as `Authorization: Bearer …` headers.
# The SA therefore needs roles/aiplatform.user.
#
# By default the project's default compute SA is used (has roles/editor,
# sufficient for Vertex). For tighter scoping set var.callout_service_account.

locals {
  callout_service_account = coalesce(
    var.callout_service_account,
    "${data.google_project.project.number}-compute@developer.gserviceaccount.com",
  )
}

# ===================================================================
# CLOUD RUN — CALLOUT (Python ext_proc service)
# ===================================================================

resource "google_cloud_run_v2_service" "callout" {
  name                = "litellm-gateway-callout"
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = local.callout_service_account

    containers {
      name  = "callout"
      image = var.callout_image
      ports {
        name           = "h2c"
        container_port = 8080
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "SEC_KEYWORDS"
        value = var.sec_keywords
      }
      env {
        name  = "ALLOWED_MODELS"
        value = var.allowed_models
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
      startup_probe {
        http_get {
          path = "/"
          port = 80
        }
        initial_delay_seconds = 5
        period_seconds        = 5
        failure_threshold     = 3
      }
      liveness_probe {
        http_get {
          path = "/"
          port = 80
        }
        period_seconds = 10
      }
    }

    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "callout_public_invoker" {
  name     = google_cloud_run_v2_service.callout.name
  location = google_cloud_run_v2_service.callout.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_compute_region_network_endpoint_group" "callout_neg" {
  name                  = "litellm-gateway-callout-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = google_cloud_run_v2_service.callout.name
  }
}

# Global backend service — serverless NEGs must not specify balancing_mode.
resource "google_compute_backend_service" "callout_backend" {
  name                  = "litellm-gateway-callout-be"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTP2"
  backend {
    group = google_compute_region_network_endpoint_group.callout_neg.id
  }
}

# ===================================================================
# CLOUD RUN — UPSTREAM APPLICATION (non-LLM traffic)
# ===================================================================

resource "google_cloud_run_v2_service" "upstream_app" {
  name                = "litellm-gateway-upstream"
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = var.upstream_app_image
      ports {
        container_port = 8080
      }
    }
    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "upstream_public_invoker" {
  name     = google_cloud_run_v2_service.upstream_app.name
  location = google_cloud_run_v2_service.upstream_app.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_compute_region_network_endpoint_group" "upstream_neg" {
  name                  = "litellm-gateway-upstream-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = google_cloud_run_v2_service.upstream_app.name
  }
}

resource "google_compute_backend_service" "upstream_backend" {
  name                  = "litellm-gateway-upstream-be"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTPS"
  backend {
    group = google_compute_region_network_endpoint_group.upstream_neg.id
  }
}

# ===================================================================
# VERTEX AI BACKEND — GLOBAL INTERNET NEG (HTTPS to aiplatform.googleapis.com)
# ===================================================================
#
# Global external Application LB automatically rewrites the Host header to
# the FQDN of the Internet NEG endpoint — unlike regional LBs which pass
# the client's Host through unchanged.  This means the callout only needs
# to rewrite :path and inject Authorization; no :authority override is needed.

resource "google_compute_global_network_endpoint_group" "vertex_neg" {
  name                  = "litellm-gateway-vertex-neg"
  network_endpoint_type = "INTERNET_FQDN_PORT"
  default_port          = 443
  depends_on            = [google_project_service.apis]
}

resource "google_compute_global_network_endpoint" "vertex_endpoint" {
  global_network_endpoint_group = google_compute_global_network_endpoint_group.vertex_neg.name
  fqdn                          = "${var.region}-aiplatform.googleapis.com"
  port                          = 443
}

resource "google_compute_backend_service" "vertex_backend" {
  name                  = "litellm-gateway-vertex-be"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTPS"
  timeout_sec           = 180

  backend {
    group           = google_compute_global_network_endpoint_group.vertex_neg.id
    balancing_mode  = "UTILIZATION"
    capacity_scaler = 1.0
  }

  depends_on = [google_compute_global_network_endpoint.vertex_endpoint]
}


# ===================================================================
# LOAD BALANCER — GLOBAL EXTERNAL HTTPS APPLICATION LB
# ===================================================================

resource "google_compute_global_address" "lb_ip" {
  name = "litellm-gateway-lb-ip"
}

resource "tls_private_key" "lb_key" {
  algorithm = "RSA"
}

resource "tls_self_signed_cert" "lb_cert" {
  private_key_pem = tls_private_key.lb_key.private_key_pem
  subject {
    common_name = "litellm-gateway.example.com"
  }
  validity_period_hours = 8760 # 1 year
  allowed_uses          = ["server_auth"]
}

resource "google_compute_ssl_certificate" "lb_cert" {
  name        = "litellm-gateway-cert"
  private_key = tls_private_key.lb_key.private_key_pem
  certificate = tls_self_signed_cert.lb_cert.cert_pem
}

# URL map: LLM paths → Vertex backend; everything else → upstream app.
resource "google_compute_url_map" "url_map" {
  name            = "litellm-gateway-url-map"
  default_service = google_compute_backend_service.upstream_backend.id

  host_rule {
    hosts        = ["*"]
    path_matcher = "llm"
  }

  path_matcher {
    name            = "llm"
    default_service = google_compute_backend_service.upstream_backend.id

    # route_action with url_rewrite.host_rewrite is required for EXTERNAL_MANAGED
    # global LBs — unlike classic global LBs, they do not auto-rewrite the Host
    # header to the Internet NEG FQDN.  The rewrite is applied after any
    # clear_route_cache re-evaluation triggered by the Traffic Extension.

    route_rules {
      priority = 1
      match_rules {
        prefix_match = "/v1/"
      }
      route_action {
        weighted_backend_services {
          backend_service = google_compute_backend_service.vertex_backend.id
          weight          = 100
        }
        url_rewrite {
          host_rewrite = "${var.region}-aiplatform.googleapis.com"
        }
      }
    }
  }
}

resource "google_compute_target_https_proxy" "https_proxy" {
  name             = "litellm-gateway-https-proxy"
  url_map          = google_compute_url_map.url_map.id
  ssl_certificates = [google_compute_ssl_certificate.lb_cert.id]
}

resource "google_compute_global_forwarding_rule" "forwarding_rule" {
  name                  = "litellm-gateway-fwd-rule"
  port_range            = "443"
  target                = google_compute_target_https_proxy.https_proxy.id
  ip_address            = google_compute_global_address.lb_ip.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# ===================================================================
# SERVICE EXTENSIONS — TRAFFIC EXTENSION (intercepts LLM paths)
# ===================================================================
#
# The Python callout handles all four phases:
#   REQUEST_HEADERS  — marks the stream as LLM, sets x-litellm-routed
#   REQUEST_BODY     — transforms OpenAI → Vertex, rewrites :path/Authorization
#   RESPONSE_HEADERS — removes content-length (Vertex's value is stale post-transform)
#   RESPONSE_BODY    — transforms Vertex → OpenAI (buffered or SSE streaming)

resource "google_network_services_lb_traffic_extension" "callout" {
  name                  = "litellm-gateway-traffic-ext"
  location              = "global"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  forwarding_rules = [
    google_compute_global_forwarding_rule.forwarding_rule.self_link
  ]
  extension_chains {
    name = "litellm-gateway-chain"
    match_condition {
      cel_expression = "request.path in ['/v1/chat/completions', '/v1/completions', '/v1/embeddings', '/v1/models', '/chat/completions', '/completions', '/embeddings']"
    }
    extensions {
      name             = "litellm-gateway-callout"
      service          = google_compute_backend_service.callout_backend.self_link
      authority        = "litellm-gateway.example.com"
      supported_events = ["REQUEST_HEADERS", "REQUEST_BODY", "RESPONSE_HEADERS", "RESPONSE_BODY"]
      timeout          = "10s"
    }
  }
  depends_on = [google_project_service.apis]
}

# ===================================================================
# OUTPUTS
# ===================================================================

output "load_balancer_ip" {
  description = "The external IP address of the load balancer."
  value       = google_compute_global_address.lb_ip.address
}

output "callout_service_url" {
  description = "The URL of the Python ext_proc callout Cloud Run service."
  value       = google_cloud_run_v2_service.callout.uri
}

output "upstream_service_url" {
  description = "The URL of the upstream application Cloud Run service."
  value       = google_cloud_run_v2_service.upstream_app.uri
}

output "vertex_endpoint" {
  description = "The Vertex AI FQDN this deployment forwards LLM requests to."
  value       = "${var.region}-aiplatform.googleapis.com"
}

output "curl_test_command" {
  description = "Example curl command to test the LiteLLM gateway through the load balancer."
  value       = <<-EOT
    curl -sk -X POST https://${google_compute_global_address.lb_ip.address}/v1/chat/completions \
      -H "Content-Type: application/json" \
      -d '{"model": "vertex_ai/gemini-2.5-flash", "messages": [{"role": "user", "content": "Hello"}]}'
  EOT
}
