#%%
import numpy as np
import scipy as sp

'''======================= HELPER FUNCTIONS ======================='''

# Construct B matrix as seen in 3.1.2 of the reference paper
def constructB(d, n):
    Bt = np.zeros((d, n))
    if n == 1:
        Bt[0,0] = 1
    else:
        num = np.arange(d)
        Bt[num, num+1] = 1
    B = Bt.T
    return B

# Construct similar B matrix as above, but for second order monomials
def constructSecondOrderB(s, n):
    Bt = np.zeros((s, n))
    if n == 1:
        Bt[0,0] = 1
    else:
        row = 0
        for i in range(d+1, d+1+s):
            Bt[row,i] = 1
            row += 1
    B = Bt.T
    return B

'''======================= CONSTRUCT DATA MATRIX ======================='''

from brownian import brownian

# The Wiener process parameter.
delta = 2
# Total time.
T = 10.0
# Number of steps.
N = 1000
# Time step size
dt = T/N
# Number of realizations to generate.
m = 20
# Create an empty array to store the realizations.
X = np.empty((m, N+1))
# Initial values of x.
X[:, 0] = 50
brownian(X[:, 0], N, dt, delta, out=X[:, 1:])

#%%
'''======================= SETUP/DEFINITIONS ======================='''
import observables
from sympy import symbols
from sympy.polys.monomials import itermonomials, monomial_count
from sympy.polys.orderings import monomial_key

d = X.shape[0]
m = X.shape[1]
s = int(d*(d+1)/2) # number of second order poly terms
rtol=1e-02
atol=1e-02
psi = observables.monomials(2)
# x_str = ""
# for i in range(d):
#     x_str += 'x_' + str(i) + ', '
# x_syms = symbols(x_str)
# M = itermonomials(x_syms, 2)
# sortedM = sorted(M, key=monomial_key('grlex', np.flip(x_syms)))
# print(sortedM)
Psi_X = psi(X)
nablaPsi = psi.diff(X)
nabla2Psi = psi.ddiff(X)
print("nablaPsi Shape", nablaPsi.shape)
n = Psi_X.shape[0]

#%%
'''======================= COMPUTATIONS ======================='''

# This computes dpsi_k(x) exactly as in the paper
# t = 1 is a placeholder time step, not really sure what it should be
def dpsi(k, l, t=1):
    difference = (X[:, l+1] - X[:, l])
    term_1 = (1/t) * (difference)
    term_2 = nablaPsi[k, :, l]
    term_3 = (1/(2*t)) * (difference.reshape(-1, 1) @ difference.reshape(1, -1))
    term_4 = nabla2Psi[k, :, :, l]
    return np.dot(term_1, term_2) + np.tensordot(term_3, term_4)
vectorized_dpsi = np.vectorize(dpsi)

# Construct \text{d}\Psi_X matrix
dPsi_X = np.empty((n, m))
for column in range(m-1):
    dPsi_X[:, column] = vectorized_dpsi(range(n), column)

#%%
# Calculate Koopman generator approximation
train = int(m * 0.8)
test = m - train
M = dPsi_X[:, :train] @ np.linalg.pinv(Psi_X[:, :train]) # \widehat{L}^\top
L = M.T # estimate of Koopman generator

def check_symmetric(a, rtol=1e-02, atol=1e-02):
    return np.allclose(a, a.T, rtol=rtol, atol=atol)
print("Is L approximately symmetric:", check_symmetric(L))

# Eigen decomposition
eig_vals, eig_vecs = sp.sparse.linalg.eigs(L) if sp.sparse.issparse(L) else sp.linalg.eig(L)
# Compute eigenfunction matrix
eig_funcs = (eig_vecs).T @ Psi_X

#%% Construct estimates of drift vector (b) and diffusion matrix (a) using two methods:
# 1. Directly from dictionary functions without dimension reduction  
# 2. Construct eigendecomposition and restrict its order

# Construct B matrix that selects first-order monomials (except 1) when multiplied by list of dictionary functions
B = constructB(d, n)
# Construct second order B matrix (selects second-order monomials)
second_orderB = constructSecondOrderB(s, n)

# Computed b function (sometimes denoted by \mu) without dimension reduction
L_times_B_transposed = (L @ B).T
def b(l):
    return L_times_B_transposed @ Psi_X[:, l] # (k,)

# The b_v2 function allows for heavy dimension reduction
# default is reducing by 90% (taking the first n/10 eigen-parts)

# Calculate Koopman modes
V = B.T @ np.linalg.inv((eig_vecs).T)

# TODO: Figure out correct place to take reals
def b_v2(l, num_dims=n//10):
    res = 0
    for ell in range(n-1, n-num_dims, -1):
        res += eig_vals[ell] * eig_funcs[ell, l] * V[:, ell] #.reshape(-1, 1)
    return np.real(res)

# the following a functions compute the diffusion matrices as flattened vectors
# this was calculated in a weird way, so it could have issues...
L_times_second_orderB_transpose = (L @ second_orderB).T

def a(l):
    return (L_times_second_orderB_transpose @ Psi_X[:, l]) - \
        (second_orderB.T @ nablaPsi[:, :, l] @ b(l))

def a_v2(l):
    return (L_times_second_orderB_transpose @ Psi_X[:, l]) - \
        (second_orderB.T @ nablaPsi[:, :, l] @ b_v2(l))

#%% Reshape a matrix and perform some tests
# Function to reshape the a vector at a specific snapshot index
# I think it needs a rewrite
# def evalAMatrix(l):
#     a_matrix = np.zeros((d, d))
#     a_l = a(l)
#     for p in range(d+1, d+1+s):
#         monomial = str(sortedM[p])
#         i = 0
#         j = 0
#         split_mon = monomial.split('**')
#         if len(split_mon) > 1:
#             i = int(split_mon[0][-1])
#             j = int(split_mon[0][-1])
#         else:
#             split_mon = monomial.split('*')
#             i = int(split_mon[0][-1])
#             j = int(split_mon[1][-1])

#         a_matrix[i,j] = a_l[p-d-1]
#         a_matrix[j,i] = a_l[p-d-1]

#     return a_matrix

# for j in range(0, n+1):
#     print(np.count_nonzero(evalAMatrix(j)))

# diagAMat = np.zeros(d,d)
# for j in range(0, n+1):
#     evaldA = evalAMatrix(n)
#     for i in range(0, d):
#         diagAMat[i,i] = evaldA[i,i]
#     print(np.allclose(diagAMat,evalAMatrix(n), rtol=rtol, atol=atol))

# Oh no... it's not positive definite
# Some calculation must be wrong
# decomp = sp.linalg.cholesky(evalAMatrix(0))

# def sigma(l):
#     # Attempt at work around without Cholesky
#     U, S, V = np.linalg.svd(evalAMatrix(l))
#     square_S = np.diag(S**(1/2))
#     sigma = V @ square_S @ V.T
#     return sigma

# # snapshots by coins
# # rows are snapshots
# epsilons = np.empty((d, m, 1))
# def epsilon_t(l):
#     return np.linalg.inv(sigma(l-1).T @ sigma(l-1)) @ sigma(l-1).T @ (X[:, l].reshape(-1, 1) - b_v2(l-1))

#     for snapshot_index in range(1, epsilons.shape[1], 1):
#         print("snapshot ", snapshot_index)
#         epsilons[:, snapshot_index] = epsilon_t(snapshot_index)

# # Epsilons produced make no sense...
# # We are looking for numbers that follow a
# # normal distribution but these are way off

# epsilons = np.array(epsilons)
# print(epsilons)
# print(epsilons.shape)