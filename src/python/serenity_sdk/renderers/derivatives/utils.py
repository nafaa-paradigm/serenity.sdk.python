import numpy as np


def svi_w(k, a, b, r, m, s):
    """
    svi total variance (vol**2 t)

    :param k: log moneyness
    :param a: svi a
    :param b: svi b
    :param r: svi rho
    :param m: svi m
    :param s: svi s
    :return: total variance
    """
    return a + b * (r * (k-m) + np.sqrt((k-m)**2 + s**2))


def svi_vol(k, T, a, b, r, m, s):
    """
    svi volatility

    :param k: log moneyness
    :param T: time-to-expiry
    :param a: svi a
    :param b: svi b
    :param r: svi rho
    :param m: svi m
    :param s: svi s
    :return: volatility
    """
    return np.sqrt(svi_w(k, a, b, r, m, s)/T)
