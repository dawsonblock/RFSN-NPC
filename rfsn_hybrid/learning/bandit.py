"""
Contextual bandit learner for action selection.

Implements LinUCB (Linear Upper Confidence Bound) algorithm
with bounded parameters and deterministic exploration.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import math


@dataclass
class BanditArm:
    """
    An arm (action) in the bandit problem.
    
    Tracks statistics for LinUCB algorithm.
    
    Attributes:
        action_id: Identifier for this action
        theta: Weight vector (feature weights)
        A: Feature covariance matrix (as dict for simplicity)
        b: Reward-weighted feature sum
        n: Number of times this arm was pulled
    """
    action_id: str
    theta: Dict[str, float] = field(default_factory=dict)
    A_diag: Dict[str, float] = field(default_factory=dict)  # Diagonal only for efficiency
    b: Dict[str, float] = field(default_factory=dict)
    n: int = 0
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            "action_id": self.action_id,
            "theta": self.theta,
            "A_diag": self.A_diag,
            "b": self.b,
            "n": self.n,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "BanditArm":
        """Deserialize from dictionary."""
        return cls(
            action_id=data["action_id"],
            theta=data.get("theta", {}),
            A_diag=data.get("A_diag", {}),
            b=data.get("b", {}),
            n=data.get("n", 0),
        )


class LinUCBBandit:
    """
    Linear Upper Confidence Bound contextual bandit.
    
    Features:
    - Context-dependent action selection
    - Exploration-exploitation tradeoff via UCB
    - Bounded parameter updates
    - Deterministic with seeded PRNG
    
    This is a simplified version using diagonal covariance matrices
    for efficiency and bounded memory.
    """
    
    def __init__(
        self,
        alpha: float = 0.2,
        lambda_reg: float = 1.0,
        prng_seed: Optional[int] = None,
    ):
        """
        Initialize LinUCB bandit.
        
        Args:
            alpha: Exploration parameter (higher = more exploration)
            lambda_reg: L2 regularization parameter
            prng_seed: Random seed for deterministic behavior
        """
        self.alpha = max(0.0, min(2.0, alpha))  # Clamp exploration
        self.lambda_reg = max(0.01, min(10.0, lambda_reg))
        
        # Deterministic PRNG
        self.rng = random.Random(prng_seed)
        
        # Arms (actions) indexed by action_id
        self.arms: Dict[str, BanditArm] = {}
        
        # Statistics
        self.total_pulls = 0
        self.total_reward = 0.0
    
    def score_actions(
        self,
        context: Dict[str, float],
        action_ids: List[str],
    ) -> Dict[str, float]:
        """
        Score each action given the context.
        
        Uses LinUCB: score = theta^T x + alpha * sqrt(x^T A^-1 x)
        
        Args:
            context: Feature dictionary
            action_ids: List of candidate action IDs
            
        Returns:
            Dictionary mapping action_id -> score
        """
        scores = {}
        
        for action_id in action_ids:
            # Initialize arm if not seen before
            if action_id not in self.arms:
                self.arms[action_id] = BanditArm(action_id=action_id)
            
            arm = self.arms[action_id]
            
            # Compute expected reward: theta^T x
            expected_reward = self._dot_product(arm.theta, context)
            
            # Compute uncertainty: alpha * sqrt(x^T A^-1 x)
            # Simplified using diagonal approximation
            uncertainty = self._compute_ucb_bonus(arm, context)
            
            # LinUCB score
            scores[action_id] = expected_reward + self.alpha * uncertainty
        
        return scores
    
    def update(
        self,
        context: Dict[str, float],
        action_id: str,
        reward: float,
    ) -> None:
        """
        Update the bandit model based on observed reward.
        
        Args:
            context: Feature dictionary used for selection
            action_id: Action that was taken
            reward: Observed reward (-1.0 to 1.0)
        """
        # Clamp reward
        reward = max(-1.0, min(1.0, reward))
        
        # Get or create arm
        if action_id not in self.arms:
            self.arms[action_id] = BanditArm(action_id=action_id)
        
        arm = self.arms[action_id]
        
        # Initialize A and b if needed
        for feature in context.keys():
            if feature not in arm.A_diag:
                arm.A_diag[feature] = self.lambda_reg
            if feature not in arm.b:
                arm.b[feature] = 0.0
            if feature not in arm.theta:
                arm.theta[feature] = 0.0
        
        # Update A (diagonal): A += x * x^T (diagonals only)
        for feature, value in context.items():
            arm.A_diag[feature] += value * value
        
        # Update b: b += r * x
        for feature, value in context.items():
            arm.b[feature] += reward * value
        
        # Update theta: theta = A^-1 b (element-wise for diagonal)
        for feature in arm.theta.keys():
            if arm.A_diag[feature] > 0:
                arm.theta[feature] = arm.b[feature] / arm.A_diag[feature]
        
        # Update statistics
        arm.n += 1
        self.total_pulls += 1
        self.total_reward += reward
        
        # Clamp theta values to prevent instability
        for feature in arm.theta.keys():
            arm.theta[feature] = max(-2.0, min(2.0, arm.theta[feature]))
    
    def _dot_product(self, weights: Dict[str, float], features: Dict[str, float]) -> float:
        """Compute dot product between weight and feature vectors."""
        result = 0.0
        for feature, value in features.items():
            if feature in weights:
                result += weights[feature] * value
        return result
    
    def _compute_ucb_bonus(self, arm: BanditArm, context: Dict[str, float]) -> float:
        """
        Compute UCB exploration bonus.
        
        Simplified version using diagonal covariance approximation.
        """
        uncertainty = 0.0
        for feature, value in context.items():
            if feature in arm.A_diag and arm.A_diag[feature] > 0:
                # x^T A^-1 x ≈ sum(x_i^2 / A_ii)
                uncertainty += (value * value) / arm.A_diag[feature]
        
        return math.sqrt(max(0.0, uncertainty))
    
    def get_statistics(self) -> Dict:
        """Get learning statistics."""
        return {
            "total_pulls": self.total_pulls,
            "total_reward": self.total_reward,
            "avg_reward": self.total_reward / max(1, self.total_pulls),
            "num_arms": len(self.arms),
            "alpha": self.alpha,
        }
    
    def reset(self) -> None:
        """Reset all learning state."""
        self.arms = {}
        self.total_pulls = 0
        self.total_reward = 0.0
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            "alpha": self.alpha,
            "lambda_reg": self.lambda_reg,
            "arms": {aid: arm.to_dict() for aid, arm in self.arms.items()},
            "total_pulls": self.total_pulls,
            "total_reward": self.total_reward,
        }
    
    @classmethod
    def from_dict(cls, data: Dict, prng_seed: Optional[int] = None) -> "LinUCBBandit":
        """Deserialize from dictionary."""
        bandit = cls(
            alpha=data.get("alpha", 0.2),
            lambda_reg=data.get("lambda_reg", 1.0),
            prng_seed=prng_seed,
        )
        
        # Restore arms
        arms_data = data.get("arms", {})
        bandit.arms = {
            aid: BanditArm.from_dict(arm_data)
            for aid, arm_data in arms_data.items()
        }
        
        # Restore statistics
        bandit.total_pulls = data.get("total_pulls", 0)
        bandit.total_reward = data.get("total_reward", 0.0)
        
        return bandit
