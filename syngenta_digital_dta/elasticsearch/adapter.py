from __future__ import annotations
import typing
from typing import TypedDict

from elasticsearch import Elasticsearch

from syngenta_digital_dta.common import schema_mapper
from syngenta_digital_dta.common.base_adapter import BaseAdapter, BaseAdapterKwargs
from syngenta_digital_dta.elasticsearch.es_connection import es_connection
from syngenta_digital_dta.elasticsearch import es_mapper

if typing.TYPE_CHECKING:
    from typing import Any, Dict, Optional, Literal, MutableMapping, Union, Collection, Tuple
    from typing_extensions import Unpack, NotRequired, Required


class ElasticsearchAdapter(BaseAdapter):

    def __init__(self, **kwargs: Unpack[ElasticsearchAdapterKwargs]):
        super().__init__(**kwargs)
        self.index = kwargs['index']
        self.endpoint = kwargs['endpoint']
        self.model_schema_file = kwargs['model_schema_file']
        self.model_schema = kwargs['model_schema']
        self.model_identifier = kwargs['model_identifier']
        self.authentication = kwargs.get('authentication')
        self.port = kwargs.get('port')
        self.user = kwargs.get('user')
        self.password = kwargs.get('password')
        self.size = kwargs.get('size', 10)
        self.connection: Elasticsearch
        self.__connect()

    @es_connection
    def __connect(self):
        # just need to call to invoke the decorator
        pass

    def create_template(self, **kwargs):
        kwargs['use_patterns'] = True
        body = self.__create_template_body(**kwargs)
        self.connection.indices.put_template(
            name=f'{kwargs["name"]}-template',
            body=body
        )

    def create_index(self, **kwargs):
        if not self.connection.indices.exists(self.index):
            create_args = {}
            create_args['index'] = self.index
            if kwargs.get('template', True):
                create_args['body'] = self.__create_template_body(**kwargs)
            self.connection.indices.create(**create_args)

    def create(self, **kwargs):
        data = schema_mapper.map_to_schema(kwargs['data'], self.model_schema_file, self.model_schema)
        response = self.connection.index(
            index=self.index,
            id=data[self.model_identifier],
            body=data,
            op_type='create',
            refresh=kwargs.get('refresh', True)
        )
        super().publish('create', data, **kwargs)
        return response

    def update(self, **kwargs):
        response = self.connection.update(
            index=self.index,
            id=kwargs['data'][self.model_identifier],
            body={'doc': kwargs['data']},
            refresh=kwargs.get('refresh', True)
        )
        super().publish('update', kwargs['data'], **kwargs)
        return response

    def overwrite(self, **kwargs):
        data = schema_mapper.map_to_schema(kwargs['data'], self.model_schema_file, self.model_schema)
        response = self.connection.index(
            index=self.index,
            id=data[self.model_identifier],
            body=data,
            op_type='index',  # `...opType must be 'create' or 'index'...`
            refresh=kwargs.get('refresh', True)
        )
        super().publish('overwrite', data, **kwargs)
        return response

    def upsert(self, **kwargs):
        operation = kwargs.get('operation', 'update')

        if self.connection.exists(index=self.index, id=kwargs['data'][self.model_identifier]):
            if operation == 'update':
                return self.update(**kwargs)

            if operation == 'overwrite':
                return self.overwrite(**kwargs)

            raise Exception(f'Input operation "{operation}" not supported!')

        return self.create(**kwargs)

    def delete(self, identifier_value, **kwargs):
        response = self.connection.delete(
            index=self.index,
            id=identifier_value,
            refresh=kwargs.get('refresh', True)
        )
        super().publish('delete', {self.model_identifier: identifier_value}, **kwargs)
        return response

    def get(self, identifier_value, **kwargs):
        try:
            response = self.connection.get(index=self.index, id=identifier_value)
            if kwargs.get('normalize'):
                response = response.get('_source')
            return response
        except BaseException:
            return {}

    def query(self, query: Dict[str, Any], *, normalize: bool = False,
              **kwargs: Unpack[ElasticsearchSearchKwargs]) -> Any:
        # dfs_query_then_fetch improves accuracy of results scoring,
        # but adds a round-trip to each shard, which can result in slower searches.
        kwargs.setdefault('search_type', 'dfs_query_then_fetch')
        response = self.connection.search(
            index=self.index,
            size=self.size,
            body={'query': query},
            **kwargs
        )
        if normalize:
            response = self.__normalize_hits(response)
        return response

    def __normalize_hits(self, hits):
        normalized_hits = []
        for hit in hits.get('hits', {}).get('hits', []):
            normalized_hits.append(hit['_source'])
        return normalized_hits

    def __create_template_body(self, **kwargs):
        body = {
            'settings': self.__get_settings(**kwargs),
            'mappings': self.__convert_openapi_mapping(self.model_schema_file, self.model_schema, kwargs.get('special'))
        }
        if kwargs.get('use_patterns') and isinstance(kwargs['index_patterns'], list):
            body['index_patterns'] = kwargs['index_patterns']
        elif kwargs.get('use_patterns'):
            body['index_patterns'] = [kwargs['index_patterns']]
        return body

    def __get_settings(self, **kwargs):
        if kwargs.get('settings'):
            return kwargs['settings']
        settings = {
            'number_of_replicas': 1,
            'number_of_shards': 1,
            'analysis': {
                'analyzer': {
                    'url_email_analyzer': {
                        'type': 'custom',
                        'tokenizer': 'uax_url_email'
                    }
                }
            }
        }
        return settings

    def __convert_openapi_mapping(self, schema_file, schema_key, special=None):
        mapping = es_mapper.convert_schema_to_mapping(schema_file, schema_key, special)
        return mapping


class ElasticsearchAdapterKwargs(BaseAdapterKwargs, total=True):
    """A TypedDict describing the type of **kwargs of the __init__() method"""
    index: str
    endpoint: str
    model_schema_file: str
    model_schema: Optional[str]
    model_identifier: Optional[str]
    authentication: NotRequired[Optional[str]]
    port: NotRequired[Optional[int]]
    user: NotRequired[Optional[str]]
    password: NotRequired[Optional[str]]
    size: NotRequired[Optional[int]]


class ElasticsearchSearchKwargs(TypedDict, total=False):
    """A TypedDict describing the type of **kwargs of the search() method"""
    # body: Optional[Any]
    # index: Optional[Any]
    doc_type: Optional[Any]
    _source: Optional[Any]
    _source_excludes: Optional[Any]
    _source_includes: Optional[Any]
    allow_no_indices: Optional[Any]
    allow_partial_search_results: Optional[Any]
    analyze_wildcard: Optional[Any]
    analyzer: Optional[Any]
    batched_reduce_size: Optional[Any]
    ccs_minimize_roundtrips: Optional[Any]
    default_operator: Optional[Any]
    df: Optional[Any]
    docvalue_fields: Optional[Any]
    expand_wildcards: Optional[Any]
    explain: Optional[Any]
    from_: Optional[Any]
    ignore_throttled: Optional[Any]
    ignore_unavailable: Optional[Any]
    lenient: Optional[Any]
    max_concurrent_shard_requests: Optional[Any]
    min_compatible_shard_node: Optional[Any]
    pre_filter_shard_size: Optional[Any]
    preference: Optional[Any]
    q: Optional[Any]
    request_cache: Optional[Any]
    rest_total_hits_as_int: Optional[Any]
    routing: Optional[Any]
    scroll: Optional[Any]
    search_type: Optional[Literal['query_then_fetch', 'dfs_query_then_fetch']]
    seq_no_primary_term: Optional[Any]
    # size: Optional[Any]
    sort: Optional[Any]
    stats: Optional[Any]
    stored_fields: Optional[Any]
    suggest_field: Optional[Any]
    suggest_mode: Optional[Any]
    suggest_size: Optional[Any]
    suggest_text: Optional[Any]
    terminate_after: Optional[Any]
    timeout: Optional[Any]
    track_scores: Optional[Any]
    track_total_hits: Optional[Any]
    typed_keys: Optional[Any]
    version: Optional[Any]
    pretty: Optional[bool]
    human: Optional[bool]
    error_trace: Optional[bool]
    format: Optional[str]
    filter_path: Optional[Union[str, Collection[str]]]
    request_timeout: Optional[Union[int, float]]
    ignore: Optional[Union[int, Collection[int]]]
    opaque_id: Optional[str]
    http_auth: Optional[Union[str, Tuple[str, str]]]
    api_key: Optional[Union[str, Tuple[str, str]]]
    params: Optional[MutableMapping[str, Any]]
    headers: Optional[MutableMapping[str, str]]
