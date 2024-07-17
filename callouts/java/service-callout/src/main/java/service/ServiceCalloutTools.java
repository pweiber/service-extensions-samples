package service;

/*
 * Copyright 2015 The gRPC Authors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import com.google.common.collect.ImmutableListMultimap;
import com.google.protobuf.ByteString;
import io.envoyproxy.envoy.config.core.v3.HeaderValue;
import io.envoyproxy.envoy.config.core.v3.HeaderValueOption;
import io.envoyproxy.envoy.service.ext_proc.v3.*;
import io.envoyproxy.envoy.type.v3.HttpStatus;

import java.util.Map;


/**
 * ServiceCalloutTools provides utility methods for handling HTTP header and body mutations in service callouts.
 */
public class ServiceCalloutTools {

    /**
     * Adds header mutations to the response builder.
     *
     * @param headersResponseBuilder Builder for modifying response headers
     * @param add                    Iterable containing header key-value pairs to be added
     */
    public static HeadersResponse addHeaderMutations(
            HeadersResponse.Builder headersResponseBuilder, Iterable<Map.Entry<String, String>> add) {
        if (add != null) {
            HeaderMutation.Builder headerMutationBuilder =
                    headersResponseBuilder.getResponseBuilder().getHeaderMutationBuilder();
            for (Map.Entry<String, String> entry : add) {
                headerMutationBuilder
                        .addSetHeadersBuilder()
                        .getHeaderBuilder()
                        .setKey(entry.getKey())
                        .setValue(entry.getValue())
                        .setRawValue(ByteString.copyFromUtf8(entry.getValue()));
            }
        }
        return headersResponseBuilder.build();
    }

    /**
     * Configures the headers response.
     *
     * @param headersResponseBuilder Builder for modifying response headers
     * @param add                    Iterable containing header value options to be added
     * @param remove                 Iterable containing header keys to be removed
     * @param clearRouteCache        Boolean indicating whether to clear the route cache
     * @return Constructed HeadersResponse object
     */
    public static HeadersResponse configureHeadersResponse(
            HeadersResponse.Builder headersResponseBuilder,
            Iterable<HeaderValueOption> add,
            Iterable<String> remove,
            Boolean clearRouteCache) {
        CommonResponse.Builder responseBuilder = headersResponseBuilder.getResponseBuilder();
        HeaderMutation.Builder headerBuilder = responseBuilder.getHeaderMutationBuilder();
        if (add != null) {
            headerBuilder.addAllSetHeaders(add);
        }
        if (remove != null) {
            headerBuilder.addAllRemoveHeaders(remove);
        }
        if (clearRouteCache != null) {
            responseBuilder.setClearRouteCache(clearRouteCache);
        }
        return headersResponseBuilder.build();
    }

    /**
     * Builds a body mutation response.
     *
     * @param bodyResponseBuilder Builder for modifying response body
     * @param body                The body content to be set
     * @param clearBody           Boolean indicating whether to clear the body
     * @param clearRouteCache     Boolean indicating whether to clear the route cache
     * @return Constructed BodyResponse object
     */
    public static BodyResponse AddBodyMutations(
            BodyResponse.Builder bodyResponseBuilder,
            String body,
            Boolean clearBody,
            Boolean clearRouteCache) {
        CommonResponse.Builder responseBuilder = bodyResponseBuilder.getResponseBuilder();
        BodyMutation.Builder bodyBuilder = responseBuilder.getBodyMutationBuilder();
        if (body != null) {
            bodyBuilder.setBody(ByteString.copyFromUtf8(body));
        }
        if (clearBody != null) {
            bodyBuilder.setClearBody(clearBody);
        }
        if (clearRouteCache != null) {
            responseBuilder.setClearRouteCache(clearRouteCache);
        }
        return bodyResponseBuilder.build();
    }


    /**
     * Creates an immediate HTTP response with specific headers and status code.
     * <p>
     * Args:
     * code (StatusCode): The HTTP status code to return.
     * headers: Optional list of tuples (header, value) to include in the response.
     * append_action: Optional action specifying how headers should be appended.
     * <p>
     * Returns:
     * ImmediateResponse: Configured immediate response with the specified headers and status code.
     */
//    public static ImmediateResponse BuildImmediateResponse (
//            ImmediateResponse.Builder immediateResponseBuilder,
//            Iterable<Map.Entry<String, String>> addHeaders,
//            HttpStatus status
//    ) {
//
//        HeaderMutation.Builder headerMutationBuilder = immediateResponseBuilder
//                .getHeadersBuilder();
//
//        for(Map.Entry<String, String> entry : addHeaders) {
//            headerMutationBuilder
//                    .addSetHeadersBuilder()
//                    .getHeaderBuilder()
//                    .setKey(entry.getKey())
//                    .setValue(entry.getValue())
//                    .setRawValue(ByteString.copyFromUtf8(entry.getValue()));
//        }
//
//        immediateResponseBuilder.setStatus(status);
//
//        return immediateResponseBuilder.build();
//
//    }
    public static ImmediateResponse BuildImmediateResponse(
            HttpStatus status,
            ImmutableListMultimap<String, String> headers) {
        ImmediateResponse.Builder immediateResponseBuilder = ImmediateResponse.newBuilder();
        immediateResponseBuilder.setStatus(status);

        HeaderMutation.Builder headerMutationBuilder = immediateResponseBuilder.getHeadersBuilder();
        headers.entries().forEach(entry -> {
            headerMutationBuilder.addSetHeaders(
                    HeaderValueOption.newBuilder().setHeader(
                            HeaderValue.newBuilder().setKey(entry.getKey()).setValue(entry.getValue()).build()
                    ).build()
            );
        });

        return immediateResponseBuilder.build();
    }
}
