

def flat_forward(t, y):

    ff = y.copy()
    for i in range(1, len(t)):
        ff[i] = (y[i]*t[i] - y[i-1]*t[i-1])/(t[i]-t[i-1])
    return ff
