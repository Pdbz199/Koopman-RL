#%%
import observables
import domain
import numpy as np
import scipy as sp
import numba as nb
import estimate_L
from brownian import brownian

#%%
@nb.njit(fastmath=True) #, parallel=True)
def nb_einsum(A, B):
    assert A.shape == B.shape
    res = 0
    for i in range(A.shape[0]):
        for j in range(A.shape[1]):
            res += A[i,j]*B[i,j]
    return res

@nb.njit(fastmath=True)
def dpsi(X, nablaPsi, nabla2Psi, k, l, t=1):
    difference = X[:, l+1] - X[:, l]
    term_1 = (1/t) * (difference)
    term_2 = nablaPsi[k, :, l]
    term_3 = (1/(2*t)) * np.outer(difference, difference)
    term_4 = nabla2Psi[k, :, :, l]
    return np.dot(term_1, term_2) + nb_einsum(term_3, term_4)

@nb.njit(fastmath=True)
def dPsiMatrix(X, nablaPsi, nabla2Psi, k, m):
    dPsi_X = np.zeros((k, m))
    for row in range(k):
        for column in range(m-1):
            dPsi_X[row, column] = dpsi(
                X, nablaPsi, nabla2Psi, row, column
            )
    return dPsi_X

#%% Create data matrices
# The Wiener process parameter.
sigma = 1
# Total time.
T = 10
# Number of steps.
N = 10000
# Time step size
dt = T/N
# Number of realizations to generate.
n = 1
# Create an empty array to store the realizations.
X = np.empty((n, N+1))
# Initial values of x.
X[:, 0] = 50
brownian(X[:, 0], N, dt, sigma, out=X[:, 1:])
Z = np.roll(X,-1)[:, :-1]
X = X[:, :-1]

data = X[:,:8000]
time_delayed_data = Z[:,:8000]

#%%
d = data.shape[0]
m = data.shape[1]
# s = int(d*(d+1)/2) # number of second order poly terms
# rtoler=1e-02
# atoler=1e-02

# psi = observables.monomials(10)

bounds = np.array([[-200, 200]])
boxes = np.array([1000])
Omega = domain.discretization(bounds, boxes)
psi = observables.gaussians(Omega, 1)

Psi_X = psi(data)
Psi_Z = psi(time_delayed_data)
k = Psi_X.shape[0]
nablaPsi = psi.diff(data)
nabla2Psi = psi.ddiff(data)
# B = constructB(d, k)
# second_order_B = constructSecondOrderB(s, k)
dPsi_X = dPsiMatrix(data, nablaPsi, nabla2Psi, k, m)

#%%
M = (dPsi_X @ Psi_X.T) @ np.linalg.pinv(Psi_X @ Psi_X.T)
L = M.T
# The above is from the paper under equation 5 but
# it did not seem to identify the system well

#%%
K = sp.linalg.expm(L)





#%% Klus says to try with Ornstein-Uhlenbeck system
# This was a success!
import observables
import numpy as np
import scipy as sp
from systems import vec_ornstein_uhlenbeck

n = 1 # num paths

_, X = vec_ornstein_uhlenbeck(np.zeros(n), np.full(n, 2), 10000)
Z = np.roll(X,-1)[:, :-1]
X = X[:, :-1]

data = X[:,:8000]
time_delayed_data = Z[:,:8000]

#%%
d = data.shape[0]
m = data.shape[1]
psi = observables.monomials(10)
Psi_X = psi(data)
Psi_Z = psi(time_delayed_data)
k = Psi_X.shape[0]
nablaPsi = psi.diff(data)
nabla2Psi = psi.ddiff(data)
dPsi_X = dPsiMatrix(data, nablaPsi, nabla2Psi, k, m)

#%%
# M = (dPsi_X @ Psi_X.T) @ np.linalg.pinv(Psi_X @ Psi_X.T)
# L = M.T
# L = estimate_L.rrr(Psi_X.T, dPsi_X.T)
# L = estimate_L.SINDy(Psi_X.T, dPsi_X.T, d)
L = estimate_L.gedmd(Psi_X.T, dPsi_X.T, rank=11)

#%%
K = sp.linalg.expm(L)