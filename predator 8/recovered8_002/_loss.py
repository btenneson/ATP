"""Compatibility alias for recovered scikit-learn joblib artifacts.

The recovered prcom policy was serialized with the compiled scikit-learn loss
module recorded under the top-level module name `_loss`.  Current scikit-learn
packages expose those classes as `sklearn._loss._loss`.  Re-exporting them here
lets Python resolve the historical pickle reference without changing the model
parameters or prediction logic.
"""
from sklearn._loss._loss import *  # noqa: F401,F403
