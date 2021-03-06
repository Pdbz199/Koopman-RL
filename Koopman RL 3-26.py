# Koopman RL Report: 03.26.2021

## OpenAI Gym Koopman Prediction Application: CartPole
'''
To see how well (and quickly) the Koopman operator could predict future states, I used a Q-learning agent that learned a near-optimal policy for the CartPole environment and fit an approximate Koopman operator to it.
'''
'''
X = np.load('state-action-inputs.npy') # 20,000 entries
X = X[:int(X.shape[0]*0.0015)] # 30 points!

# Fit Koopman operator using closed-form solution to DMD
optdmd = OptDMD(svd_rank=15)
model_optdmd = pk.Koopman(regressor=optdmd)
model_optdmd.fit(X)
'''

'''
import math
from sklearn.preprocessing import KBinsDiscretizer
from typing import Tuple
import gym
env = gym.make('CartPole-v0')
koopEnv = gym.make('CartPole-v0')

Q_table = np.load('Q_table.npy')

n_bins = ( 6, 12 )
lower_bounds = [ env.observation_space.low[2], -math.radians(50) ]
upper_bounds = [ env.observation_space.high[2], math.radians(50) ]

def discretizer( _, __, angle, pole_velocity ) -> Tuple[int,...]:
    """Convert continuous state into a discrete state"""
    est = KBinsDiscretizer(n_bins=n_bins, encode='ordinal', strategy='uniform')
    est.fit([ lower_bounds, upper_bounds ])
    return tuple( map( int, est.transform([[ angle, pole_velocity ]])[0] ) )

def policy(state: tuple):
    """ Choosing an action on epsilon-greedy policy """
    return np.argmax(Q_table[state])
'''

'''
current_state = discretizer(*env.reset())
current_stateK = discretizer(*koopEnv.reset())
action = policy(current_state)
actionK = policy(current_state)

q_learner_reward = 0
koopman_reward = 0

for i in range(num_steps):
    # environment details
    observation, reward, done, _ = env.step(action)
    observationK, rewardK, doneK, _ = koopEnv.step(actionK)

    # keep track of rewards
    q_learner_reward += reward
    koopman_reward += rewardK

    # discretize state - hoping generator won't have to!
    new_state = discretizer(*observation)
    new_stateK = discretizer(*observationK)

    # get actions
    next_action = policy(new_state)
    prediction = model_optdmd.predict(np.array([*list(current_stateK), actionK]))
    prediction = np.round(np.real(prediction))
    next_actionK = int(prediction[-1])

    # update environments
    action = next_action
    actionK = next_actionK
    current_state = new_state
    current_stateK = new_stateK

print("Q rewards:", q_learner_reward)
print("K rewards:", koopman_reward)
'''

'''
We can see that the rewards are both 200 which means that the Koopman predictor works very well given good data, though there are plenty of papers on the subject. One thing we may want to look into is how well we can learn a controller from the Koopman operator, but since we are focused on the Generator operator, what we really want to see now is the predictive power of the Koopman Generator and how it can be used for control!
'''

## Stochastic Koopman Generator Analysis
'''
We simulated some paths from a standard Brownian Motion (drift coefficient 0 and diffusion coefficient 1) and then tried 3 different methods from two papers: 
+ Klus et al 2020 <https://arxiv.org/pdf/1909.10638.pdf>
+ Li and Duan 2020 <https://arxiv.org/ftp/arxiv/papers/2005/2005.03769.pdf>
'''
### Simlulation of Brownian Data
'''
We simulated 20 paths of standard BM each with 5000 steps in a time interval of size 5000 so that the time step was 1. We took each of these 20 paths to be a state variable in our state vector. Our state vector is thus comprised of 20 iid BMs. Formally, our state vector dynamics have the form
$$
    \text{d}\tilde X_t = b\text{d}t + \Sigma\text{d}W_t
$$
where $b$ is a $n=20$ dimensional vector of 0s and $\Sigma$ is a $n\times n$ identity matrix.
'''
'''
from brownian import brownian

# The Diffusion process parameter.
sigma = 1
# Total time.
T = 20000.0
# Number of steps.
N = 20000
# Time step size
dt = T/N
# Number of realizations to generate.
m = 20
# Create an empty array to store the realizations.
X = np.empty((m, N+1))
# Initial values of x.
X[:, 0] = 50
brownian(X[:, 0], N, dt, sigma, out=X[:, 1:])
Z = np.roll(X,-1)[:, :-1]
X = X[:, :-1]
'''

### Fitting the BM data using Generator EDMD (gEDMD) from Klus et al. 2020
'''
From the learner's point of view, we assume that we are in the class of continuous Markov processes and thus that the generator is of the form
$$
    \mathcal{L}f = b\cdot\nabla_{\tilde x}f + \frac{1}{2}a:\nabla^2_{\tilde x}f 
    %= \sum_{i=1}^n b_i\frac{\partial f}{\partial \tilde{x}_i} + \frac{1}{2} \sum_{i=1}^n \sum_{j=1}^n a_{ij} \frac{\partial^2 f}{\partial \tilde{x}_i \partial \tilde{x}_j},
$$
where $a = \sigma \sigma^\top$, $\nabla^2_x$ denotes the Hessian, and $:$ denotes the double dot product. Applying the generator to each dictionary function \psi_k and assuming that we have access to a single ergodic sample with time step $dt= 1$, we can use the following finite difference estimator of $\mathcal{L}\psi_k$:
$$
\widehat{d\psi_k}(\tilde{\mathbf{x}}_l) = \frac{1}{t}(\tilde{\mathbf{x}}_{l+1} - \tilde{\mathbf{x}}_l) \cdot \nabla\psi_k(\tilde{\mathbf{x}}_l) + \frac{1}{2t} \Big[(\tilde{\mathbf{x}}_{l+1} - \tilde{\mathbf{x}}_l)(\tilde{\mathbf{x}}_{l+1} - \tilde{\mathbf{x}}_l)^\top\Big] : \nabla^2 \psi_k(\tilde{\mathbf{x}}_l)
$$
Note that we are adopting Klus's notation here only for reference. The stochastic total differential $d\psi_k$ is a different object that the generator of the Koopman operator they are related in that the drift of the stochastic total differential is the same thing as the generator.

Next, we set up matrices for the dictionary and the generator applied to it: 
$$
    \Psi_{\mathbf{X}} = \begin{bmatrix} 
                        \psi_1(\tilde{\mathbf{x}}_1) & \dots & \psi_1(\tilde{\mathbf{x}}_m) \\
                        \vdots & \ddots & \vdots \\
                        \psi_k(\tilde{\mathbf{x}}_1) & \dots & \psi_k(\tilde{\mathbf{x}}_m) 
                    \end{bmatrix},
$$
$$
    \text{d}\Psi_{\mathbf{X}} = \begin{bmatrix} 
                        \text{d}\psi_1(\tilde{\mathbf{x}}_1) & \dots & \text{d}\psi_1(\tilde{\mathbf{x}}_m) \\
                        \vdots & \ddots & \vdots \\
                        \text{d}\psi_k(\tilde{\mathbf{x}}_1) & \dots & \text{d}\psi_k(\tilde{\mathbf{x}}_m) 
                    \end{bmatrix}
$$

The idea behind generator EDMD is that we assume that the genertor applied to the the dictionary functions can be ("approximately") expressed as a linear combination of the dictionary functions and find the coeficients of those linear combinations by minimizing $|| \text{d}\Psi_{\tilde{\mathbf{X}}} - M\Psi_{\tilde{\mathbf{X}}} ||_F$ which leads to the least-squares approximation
$$ 
M = \text{d}\Psi_{\tilde{\mathbf{X}}} \Psi^{+}_{\tilde{\mathbf{X}}} = (\text{d}\Psi_{\tilde{\mathbf{X}}}\Psi_{\tilde{\mathbf{X}}}^\top)(\Psi_{\tilde{\mathbf{X}}}\Psi_{\tilde{\mathbf{X}}}^\top)^+ $$
$$
Thus, we obtain the empirical estimate $L=M^T$ of the Koopman generator $\mathcal{L}$.

For the dictionary space, we chose monomials of up to order 2. We also tried monomials of order 1, which is not sufficient to pick up the diffusion term, but was successful at picking up the drift quicker. We hypothesize that this is because there are fewer terms in the regression over the dictionary functions.

Note: we used Klus's d3 repo to create the PsiX and dPsiX objects
'''
'''
Put in code for constructing PsiX, dPsiX, M, L here
'''

'''
Specifically, to identify $b(x)$
\begin{enumerate}
    \item Get eigenfunctions $\xi_i$ of $\widehat{L}$ and store them in $\Xi = \{ \xi_1, \cdots, \xi_n \}$.
    \item Express eigenfunctions in terms of the dictionary $\psi(x) = \Xi^\top \psi(x)$
    \item Calculate Koopman modes $V = B^\top \Xi^{-\top}$
    \item Express drift in terms of reduced order eigenexpansion (we decided to set our default cutoff to be one tenth of the total eigenfunctions)
    $$ (\mathcal{L}g) (x) = b(x) \approx \sum_{\ell = 1}^{cutoff} \lambda_\ell \psi_\ell(x) v_\ell $$
    where $v_\ell$ is the $\ell$th column vector of $V$.
    \item Alternatively we can use the Koopman generator approximation $\widehat{L}$ directly and get drift $b$:
    $$ \mathcal{L}g(x) = b(x) \approx (LB)^\top  \psi(x) $$
\end{enumerate}
'''
'''
\item {\bf Detailed Derivation of covariance matrix $a$}\\
\begin{enumerate}
    \item Set the observable, $g(x) (\in \mathbb{R}^w) = $ second order monomials
    \item Find $B \in \mathbb{R}^{s \times w}$ s.t. $B^\top \psi(x) = g(x)$
    \item 
    \begin{align*}
        \mathcal{L}g(x) &= \nabla g(x) b(x) + \text{vec}(a) \text{ where vec(}a\text{) is a vectorized (flattened) a matrix}.\\
        &= \nabla(B^\top \psi(x)) b(x) + \text{vec}(a)\\
        &= B^\top \nabla \psi(x) b(x) + \text{vec}(a) (\text{we also note that the order of }\text{vec}(a)\text{ matches the order of }g(x))\\
    \end{align*}
    Using $\mathcal{L}g(x) \approx (\widehat{L} B)^\top \psi(x)$
    $$ \implies \text{vec}(a) \approx (\widehat{L}B)^\top \psi(x) - B^\top \nabla \psi(x) \widehat{b}(x) $$
    \item Given an estimate for $\widehat{b}(x)$, we can estimate $a(x)$
    $$ \widehat{a} = (\widehat{L} B)^\top \psi(x) - B \nabla \psi(x) \widehat{b}(x) $$
\end{enumerate}
'''

''' RESULTS OF b AND b_v2
By calculating the b's separetely and printing out their values, we could tell that they were (relatively) close to zero (numbers were around the +/- 1e-2 area) which is exactly what we were hoping to find. It is nice that the heavily reduced b_v2 performed well because it means that we can actually take advantage of the computational benefits.
'''

''' RESULTS OF a AND a_v2
Unfortunately, the results of both a and a_v2 are far from identity matrices. In fact, most of the entries were on the scale of +/- 1e1
'''

''' RESULTS OF b_v3
This new version of b reached good results, but not quite as good as either b or b_v2 from earlier. The entries were on the scale of +/- 1e-1.
'''

''' RESULTS OF a_v3
This version of a  achieved the results we were hoping for and returned near identity matrices with numbers of about +/- 1e-1 in the entries outside the diagonal.
'''


'''Theory for Lu and Duan (2021)
We tried one final appoach that was adapted from Lu and Duan 2021. They exploit the Perron-Frobenius operator (PF)(solution to the Fokker-Planck equation) to analyze systems with non-Gaussian Levy noise in addition to Gaussian noise. We restricted their method to analyze our system which just has Guassian noise. We will describe the estimation procedure here, but for the theory, please see their paper.

First, we assume that the drift can be approximated as a linear combination of the dictionary functions, $b(x) \approx \psi(x)^\top C$ where $C$ is a $k\times d$ matrix. Next, we collect a sample of the finite differences between observations $S\in \mathbb{R}^{d\times m}$ where the jth column vector is
$$
S_j = (x_j - z_j)/h
$$
where $x_j$ is the jth snapshot vector and $z_j=x_{j+h}$ is the associated future value where we take time step $h=1$. To find the coeficient matrix $C$, we solve the following least squares problem
$$
min_{C} ||\Psi_X^\top C - S^\top||_F
$$
which leads to the solution
$$
\hat C = (\Psi_X \Psi_X)^{-1}(\Psi_XB^\top)
$$
'''

'''
Finally, to calculate the diffusion matrix using Li and Duan's approach, we make the same assumption about each element of the diffusion matrix as being approximated as a linear combination of the dictionary functions 
$$
a_{ij}(x) \appox d_ij \cdot \psi(x)
$$
where $d_ij = [d_{ij,1},\, \cdots,\, d_{ij,k}]^\top$. For the diffusion terms, we need to collect samples of the (cross) quadratic variation
$$
B_{ij} = h^{-1}[(x_{i,1}-z_{i,1})(x_{j,1}-z_{j,1})]
$$
where $i$ and $j$ represent the $i$-th and $j$-th components of the snapshot vectors. The resulting least squares problem to find the coeficients $d_{ij}$ for each ($i$, $j$) pair is
$$
||\Psi_X^\top d_{ij} - B_{ij}||
$$
which results in the estimate 
$$
\hat{d}_{ij} = (\Psi_X\Psi_X^\top)^{-1}(\Psi_X B_{ij})
$$
TODO: Figure out how to vectorize/matrix-ize for faster computation!
'''