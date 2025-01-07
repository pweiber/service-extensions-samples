load("//:plugins.bzl", "proxy_wasm_plugin_cpp", "proxy_wasm_plugin_rust", "proxy_wasm_plugin_go", "proxy_wasm_tests")

licenses(["notice"])  # Apache 2

proxy_wasm_plugin_rust(
    name = "plugin_rust.wasm",
    srcs = ["plugin.rs"],
    deps = [
        "@crate_index//:log",
        "@crate_index//:proxy-wasm",
    ],
)

proxy_wasm_plugin_cpp(
    name = "plugin_cpp.wasm",
    srcs = ["plugin.cc"],
)

proxy_wasm_plugin_go(
    name = "plugin_go.wasm",
    srcs = ["plugin.go"],
    deps = [
        "@com_github_proxy_wasm_proxy_wasm_go_sdk//proxywasm:go_default_library",
        "@com_github_proxy_wasm_proxy_wasm_go_sdk//proxywasm/types:go_default_library",
    ],
)

proxy_wasm_tests(
    name = "tests",
    plugins = [
        ":plugin_cpp.wasm",
        ":plugin_rust.wasm",
        ":plugin_go.wasm",
    ],
    tests = ":tests.textpb",
)
