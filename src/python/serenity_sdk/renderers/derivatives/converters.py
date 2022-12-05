from typing import List, Dict, Any
import pandas as pd


def _get_obj_in_kw(obj: object, no_underscores=True) -> dict:
    """
    to convert an object in a kw dictionary

    :param obj: object
    :param no_underscores: whether to exclude the variabes starting with '_', defaults to True
    :return: dictionary
    """
    if no_underscores:
        return {variable: value for variable, value in vars(obj).items()
                if not variable.startswith('_')}
    else:
        return {variable: value for variable, value in vars(obj).items()}


def convert_object_list_to_df(obj_list: List[object], no_underscores=True) -> pd.DataFrame:
    """
    to convert a list of object into a pandas' DataFrame tabular form

    :param obj_list: a list of objects
    :param no_underscores: whether to exclude the variabes starting with '_', defaults to True
    :return: pd.DataFrame
    """

    df = pd.DataFrame([_get_obj_in_kw(obj, no_underscores) for obj in obj_list])
    return df


def convert_object_dict_to_df(obj_dict: Dict[Any, object], no_underscores=True) -> pd.DataFrame:
    """
    to convert a list of object into a pandas' DataFrame tabular form

    :param obj_dict: a dictionary of objects
    :param no_underscores: whether to exclude the variabes starting with '_', defaults to True
    :return: pd.DataFrame
    """

    df = pd.DataFrame({k: _get_obj_in_kw(obj, no_underscores) for k, obj in obj_dict.items()})
    return df


def convert_object_to_ds(obj: object, no_underscores=True) -> pd.Series:
    """
    to convert an object into a pandas' Series form

    :param obj: object
    :param no_underscores: whether to exclude the variabes starting with '_', defaults to True
    :return: pd.Series
    """
    return pd.Series(_get_obj_in_kw(obj))
