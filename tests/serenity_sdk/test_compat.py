import pytest

from serenity_sdk.client import (APIPathMapper, CallType, CallingConvention, Environment,
                                 UnknownOperationError, UnsupportedOperationError)


def test_lookup_call_type():
    api_mapper = APIPathMapper()
    assert api_mapper.get_call_type('/refdata/asset/types') == CallType.GET


def test_lookup_default_calling_convention_default():
    dev_api_mapper = APIPathMapper(Environment.DEV)
    assert dev_api_mapper.get_default_calling_convention() == CallingConvention.BODY_ONLY

    prod_api_mapper = APIPathMapper()
    assert prod_api_mapper.get_default_calling_convention() == CallingConvention.MIXED


def test_lookup_api_path_no_remapping():
    api_mapper = APIPathMapper()
    api_path = api_mapper.get_api_path('/refdata/asset/summaries')
    assert api_path == '/refdata/asset/summaries'


def test_lookup_api_path_with_remapping_prod():
    api_mapper = APIPathMapper()
    api_path = api_mapper.get_api_path('/risk/market/factor/covariance')
    assert api_path == '/risk/factor/covariance'


def test_lookup_api_path_with_remapping_dev_given_new():
    api_mapper = APIPathMapper(Environment.DEV)
    api_path = api_mapper.get_api_path('/risk/market/factor/covariance')
    assert api_path == '/risk/market/factor/covariance'


def test_lookup_api_path_with_remapping_dev_given_old():
    api_mapper = APIPathMapper(Environment.DEV)
    api_path = api_mapper.get_api_path('/risk/factor/covariance')
    assert api_path == '/risk/market/factor/covariance'


def test_lookup_api_path_unknown():
    api_mapper = APIPathMapper()
    with pytest.raises(UnknownOperationError):
        api_mapper.get_api_path('/foo/bar')


def test_lookup_api_path_unsupported():
    api_mapper = APIPathMapper()
    with pytest.raises(UnsupportedOperationError):
        api_mapper.get_api_path('/valuation/portfolio/compute')
