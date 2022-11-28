from serenity_sdk.client import (APIPathMapper, Environment)


def test_lookup_api_path_no_remapping():
    api_mapper = APIPathMapper()
    api_path = api_mapper.get_api_path('/refdata/asset/summaries')
    assert api_path == '/refdata/asset/summaries'


def test_lookup_api_path_with_remapping_dev_given_new():
    api_mapper = APIPathMapper(Environment.DEV)
    api_path = api_mapper.get_api_path('/risk/market/factor/covariance')
    assert api_path == '/risk/market/factor/covariance'


def test_lookup_api_path_with_remapping_dev_given_old():
    api_mapper = APIPathMapper(Environment.DEV)
    api_path = api_mapper.get_api_path('/risk/factor/covariance')
    assert api_path == '/risk/market/factor/covariance'
