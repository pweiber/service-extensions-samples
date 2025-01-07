package main

import (
	"github.com/proxy-wasm/proxy-wasm-go-sdk/proxywasm"
	"github.com/proxy-wasm/proxy-wasm-go-sdk/proxywasm/types"
)

func main() {}

// vmContext is top-level per-VM context. We set the PluginContext factory here.
func init() {
	proxywasm.SetVMContext(&vmContext{})
}

// vmContext just spawns pluginContext when a new plugin instance is created.
type vmContext struct {
	types.DefaultVMContext
}

func (vc *vmContext) NewPluginContext(contextID uint32) types.PluginContext {
	return &pluginContext{}
}

// pluginContext spawns an HTTP context for each new HTTP stream.
type pluginContext struct {
	types.DefaultPluginContext
}

func (pc *pluginContext) NewHttpContext(contextID uint32) types.HttpContext {
	return &myHttpContext{}
}

// myHttpContext is per-stream.
type myHttpContext struct {
	types.DefaultHttpContext
}

// OnHttpRequestHeaders is called when Envoy receives the request headers.
func (ctx *myHttpContext) OnHttpRequestHeaders(numHeaders int, endOfStream bool) types.Action {
	// Always be a friendly proxy.
	proxywasm.AddHttpRequestHeader("Message", "hello")
	proxywasm.ReplaceHttpRequestHeader("Welcome", "warm")
	return types.ActionContinue
}

// OnHttpResponseHeaders is called when Envoy sends out the response headers.
func (ctx *myHttpContext) OnHttpResponseHeaders(numHeaders int, endOfStream bool) types.Action {
	// Conditionally add to a header value.
	msgValue, err := proxywasm.GetHttpResponseHeader("Message")
	if err != nil {
		proxywasm.LogCriticalf("failed to get 'Message' header: %v", err)
	} else if msgValue == "foo" {
		// If Message == "foo", add "bar" to the same header name
		proxywasm.AddHttpResponseHeader("Message", "bar")
	}
	// Unconditionally remove the "Welcome" header.
	proxywasm.RemoveHttpResponseHeader("Welcome")
	return types.ActionContinue
}
