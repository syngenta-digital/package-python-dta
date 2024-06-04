import json
import os
import unittest
import warnings
from datetime import datetime
from unittest import mock

import boto3
import requests

import syngenta_digital_dta


class S3AdapterTest(unittest.TestCase):

    def setUp(self, *args, **kwargs):
        warnings.simplefilter('ignore', ResourceWarning)
        self.maxDiff = None
        self.bucket = 'unit-test'
        self.endpoint = 'http://localhost:4566'
        self.file = open('./tests/mock/example.json')
        self.__create_unit_test_bucket()
        self.adapter = syngenta_digital_dta.adapter(
            engine='s3',
            endpoint=self.endpoint,
            bucket=self.bucket
        )

    def __create_unit_test_bucket(self):
        try:
            s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                region_name="us-east-2",
            )
            s3_client.create_bucket(
                Bucket=self.bucket,
                CreateBucketConfiguration={
                    'LocationConstraint': 'us-east-2'
                }
            )
        except:
            pass

    def test_init(self):
        self.assertIsInstance(self.adapter, syngenta_digital_dta.s3.adapter.S3Adapter)

    def test_create(self):
        results = self.adapter.create(
            s3_path='test/test-create.json',
            data={'test': True},
            json=True
        )
        self.assertEqual(results['ResponseMetadata']['HTTPStatusCode'], 200)

    def test_create_with_tags(self):
        self.adapter.create(
            s3_path='test/test-create.json',
            data={'test': True},
            json=True,
            tags={'partener': 'ingestor', 'integrationAccountReference': 'dummy_account'}
        )
        tags_result = self.adapter.client.get_object_tagging(
            Bucket=self.bucket,
            Key='test/test-create.json',
        )
        self.assertListEqual(tags_result['TagSet'], [{'Key': 'partener', 'Value': 'ingestor'},
                                                     {'Key': 'integrationAccountReference', 'Value': 'dummy_account'}])

    def test_add_tags(self):
        # create object
        self.adapter.create(
            s3_path='test/test-create2.json',
            data={'test': True},
            json=True,
        )
        # make sure no tags exists for the created object
        tags_result = self.adapter.client.get_object_tagging(
            Bucket=self.bucket,
            Key='test/test-create2.json',
        )
        self.assertListEqual(tags_result['TagSet'], [])
        # modify tags
        self.adapter.put_object_tags(
            s3_path='test/test-create2.json',
            tags={'partener': 'ingestor', 'integrationAccountReference': 'dummy_account'}
        )
        # validate the existing tags
        tags_result = self.adapter.client.get_object_tagging(
            Bucket=self.bucket,
            Key='test/test-create2.json',
        )
        self.assertListEqual(tags_result['TagSet'], [{'Key': 'partener', 'Value': 'ingestor'},
                                                     {'Key': 'integrationAccountReference', 'Value': 'dummy_account'}])

    def test_put_stream(self):
        url = 'https://github.com/syngenta-digital/package-python-dta/archive/refs/heads/master.zip'
        response = requests.get(url, stream=True)
        self.adapter.upload_stream(data=response.content, s3_path='test/code-clone-stream.zip')
        results = self.adapter.read(
            s3_path='test/code-clone-stream.zip',
            json=False,
            decode=False
        )
        self.assertEqual(results['ResponseMetadata']['HTTPStatusCode'], 200)

    def test_read(self):
        data = {'test': True}
        s3_path = 'test/test-read.json'
        self.adapter.create(
            s3_path=s3_path,
            data=data,
            json=True
        )
        result = self.adapter.read(
            s3_path=s3_path,
            json=True
        )
        self.assertDictEqual(data, result)

    def test_delete(self):
        s3_path = 'test/test-delete.json'
        self.adapter.create(
            s3_path=s3_path,
            data={'test': True},
            json=True
        )
        results = self.adapter.delete(s3_path=s3_path)
        self.assertEqual(results['ResponseMetadata']['HTTPStatusCode'], 204)

    def test_download(self):
        s3_path = 'test/test-download.json'
        data = {'test': True}
        self.adapter.create(
            s3_path=s3_path,
            data=data,
            json=True
        )
        download_path = '/tmp/unit-test-download/test.json'
        self.adapter.download(s3_path=s3_path, download_path=download_path)
        with open(download_path) as json_file:
            json_dict = json.load(json_file)
        self.assertEqual(True, os.path.exists(download_path))
        self.assertDictEqual(json_dict, data)

    def test_object_exist_true(self):
        s3_path = 'test/test_is_exist_true.json'
        self.adapter.create(
            s3_path=s3_path,
            data={'test': True},
            json=True
        )

        result = self.adapter.object_exist(s3_path=s3_path)

        self.assertEqual(result, True)

    def test_object_exist_false(self):
        s3_path = 'test/test_is_exist_false.json'
        result = self.adapter.object_exist(s3_path=s3_path)
        self.assertEqual(result, False)

    def __read_in_chunks(self):
        return self.file.read(6000000)

    def test_multipart_upload(self):
        chunks = []
        for piece in iter(self.__read_in_chunks, ''):
            chunks.append(piece)
        s3_path = 'test/test-multipart.json'
        results = self.adapter.multipart_upload(chunks=chunks, s3_path=s3_path)
        self.assertEqual(results['ResponseMetadata']['HTTPStatusCode'], 200)
        self.assertEqual(results['Location'],
                         'http://unit-test.s3.localhost.localstack.cloud:4566/test/test-multipart.json')

    def test_create_presigned_read_url(self):
        s3_path = 'test/test-presigned-url.json'
        self.adapter.create(
            s3_path=s3_path,
            data={'test': True},
            json=True
        )
        result = self.adapter.create_presigned_read_url(s3_path=s3_path, expiration=3600)
        self.assertEqual(True, s3_path in result)

    def test_create_presigned_post_url(self):
        s3_path = 'test/test-presigned-url.json'
        result = self.adapter.create_presigned_post_url(s3_path=s3_path, expiration=3600)
        self.assertEqual(True, self.bucket in result['url'])

    def test_list_dir_subfolders(self):
        folder = 'first_level/123/'
        self.adapter.create(
            s3_path='first_level/123/test-create.json',
            data={'test': True},
            json=True
        )
        result = self.adapter.list_dir_subfolders(dir_name='first_level/')
        self.assertIn(folder, result)

    def test_list_dir_files(self):
        file = 'test/test-create.json'
        result = self.adapter.list_dir_files(dir_name='test/')
        self.assertIn(file, result)

    def test_list_dir_files_with_date(self):
        file = 'test/test-create.json'
        result = self.adapter.list_dir_files(dir_name='test/', date=datetime(2000, 1, 1))
        self.assertIn(file, result)

    def test_rename_object(self):
        old_file = 'test/test-create.json'
        self.adapter.rename_object(old_file_name=old_file, new_file_name='test/test-new.json')

    def test_upload_fileobj_public_read_true(self):
        s3_path = 'my_s3_path'
        public_read = True
        data = "my_s3_data".encode()

        adapter = syngenta_digital_dta.adapter(
            engine='s3',
            endpoint=self.endpoint,
            bucket=self.bucket
        )

        adapter.client = mock.MagicMock()
        adapter.upload_stream(data=data, s3_path=s3_path, public_read=public_read)
        adapter.client.upload_fileobj.assert_called_with(
            mock.ANY,
            'unit-test',
            'my_s3_path',
            ExtraArgs={'ACL': 'public-read'},
            Config=mock.ANY
        )

    def test_upload_fileobj_public_read_false(self):
        s3_path = 'my_s3_path'
        public_read = False
        data = "my_s3_data".encode()

        adapter = syngenta_digital_dta.adapter(
            engine='s3',
            endpoint=self.endpoint,
            bucket=self.bucket
        )

        adapter.client = mock.MagicMock()
        adapter.upload_stream(data=data, s3_path=s3_path, public_read=public_read)
        adapter.client.upload_fileobj.assert_called_with(
            mock.ANY,
            'unit-test',
            'my_s3_path',
            ExtraArgs={'ACL': 'private'},
            Config=mock.ANY
        )

    def test_public_url(self):
        s3_path = 'my_s3_dir/my_s3_folder/my_s3_file.txt'
        url = self.adapter.create_public_url(s3_path=s3_path)
        self.assertEqual(
            "http://localhost:4566/unit-test/my_s3_dir/my_s3_folder/my_s3_file.txt",
            url
        )

    @mock.patch("syngenta_digital_dta.common.publisher.publish")
    @mock.patch("syngenta_digital_dta.s3.adapter.S3Adapter.create_public_url")
    def test_publish_notification(self, mock_create_public_url, mock_publish):
        presigned_url = "http://some_url.com"
        record_type = "somerecordtype"
        mock_create_public_url.return_value = presigned_url
        mock_publish.return_value = None
        adapter = syngenta_digital_dta.adapter(
            engine='s3',
            endpoint=self.endpoint,
            bucket=self.bucket,
            sns_attributes={
                "record_type": record_type
            }
        )
        adapter.publish_notification()
        mock_publish.assert_called_with(endpoint=None, arn=None,
                                        attributes={'operation': {'DataType': 'String', 'StringValue': 'create'},
                                                    'record_type': {'DataType': 'String',
                                                                    'StringValue': record_type}},
                                        data={'presigned_url': presigned_url}, fifo_group_id=None,
                                        fifo_duplication_id=None)
