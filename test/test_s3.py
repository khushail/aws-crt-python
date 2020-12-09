# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0.

from awscrt.http import HttpHeaders, HttpRequest
from awscrt.s3 import S3Client, AwsS3RequestType, S3Request
from test import NativeResourceTest, TIMEOUT
from awscrt.io import LazyReadStream, ClientBootstrap, ClientTlsContext, DefaultHostResolver, EventLoopGroup, TlsConnectionOptions, TlsContextOptions, init_logging, LogLevel
from awscrt.auth import AwsCredentialsProvider
import io
import unittest
import os


def s3_client_new(secure, region, part_size=0):

    event_loop_group = EventLoopGroup()
    host_resolver = DefaultHostResolver(event_loop_group)
    bootstrap = ClientBootstrap(event_loop_group, host_resolver)
    credential_provider = AwsCredentialsProvider.new_default_chain(bootstrap)
    tls_option = None
    if secure:
        opt = TlsContextOptions()
        ctx = ClientTlsContext(opt)
        tls_option = TlsConnectionOptions(ctx)

    s3_client = S3Client(
        bootstrap=bootstrap,
        region=region,
        credential_provider=credential_provider,
        tls_connection_options=tls_option,
        part_size=part_size)

    return s3_client


class S3ClientTest(NativeResourceTest):
    region = "us-west-2"
    timeout = 10  # seconds

    def test_sanity(self):
        s3_client = s3_client_new(False, self.region)
        self.assertIsNotNone(s3_client)

    def test_sanity_secure(self):
        s3_client = s3_client_new(True, self.region)
        self.assertIsNotNone(s3_client)

    def test_wait_shutdown(self):
        s3_client = s3_client_new(False, self.region)
        self.assertIsNotNone(s3_client)

        shutdown_event = s3_client.shutdown_event
        del s3_client
        self.assertTrue(shutdown_event.wait(self.timeout))


class S3RequestTest(NativeResourceTest):
    get_test_object_path = "/get_object_test_10MB.txt"
    put_test_object_path = "/put_object_test_py_10MB.txt"
    put_test_small_object_path = "/0.txt"
    region = "us-west-2"
    bucket_name = "aws-crt-canary-bucket"
    timeout = 100  # seconds
    num_threads = 0

    response_headers = None
    response_status_code = None
    body_len = 0

    def _build_endpoint_string(self, region, bucket_name):
        return bucket_name + ".s3." + region + ".amazonaws.com"

    def _get_object_request(self):
        headers = HttpHeaders([("host", self._build_endpoint_string(self.region, self.bucket_name))])
        request = HttpRequest("GET", self.get_test_object_path, headers)
        return request

    def _put_object_request(self):
        data_len = 10485760
        body_stream = LazyReadStream("put_object_test_10MB.txt", "r+b", data_len)
        headers = HttpHeaders([("host", self._build_endpoint_string(self.region, self.bucket_name)),
                               ("Content-Type", "text/plain"), ("Content-Length", str(data_len))])
        request = HttpRequest("PUT", self.put_test_object_path, headers, body_stream)
        return request

    def _put_small_object_request(self):
        file_stats = os.stat("get_object_test_1MB.txt")
        data_len = file_stats.st_size
        body_stream = LazyReadStream("get_object_test_1MB.txt", "r+b", data_len)
        headers = HttpHeaders([("host", self._build_endpoint_string(self.region, self.bucket_name)),
                               ("Content-Type", "text/plain"), ("Content-Length", str(data_len))])
        request = HttpRequest("PUT", self.put_test_small_object_path, headers, body_stream)
        return request

    def _on_request_headers(self, status_code, headers, **kargs):
        print(status_code)
        print(headers)
        self.response_status_code = status_code
        self.assertIsNotNone(headers, "headers are none")
        self.response_headers = headers

    def _on_request_body(self, chunk, offset, **kargs):
        print(offset)
        self.assertIsNotNone(chunk, "the body chunk is none")
        self.body_len = self.body_len + len(chunk)

    def _validate_successful_get_response(self, put_object):
        self.assertEqual(self.response_status_code, 200, "status code is not 200")
        headers = HttpHeaders(self.response_headers)
        # self.assertIsNone(headers.get("accept-ranges"))
        self.assertIsNone(headers.get("Content-Range"))
        body_length = headers.get("Content-Length")
        if not put_object:
            self.assertIsNotNone(body_length, "Content-Length is missing from headers")
        if body_length:
            self.assertEqual(
                int(body_length),
                self.body_len,
                "Received body length does not match the Content-Length header")

    def _download_file_example(self):
        # num_threads is the Number of event-loops to create. Pass 0 to create one for each processor on the machine.
        event_loop_group = EventLoopGroup(self.num_threads)
        host_resolver = DefaultHostResolver(event_loop_group)
        bootstrap = ClientBootstrap(event_loop_group, host_resolver)
        credential_provider = AwsCredentialsProvider.new_default_chain(bootstrap)
        s3_client = S3Client(
            bootstrap=bootstrap,
            region="us-west-2",
            credential_provider=credential_provider)
        headers = HttpHeaders([("host", self.bucket_name + ".s3." + self.region + ".amazonaws.com")])
        request = HttpRequest("GET", "/get_object_test_1MB.txt", headers)
        file = open("get_object_test_1MB.txt", "wb")

        def on_body(chunk):
            file.write(chunk)

        s3_request = s3_client.make_request(
            request=request,
            type=AwsS3RequestType.GET_OBJECT,
            on_body=on_body)
        finished_future = s3_request.finished_future
        result = finished_future.result(self.timeout)
        file.close()

    def _upload_file_example(self):
        # num_threads is the Number of event-loops to create. Pass 0 to create one for each processor on the machine.
        init_logging(LogLevel.Trace, "log.txt")
        event_loop_group = EventLoopGroup(self.num_threads)
        host_resolver = DefaultHostResolver(event_loop_group)
        bootstrap = ClientBootstrap(event_loop_group, host_resolver)
        credential_provider = AwsCredentialsProvider.new_default_chain(bootstrap)
        s3_client = S3Client(
            bootstrap=bootstrap,
            region="us-west-2",
            credential_provider=credential_provider,
            part_size=5 * 1024 * 1024)
        data_stream = open("put_object_test_10MB.txt", 'rb')
        body_bytes = data_stream.read()
        data_len = len(body_bytes)
        data_stream.seek(0)
        data_stream_replace = io.BytesIO(body_bytes)
        print(data_len)
        headers = HttpHeaders([("host", self.bucket_name + ".s3." + self.region +
                                ".amazonaws.com"), ("Content-Type", "text/plain"), ("Content-Length", str(data_len))])
        request = HttpRequest("PUT", "/put_object_test_py_10MB.txt", headers, data_stream_replace)

        def on_headers(status_code, headers):
            """
            check the status and probably print out the headers
            """
            print(status_code)
            print(headers)

        s3_request = s3_client.make_request(
            request=request,
            type=AwsS3RequestType.PUT_OBJECT,
            on_headers=on_headers
        )
        finished_future = s3_request.finished_future
        try:
            result = finished_future.result(self.timeout)
        except Exception as e:
            print("request finished with failure:", e)

        data_stream.close()

    def _test_s3_put_get_object(self, request, type):
        s3_client = s3_client_new(False, self.region, 5 * 1024 * 1024)
        s3_request = s3_client.make_request(
            request=request,
            type=type,
            on_headers=self._on_request_headers,
            on_body=self._on_request_body)
        finished_future = s3_request.finished_future
        result = (finished_future.result(self.timeout))
        self._validate_successful_get_response(type is AwsS3RequestType.PUT_OBJECT)
        shutdown_event = s3_request.shutdown_event
        del s3_request
        self.assertTrue(shutdown_event.wait(self.timeout))

    def test_get_object(self):
        init_logging(LogLevel.Error, "unittestlog.txt")
        request = self._get_object_request()
        self._test_s3_put_get_object(request, AwsS3RequestType.GET_OBJECT)

    # def test_sample(self):
    #     self._upload_file_example()

    def test_put_object(self):
        # init_logging(LogLevel.Trace, "unittest_log.txt")
        request = self._put_object_request()
        self._test_s3_put_get_object(request, AwsS3RequestType.PUT_OBJECT)

    def test_put_small_object(self):
        # init_logging(LogLevel.Trace, "unittest_log.txt")
        request = self._put_small_object_request()
        self._test_s3_put_get_object(request, AwsS3RequestType.PUT_OBJECT)