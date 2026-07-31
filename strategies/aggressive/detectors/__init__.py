"""Aggressive Detectors Package."""
from strategies.aggressive.detectors.base_detector import BaseDetector
from strategies.aggressive.detectors.detector_result import DetectorResult
from strategies.aggressive.detectors.momentum_burst import MomentumBurst
from strategies.aggressive.detectors.vwap_magnet import VWAPMagnet
from strategies.aggressive.detectors.ribbon_ride import RibbonRide
from strategies.aggressive.detectors.compression_break import CompressionBreak
from strategies.aggressive.detectors.velocity_spike import VelocitySpike
from strategies.aggressive.detectors.pullback_quality import PullbackQuality
from strategies.aggressive.detectors.liquidity_vacuum import LiquidityVacuum

__all__ = [
    "BaseDetector",
    "DetectorResult",
    "MomentumBurst",
    "VWAPMagnet",
    "RibbonRide",
    "CompressionBreak",
    "VelocitySpike",
    "PullbackQuality",
    "LiquidityVacuum",
]
