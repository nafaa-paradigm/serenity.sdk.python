import numpy as np
from scipy.stats import norm


def bs_pv_fwd(F, sigma, K, T, kind):
    """
    Black 76

    :param F: forward price
    :param sigma: implied vol
    :param K: strike
    :param T: time-to-expiry
    :param kind: +1 (call), -1 (put)
    :return: forward pv
    """
    f = np.log(F/K)
    sigma_sq_T = sigma * np.sqrt(T)
    dp = f/sigma_sq_T + sigma_sq_T/2.0
    dn = f/sigma_sq_T - sigma_sq_T/2.0
    return kind * (F * norm.cdf(kind*dp) - K * norm.cdf(kind*dn))


def bs_pv(S, sigma, r, p, K, T, kind):
    """
    Black-Scholes

    :param S: spot
    :param sigma: implied vol
    :param r: discounting rate
    :param p: projection rate
    :param K: strike
    :param T: time-to-expiry
    :param kind: +1 (call), -1 (put)
    :return: present pv
    """
    F = np.exp(p*T) * S
    D = np.exp(-r*T)
    return D*bs_pv_fwd(F, sigma, K, T, kind)


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
