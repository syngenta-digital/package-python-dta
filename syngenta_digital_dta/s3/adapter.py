import os
from io import BytesIO

import boto3
import botocore
import jsonpickle
from botocore.config import Config
from botocore.exceptions import ClientError

from syngenta_digital_dta.common.base_adapter import BaseAdapter


class S3Adapter(BaseAdapter):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.endpoint = kwargs.get('endpoint')
        self.sns_attributes = kwargs.get('sns_attributes')
        self.sns_arn = kwargs.get('sns_arn')
        self.bucket = kwargs.get('bucket')
        self.aws_access_key_id = kwargs.get('aws_access_key_id')
        self.aws_secret_access_key = kwargs.get('aws_secret_access_key')
        self.region = kwargs.get('region')
        self.client = self.__make_client()
        self.resource = self.__make_resource()

    def __make_client(self, config=None):
        return boto3.client(
            's3',
            endpoint_url=self.endpoint,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region,
            config=config
        )

    def __make_resource(self, config=None):
        return boto3.resource(
            's3',
            endpoint_url=self.endpoint,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region,
            config=config
        )

    def create(self, **kwargs):
        result = self.put(**kwargs)
        return result

    def put(self, **kwargs):
        acl = self.__set_acl(kwargs.get('public_read', False))
        body = self.__set_body(**kwargs)
        tags = self.__construct_tags_string(**kwargs)
        results = self.client.put_object(
            ACL=acl,
            Body=body,
            Bucket=self.bucket,
            Key=kwargs['s3_path'],
            Tagging= tags
        )
        if kwargs.get('publish', True):
            super().publish('create', self.__generate_publish_data(**kwargs), **kwargs)
        return results

    def publish_notification(self, **kwargs):
        super().publish('create', self.__generate_publish_data(**kwargs), **kwargs)

    def put_object_tags(self, **kwargs):
        tags = self.__construct_tag_set(**kwargs)
        results = self.client.put_object_tagging(
            Bucket=self.bucket,
            Key=kwargs['s3_path'],
            Tagging={
                'TagSet': tags
            }
        )
        return results

    def upload_stream(self, **kwargs):
        conf = boto3.s3.transfer.TransferConfig(
            multipart_threshold=kwargs.get('threshold', 10000),
            max_concurrency=kwargs.get('concurrency', 4)
        )

        if kwargs.get('io'):
            self.client.upload_fileobj(
                kwargs['io'],
                self.bucket,
                kwargs['s3_path'],
                ExtraArgs={
                    'ACL': self.__set_acl(kwargs.get('public_read'))
                },
                Config=conf
            )
        else:
            with BytesIO(bytes(kwargs['data'])) as data:
                self.client.upload_fileobj(
                    data,
                    self.bucket,
                    kwargs['s3_path'],
                    ExtraArgs={
                        'ACL': self.__set_acl(kwargs.get('public_read'))
                    },
                    Config=conf
                )

        if kwargs.get('publish', True):
            super().publish('create', self.__generate_publish_data(**kwargs), **kwargs)

    def download_stream(self, **kwargs):
        conf = boto3.s3.transfer.TransferConfig(
            multipart_threshold=kwargs.get('threshold', 10000),
            max_concurrency=kwargs.get('concurrency', 4)
        )

        self.client.download_fileobj(
            self.bucket,
            kwargs['s3_path'],
            kwargs['io'],
            Config=conf
        )

        kwargs['io'].seek(0)

    def delete(self, **kwargs):
        result = self.client.delete_object(
            Bucket=self.bucket,
            Key=kwargs['s3_path']
        )
        return result

    def read(self, **kwargs):
        return self.get(**kwargs)

    def get(self, **kwargs):
        results = self.client.get_object(
            Bucket=self.bucket,
            Key=kwargs['s3_path']
        )
        return self.__set_results(results, **kwargs)

    def download(self, **kwargs):
        self.__create_download_directory(kwargs['download_path'])
        self.client.download_file(self.bucket, kwargs['s3_path'], kwargs['download_path'])
        return kwargs['download_path']

    def multipart_upload(self, **kwargs):
        multipart = self.client.create_multipart_upload(Bucket=self.bucket, Key=kwargs['s3_path'])
        parts = []
        for part, chunk in enumerate(kwargs['chunks']):
            part_number = part + 1  # @NOTE must be an integer between 1 and 10000, inclusive
            part_response = self.__upload_part(
                chunk=chunk, s3_path=kwargs['s3_path'], upload_id=multipart['UploadId'], part_number=part_number)
            parts.append({'ETag': part_response['ETag'], 'PartNumber': part_number})
        complete_response = self.__complete_multipart_upload(
            s3_path=kwargs['s3_path'], parts=parts, upload_id=multipart['UploadId'])

        if kwargs.get('publish', True):
            super().publish('create', self.__generate_publish_data(**kwargs), **kwargs)
        return complete_response

    def create_public_url(self, **kwargs):
        # we create a new client here to not modify other method calls
        config = Config(signature_version=botocore.UNSIGNED)
        client = self.__make_client(config=config)
        return client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': self.bucket,
                'Key': kwargs['s3_path']
            },
            ExpiresIn=0,
        )

    def create_presigned_read_url(self, **kwargs):
        results = self.client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': self.bucket,
                'Key': kwargs['s3_path']
            },
            ExpiresIn=kwargs.get('expiration', 3600)
        )
        return results

    def create_presigned_post_url(self, **kwargs):
        results = self.client.generate_presigned_post(
            self.bucket,
            kwargs['s3_path'],
            Fields=kwargs.get('required_fields'),
            Conditions=kwargs.get('required_conditions'),
            ExpiresIn=kwargs.get('expiration', 3600)
        )
        return results

    def object_exist(self, **kwargs):
        try:
            self.resource.Object(self.bucket, kwargs['s3_path']).load()
        except ClientError as error:
            if error.response['Error']['Code'] == '404':
                return False
            raise

        return True

    def list_dir_subfolders(self, **kwargs):
        result = self.client.list_objects(Bucket=self.bucket, Prefix=kwargs.get('dir_name'), Delimiter='/')
        return [obj['Prefix'] for obj in result['CommonPrefixes']]

    def list_dir_files(self, **kwargs):
        paginator = self.client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.bucket, Prefix=kwargs.get('dir_name'))
        if kwargs.get('date'):
            return [obj['Key'] for page in pages for obj in page['Contents'] if obj['LastModified'].replace(tzinfo=None) > kwargs.get('date')]

        return [obj['Key'] for page in pages for obj in page['Contents']]

    def rename_object(self, **kwargs):
        old_file_key = kwargs.get('old_file_name')
        self.resource.Object(self.bucket, kwargs.get('new_file_name')).copy_from(
            CopySource={'Bucket': self.bucket, 'Key': old_file_key})
        self.delete(s3_path=old_file_key)

    def __upload_part(self, **kwargs):
        response = self.client.upload_part(
            Body=kwargs['chunk'],
            Bucket=self.bucket,
            Key=kwargs['s3_path'],
            UploadId=kwargs['upload_id'],
            PartNumber=kwargs['part_number']
        )
        return response

    def __complete_multipart_upload(self, **kwargs):
        response = self.client.complete_multipart_upload(
            Bucket=self.bucket,
            Key=kwargs['s3_path'],
            MultipartUpload={'Parts': kwargs['parts']},
            UploadId=kwargs['upload_id']
        )
        return response

    def __create_download_directory(self, download_path):
        os.makedirs(os.path.dirname(download_path), exist_ok=True)
        with open(download_path, 'wb') as path:
            path.close()

    def __set_results(self, results, **kwargs):
        if kwargs.get('json'):
            body = results['Body'].read().decode('utf-8')
            return jsonpickle.decode(body)
        if kwargs.get('decode', True):
            return results['Body'].read().decode('utf-8')
        return results

    def __set_body(self, **kwargs):
        data = kwargs['data']
        if kwargs.get('json'):
            data = jsonpickle.dumps(data, unpicklable=False, use_decimal=True)
        if kwargs.get('encode', True):
            data = bytes(data.encode('UTF-8'))
        return data

    def __set_acl(self, public_read):
        if public_read:
            return 'public-read'
        return 'private'

    def __generate_publish_data(self, **kwargs):
        return {'presigned_url': self.create_public_url(**kwargs)}

    def __construct_tag_set(self, **kwargs) -> list:
        tags = kwargs.get('tags', None)
        result_tags = []
        if not tags:
            return result_tags
        try:
            for key, value in tags.items():
                result_tags.append({ 'Key' : key, 'Value': value})
            return result_tags
        except AttributeError as error:
            raise TypeError(' tags parameter is invalid, it should be Dict object') from error

    def __construct_tags_string(self, **kwargs):
        tags = kwargs.get('tags' , None)
        result_tags = ''
        if not tags:
            return result_tags
        try:
            for key, value in tags.items():
                result_tags += f'{key}={value}&'
            return result_tags[:-1]
        except AttributeError as error:
            raise TypeError(' tags parameter is invalid, it should be Dict object') from error
