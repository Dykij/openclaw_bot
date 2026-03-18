import math
import logging
from typing import List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

class HawkesProcess:
    """
    Simulates a Hawkes Process for high-frequency trading microstructure.
    Models self-exciting phenomena like volume spikes.
    λ(t) = μ(t) + Σ α * e^(-β * (t - t_i))
    """
    def __init__(self, mu: float = 0.1, alpha: float = 0.5, beta: float = 1.2):
        self.mu = mu        # Background intensity (exogenous noise)
        self.alpha = alpha  # Excitation factor
        self.beta = beta    # Decay rate
        
        # Keep track of timestamps of past events
        self.event_times: List[float] = []

    def add_event(self, t: float):
        """Register a new trade/volume spike at time t."""
        self.event_times.append(t)

    def current_intensity(self, t: float) -> float:
        """
        Calculates the instantaneous intensity λ(t).
        Used as a feature in the Hidden Markov Model observations.
        """
        intensity = self.mu
        for t_i in self.event_times:
            if t_i < t:
                intensity += self.alpha * math.exp(-self.beta * (t - t_i))
        return intensity
        
    def prune_old_events(self, t: float, window: float = 3600.0):
        """Optimization: Remove events too old to matter."""
        cutoff = t - window
        self.event_times = [et for et in self.event_times if et > cutoff]


class HiddenMarkovModel:
    """
    Hidden Markov Model trained via Baum-Welch and decoded via Viterbi.
    Combines price changes, Hawkes intensity, and LLM sentiment.
    """
    def __init__(self, n_hidden_states: int = 3, n_observations: int = 5):
        self.n_states = n_hidden_states
        self.n_obs = n_observations
        
        # λ = (pi, A, B)
        # pi: Initial probabilities
        self.pi = np.ones(self.n_states) / self.n_states
        
        # A: Transition matrix P(Z_{t+1} | Z_t)
        self.A = np.ones((self.n_states, self.n_states)) / self.n_states
        
        # B: Emission matrix P(X_t | Z_t)
        self.B = np.ones((self.n_states, self.n_obs)) / self.n_obs
        
        self.is_trained = False

    async def hot_reloader(self, redis_url: str = "redis://127.0.0.1:6379/0"):
        """
        Listens to the CPU-bound re-calibration script. 
        Hot-swaps matrices live without dropping GPU inference frames.
        """
        import redis.asyncio as redis
        import orjson
        import asyncio
        
        logger.info("Initializing HMM Redis Hot-Reloader...")
        while True:
            try:
                r = redis.Redis.from_url(redis_url)
                async with r.pubsub() as pubsub:
                    await pubsub.subscribe('models:parameters')
                    async for message in pubsub.listen():
                        if message['type'] == 'message':
                            payload = orjson.loads(message['data'])
                            
                            self.pi = np.array(payload.get('pi', self.pi))
                            self.A = np.array(payload.get('A', self.A))
                            self.B = np.array(payload.get('B', self.B))
                            self.is_trained = True
                            
                            logger.info("✅ HMM parameters successfully hot-swapped from Redis.")
            except Exception as e:
                logger.error(f"HMM Reloader connection dropped: {e}")
                await asyncio.sleep(5)

    def train_baum_welch(self, obs_sequence: List[int], n_iter: int = 50):
        """
        Standard Expectation-Maximization to calibrate pi, A, and B from historical sequences.
        (Simplified implementation for architecture skeleton)
        """
        T = len(obs_sequence)
        
        for iteration in range(n_iter):
            # Forward pass (alpha)
            alpha = np.zeros((T, self.n_states))
            alpha[0, :] = self.pi * self.B[:, obs_sequence[0]]
            alpha[0, :] /= np.sum(alpha[0, :])
            
            for t in range(1, T):
                for j in range(self.n_states):
                    alpha[t, j] = self.B[j, obs_sequence[t]] * np.sum(alpha[t-1, :] * self.A[:, j])
                alpha[t, :] /= np.sum(alpha[t, :])
                
            # Backward pass (beta)
            beta = np.zeros((T, self.n_states))
            beta[T-1, :] = 1.0
            
            for t in range(T-2, -1, -1):
                for i in range(self.n_states):
                    beta[t, i] = np.sum(self.A[i, :] * self.B[:, obs_sequence[t+1]] * beta[t+1, :])
                beta[t, :] /= np.sum(beta[t, :])
                
            # Update step (gamma and xi)
            gamma = alpha * beta
            gamma /= np.sum(gamma, axis=1, keepdims=True)
            
            # Re-estimate parameters (A, B, pi) simplified updates
            self.pi = gamma[0, :]
            
            # In a full Baum-Welch, A and B are updated using xi. 
            # We omit the dense math here for brevity of the skeleton.
            
        self.is_trained = True
        logger.info("HMM calibration complete via Baum-Welch.")

    def decode_viterbi(self, obs_sequence: List[int]) -> List[int]:
        """
        Finds the most likely hidden state sequence given observations.
        Used for live trading to determine the current Market Regime (Z_t).
        """
        T = len(obs_sequence)
        
        # DP tables
        T1 = np.zeros((self.n_states, T))
        T2 = np.zeros((self.n_states, T), dtype=int)
        
        # Initialize
        T1[:, 0] = self.pi * self.B[:, obs_sequence[0]]
        
        for t in range(1, T):
            for j in range(self.n_states):
                # Probabilities
                probs = T1[:, t-1] * self.A[:, j] * self.B[j, obs_sequence[t]]
                T1[j, t] = np.max(probs)
                T2[j, t] = np.argmax(probs)
                
        # Backtrace
        z = np.zeros(T, dtype=int)
        z[T-1] = np.argmax(T1[:, T-1])
        
        for t in range(T-1, 0, -1):
            z[t-1] = T2[z[t], t]
            
        return z.tolist()

class MarketRegimePredictor:
    """
    Unifies the HMM and Hawkes outputs.
    """
    def __init__(self):
        self.hawkes = HawkesProcess()
        self.hmm = HiddenMarkovModel()
        
    def determine_regime(self, current_time: float, recent_observations: List[int]) -> int:
        """
        1. Calculate Hawkes excitement lambda(t)
        2. Combine with LLM confidence signals into a discrete observation index.
        3. Pass to HMM Viterbi decoder.
        4. Return the predicted state index Z_t.
        """
        intensity = self.hawkes.current_intensity(current_time)
        
        # If intensity is extremely high, we might force a specific observation state (e.g. "high volatility")
        if intensity > 1.5:
            recent_observations.append(self.hmm.n_obs - 1) # Highest discrete state
            
        if not recent_observations:
            return 0 # Default neutral state
            
        regime_sequence = self.hmm.decode_viterbi(recent_observations)
        return regime_sequence[-1] # Return the most recent state Z_t
