from __future__ import annotations
import typing
from typing import Optional, Literal, overload

if typing.TYPE_CHECKING:
    from typing_extensions import Unpack
    from syngenta_digital_dta.dynamodb.adapter import DynamodbAdapter
    from syngenta_digital_dta.postgres.adapter import PostgresAdapter
    from syngenta_digital_dta.elasticsearch.adapter import ElasticsearchAdapter, ElasticsearchAdapterKwargs
    from syngenta_digital_dta.s3.adapter import S3Adapter
    from syngenta_digital_dta.file_system.adapter import FileSystemAdapter
    from syngenta_digital_dta.mongo.adapter import MongoAdapter

EngineID = Literal['dynamodb', 'redshift', 'postgres', 'elasticsearch', 's3', 'file_system', 'mongo']


@overload
def adapter(engine: Literal['dynamodb'], **kwargs) -> DynamodbAdapter: ...


@overload
def adapter(engine: Literal['redshift'], **kwargs) -> PostgresAdapter: ...


@overload
def adapter(engine: Literal['postgres'], **kwargs) -> PostgresAdapter: ...


@overload
def adapter(engine: Literal['elasticsearch'], **kwargs: Unpack[ElasticsearchAdapterKwargs]) -> ElasticsearchAdapter: ...


@overload
def adapter(engine: Literal['s3'], **kwargs) -> S3Adapter: ...


@overload
def adapter(engine: Literal['file_system'], **kwargs) -> FileSystemAdapter: ...


@overload
def adapter(engine: Literal['mongo'], **kwargs) -> MongoAdapter: ...


def adapter(engine: Optional[EngineID] = None, **kwargs):  # pylint: disable=R0911
    # engine=engine is not needed in the constructor calls below
    # because none of them use an 'engine' keyword argument
    if engine == 'dynamodb':
        from syngenta_digital_dta.dynamodb.adapter import DynamodbAdapter  # pylint: disable=C
        return DynamodbAdapter(**kwargs)
    if engine == 'redshift':
        from syngenta_digital_dta.postgres.adapter import PostgresAdapter  # pylint: disable=C
        return PostgresAdapter(**kwargs)
    if engine == 'postgres':
        from syngenta_digital_dta.postgres.adapter import PostgresAdapter  # pylint: disable=C
        return PostgresAdapter(**kwargs)
    if engine == 'elasticsearch':
        from syngenta_digital_dta.elasticsearch.adapter import ElasticsearchAdapter  # pylint: disable=C
        return ElasticsearchAdapter(**kwargs)
    if engine == 's3':
        from syngenta_digital_dta.s3.adapter import S3Adapter  # pylint: disable=C
        return S3Adapter(**kwargs)
    if engine == 'file_system':
        from syngenta_digital_dta.file_system.adapter import FileSystemAdapter  # pylint: disable=C
        return FileSystemAdapter(**kwargs)
    if engine == 'mongo':
        from syngenta_digital_dta.mongo.adapter import MongoAdapter  # pylint: disable=C
        return MongoAdapter(**kwargs)
    raise Exception(
        f'engine {engine or "was not supplied, an empty engine kwarg is"} not supported; contribute to get it supported :)')
