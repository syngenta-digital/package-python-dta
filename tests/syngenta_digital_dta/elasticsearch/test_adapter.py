import uuid
import unittest
import warnings

import syngenta_digital_dta, syngenta_digital_dta.elasticsearch.adapter


class ElasticsearchAdapterTest(unittest.TestCase):

    def setUp(self):
        warnings.simplefilter('ignore', ResourceWarning)
        self.maxDiff = None
        self.adapter = syngenta_digital_dta.adapter(
            engine='elasticsearch',
            index='users',
            endpoint='localhost',
            model_schema='test-elasticsearch-user-model',
            model_schema_file='tests/openapi.yml',
            model_identifier='user_id',
            model_version_key='modified'
        )

    def test_init(self):
        self.assertIsInstance(self.adapter, syngenta_digital_dta.elasticsearch.adapter.ElasticsearchAdapter)

    def test_connected(self):
        self.assertEqual(self.adapter.connection.ping(), True)

    def test_create_template(self):
        try:
            self.adapter.create_template(
                name='users',
                index_patterns='users-*'
            )
            self.assertEqual(True, True)
        except Exception as e:
            print(e)
            self.assertEqual(False, True)

    def test_create_template_list_patterns(self):
        try:
            self.adapter.create_template(
                name=uuid.uuid4().hex,
                index_patterns=[f'{uuid.uuid4().hex}-*']
            )
            self.assertEqual(True, True)
        except Exception as e:
            print(e)
            self.assertEqual(False, True)

    def test_create_custom_patterns(self):
        try:
            self.adapter.create_template(
                name=uuid.uuid4().hex,
                index_patterns=[f'{uuid.uuid4().hex}-*'],
                settings={
                    'number_of_replicas': 3,
                    'number_of_shards': 3,
                    'analysis': {
                        'analyzer': {
                            'url_email_analyzer': {
                                'type': 'custom',
                                'tokenizer': 'uax_url_email'
                            }
                        }
                    }
                }
            )
            self.assertEqual(True, True)
        except Exception as e:
            print(e)
            self.assertEqual(False, True)

    def test_create_index(self):
        try:
            adapter = syngenta_digital_dta.adapter(
                engine='elasticsearch',
                index=uuid.uuid4().hex,
                endpoint='localhost',
                model_schema='test-elasticsearch-user-model',
                model_schema_file='tests/openapi.yml',
                model_identifier='user_id',
                model_version_key='modified'
            )
            adapter.create_index()
            self.assertEqual(True, True)
        except Exception as e:
            print(e)
            self.assertEqual(False, True)

    def test_create_index_no_template(self):
        try:
            adapter = syngenta_digital_dta.adapter(
                engine='elasticsearch',
                index=uuid.uuid4().hex,
                endpoint='localhost',
                model_schema='test-elasticsearch-user-model',
                model_schema_file='tests/openapi.yml',
                model_identifier='user_id',
                model_version_key='modified'
            )
            adapter.create_index(template=False)
            self.assertEqual(True, True)
        except Exception as e:
            print(e)
            self.assertEqual(False, True)

    def test_create(self):
        data = {
            'user_id': uuid.uuid4().hex,
            'email': 'some.user@syngenta.com',
            'first': 'Some',
            'last': 'User',
            'phone': 1112224444
        }
        try:
            self.adapter.create(data=data)
            self.assertEqual(True, True)
        except Exception:
            self.assertEqual(False, True)

    def test_create_uniqueness(self):
        unique = uuid.uuid4().hex
        data = {
            'user_id': unique,
            'email': f'some.user.{unique}@syngenta.com',
            'first': 'Some',
            'last': 'User',
            'phone': 1112224444
        }
        self.adapter.create(data=data)
        try:
            self.adapter.create(data=data)
            self.assertEqual(False, True)
        except Exception as e:
            self.assertEqual('already exists' in str(e), True)

    def test_update(self):
        update_id = uuid.uuid4().hex
        data = {
            'user_id': update_id,
            'email': 'some.user-update@syngenta.com',
            'first': 'Some',
            'last': 'User',
            'phone': 1112224444
        }
        self.adapter.create(data=data)
        updated_data = {'user_id': update_id, 'first': 'Peter'}
        try:
            self.adapter.update(data=updated_data)
            self.assertEqual(True, True)
        except Exception as e:
            self.assertEqual(False, True)

    def test_update_fails(self):
        updated_data = {'user_id': uuid.uuid4().hex, 'first': 'Peter'}
        try:
            self.adapter.update(data=updated_data)
            self.assertEqual(False, True)
        except Exception as e:
            self.assertEqual(True, True)

    def test_upsert(self):
        upsert_id = uuid.uuid4().hex
        data = {
            'user_id': upsert_id,
            'email': 'some.user-upsert@syngenta.com',
            'first': 'Some',
            'last': 'User',
            'phone': 1112224444
        }
        try:
            self.adapter.upsert(data=data)  # should create
            updated_data = {'user_id': upsert_id, 'first': 'Patrick'}
            self.adapter.upsert(data=updated_data)  # should update
            self.assertEqual(True, True)
        except Exception as e:
            self.assertEqual(False, True)

    def test_delete(self):
        delete_id = uuid.uuid4().hex
        data = {
            'user_id': delete_id,
            'email': 'some.user-delete@syngenta.com',
            'first': 'Some',
            'last': 'User',
            'phone': 1112224444
        }
        try:
            self.adapter.upsert(data=data)
            self.adapter.delete(delete_id)
            self.assertEqual(True, True)
        except Exception as e:
            self.assertEqual(False, True)

    def test_get(self):
        get_id = uuid.uuid4().hex
        data = {
            'user_id': get_id,
            'email': 'some.user-get@syngenta.com',
            'first': 'Some',
            'last': 'User',
            'phone': 1112224444
        }

        self.adapter.upsert(data=data)
        response = self.adapter.get(get_id)
        self.assertDictEqual(response, {
            '_index': 'users',
            '_type': response['_type'],
            '_id': get_id,
            '_version': response['_version'],
            '_seq_no': response['_seq_no'],
            '_primary_term': response['_primary_term'],
            'found': True,
            '_source': {
                'user_id': get_id,
                'email': 'some.user-get@syngenta.com',
                'first': 'Some',
                'last': 'User',
                'phone': 1112224444
            }
        })

    def test_get_normalize(self):
        get_normailize_id = uuid.uuid4().hex
        data = {
            'user_id': get_normailize_id,
            'email': 'some.user-get-normalize@syngenta.com',
            'first': 'Some',
            'last': 'User',
            'phone': 1112224444
        }
        self.adapter.upsert(data=data)
        response = self.adapter.get(get_normailize_id, normalize=True)
        self.assertDictEqual(response, {
            "user_id": get_normailize_id,
            "email": "some.user-get-normalize@syngenta.com",
            "first": "Some",
            "last": "User",
            "phone": 1112224444
        })

    def test_get_nothing(self):
        response = self.adapter.get(uuid.uuid4().hex, normalize=True)
        self.assertEqual(response, {})

    def test_query_match(self):
        query_id = uuid.uuid4().hex
        data = {
            'user_id': query_id,
            'email': 'new.user@syngenta.com',
            'first': 'New',
            'last': 'User',
            'phone': 7778889999
        }
        self.adapter.upsert(data=data)
        response = self.adapter.query(query={
            'match': {
                'first': 'New'
            }
        })
        self.assertEqual(response['hits']['total']['value'] > 0, True)

    def test_query_normalize(self):
        query_normailize_id = uuid.uuid4().hex
        data = {
            'user_id': query_normailize_id,
            'email': 'normal.query@syngenta.com',
            'first': 'Normal',
            'last': 'Query',
            'phone': 5556667777
        }
        self.adapter.upsert(data=data)
        response = self.adapter.query(
            normalize=True,
            query={
                'match': {
                    'first': 'Normal'
                }
            }
        )
        self.assertEqual(len(response) > 0, True)

    def test_failed_query_normalize(self):
        response = self.adapter.query(
            normalize=True,
            query={
                'match': {
                    'first': 'Failure'
                }
            }
        )
        self.assertEqual(len(response), 0)

    def test_query_search_type(self):
        query = {
            "bool": {
                "must": [
                    {
                        "range": {
                            "start_date_time": {
                                "gte": "2022-01-01T00:00:00"
                            }
                        }
                    }
                ]
            }
        }
        self.adapter.query(
            query=query,
            search_type='query_then_fetch'
        )
        self.adapter.query(
            query=query,
            search_type='dfs_query_then_fetch'
        )

    def test_query_with_body_and_sort(self):
        query_normalize_id = uuid.uuid4().hex
        data = {
            'user_id': query_normalize_id,
            'email': 'normal.query@syngenta.com',
            'first': 'Normal',
            'last': 'Query',
            'phone': 5556667777
        }
        self.adapter.upsert(data=data)

        response, next_token = self.adapter.query_with_body_and_sort(
            normalize=True,
            body={
                'query': {
                    'match': {
                        'first': 'Normal'
                    }
                },
                "sort": [{"_id": "asc"}],
            }
        )
        self.assertGreater(len(response), 0)
        self.assertIsNotNone(next_token)
