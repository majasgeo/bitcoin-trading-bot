#!/usr/bin/env python3
"""
wick_detector.py - Precise Wick Detection Engine
Detects exact wick touches on Bollinger Bands with ±0.01% tolerance
Optimized for Bitcoin Trading Bot based on historical analysis
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WickDetector:
    """Advanced wick detection engine for Bollinger Bands trading"""
    
    def __init__(self, tolerance: float = 0.0001):  # 0.01% default tolerance
        self.tolerance = tolerance
        self.detected_signals = []
        logger.info(f"Initialized WickDetector with {tolerance*100:.2f}% tolerance")
    
    def calculate_wick_characteristics(self, candle: Dict) -> Dict:
        """Calculate detailed wick characteristics for a candle"""
        open_price = candle['open']
        high_price = candle['high']
        low_price = candle['low']
        close_price = candle['close']
        
        # Determine candle direction
        is_bullish = close_price > open_price
        body_size = abs(close_price - open_price)
        total_range = high_price - low_price
        
        # Calculate wick sizes
        if is_bullish:
            upper_wick = high_price - close_price
            lower_wick = open_price - low_price
        else:
            upper_wick = high_price - open_price
            lower_wick = close_price - low_price
        
        # Calculate ratios
        body_to_range_ratio = body_size / total_range if total_range > 0 else 0
        upper_wick_ratio = upper_wick / total_range if total_range > 0 else 0
        lower_wick_ratio = lower_wick / total_range if total_range > 0 else 0
        
        return {
            'is_bullish': is_bullish,
            'body_size': body_size,
            'upper_wick': upper_wick,
            'lower_wick': lower_wick,
            'total_range': total_range,
            'body_to_range_ratio': body_to_range_ratio,
            'upper_wick_ratio': upper_wick_ratio,
            'lower_wick_ratio': lower_wick_ratio,
            'has_significant_upper_wick': upper_wick_ratio > 0.3,
            'has_significant_lower_wick': lower_wick_ratio > 0.3
        }
    
    def check_band_touch(self, price: float, band_value: float) -> Dict:
        """Check if price touches band within tolerance"""
        if band_value is None or band_value == 0:
            return {'is_touch': False, 'price_diff': None, 'percentage_diff': None, 'within_tolerance': False}
        
        price_diff = abs(price - band_value)
        percentage_diff = price_diff / band_value
        within_tolerance = percentage_diff <= self.tolerance
        
        return {
            'is_touch': within_tolerance,
            'price_diff': price_diff,
            'percentage_diff': percentage_diff,
            'within_tolerance': within_tolerance,
            'exact_match': price_diff < 0.01
        }
    
    def detect_wick_band_touches(self, candle: Dict, bands: Dict[str, float], config_name: str) -> List[Dict]:
        """Detect if candle wicks touch any of the Bollinger Bands"""
        touches = []
        
        # Get candle data
        high_price = candle['high']
        low_price = candle['low']
        timestamp = candle.get('timestamp', datetime.now())
        
        # Calculate wick characteristics
        wick_chars = self.calculate_wick_characteristics(candle)
        
        # Check upper wick against Upper and Middle bands
        for band_type in ['Upper', 'Middle']:
            if band_type in bands and bands[band_type] is not None:
                band_value = bands[band_type]
                touch_analysis = self.check_band_touch(high_price, band_value)
                
                if touch_analysis['is_touch']:
                    touch = {
                        'timestamp': timestamp,
                        'config_name': config_name,
                        'candle_data': candle,
                        'wick_characteristics': wick_chars,
                        'touch_type': 'upper_wick',
                        'band_type': band_type,
                        'band_value': band_value,
                        'touch_price': high_price,
                        'touch_analysis': touch_analysis,
                        'direction_signal': 'SHORT',
                        'confidence': self._calculate_touch_confidence(wick_chars, touch_analysis, 'upper')
                    }
                    touches.append(touch)
        
        # Check lower wick against Lower and Middle bands
        for band_type in ['Lower', 'Middle']:
            if band_type in bands and bands[band_type] is not None:
                band_value = bands[band_type]
                touch_analysis = self.check_band_touch(low_price, band_value)
                
                if touch_analysis['is_touch']:
                    touch = {
                        'timestamp': timestamp,
                        'config_name': config_name,
                        'candle_data': candle,
                        'wick_characteristics': wick_chars,
                        'touch_type': 'lower_wick',
                        'band_type': band_type,
                        'band_value': band_value,
                        'touch_price': low_price,
                        'touch_analysis': touch_analysis,
                        'direction_signal': 'LONG',
                        'confidence': self._calculate_touch_confidence(wick_chars, touch_analysis, 'lower')
                    }
                    touches.append(touch)
        
        return touches
    
    def _calculate_touch_confidence(self, wick_chars: Dict, touch_analysis: Dict, wick_type: str) -> float:
        """Calculate confidence score for wick touch (0.0 to 1.0)"""
        confidence = 0.5  # Base confidence
        
        # Bonus for exact matches
        if touch_analysis.get('exact_match', False):
            confidence += 0.3
        
        # Bonus for significant wicks
        if wick_type == 'upper' and wick_chars['has_significant_upper_wick']:
            confidence += 0.2
        elif wick_type == 'lower' and wick_chars['has_significant_lower_wick']:
            confidence += 0.2
        
        # Bonus for smaller body relative to wick
        body_ratio = wick_chars['body_to_range_ratio']
        if body_ratio < 0.3:
            confidence += 0.15
        elif body_ratio < 0.5:
            confidence += 0.1
        
        return min(max(confidence, 0.0), 1.0)
    
    def scan_dataframe_for_touches(self, df: pd.DataFrame, all_bands: Dict[str, Dict[str, pd.Series]], lookback_periods: int = 3) -> List[Dict]:
        """Scan recent candles in DataFrame for band touches"""
        all_touches = []
        
        if len(df) < lookback_periods:
            return all_touches
        
        # Scan last N candles
        for i in range(-lookback_periods, 0):
            try:
                # Get candle data
                candle_data = {
                    'timestamp': df.index[i],
                    'open': df.iloc[i]['open'],
                    'high': df.iloc[i]['high'],
                    'low': df.iloc[i]['low'],
                    'close': df.iloc[i]['close'],
                    'volume': df.iloc[i]['volume']
                }
                
                # Check against all band configurations
                for config_name, bands_series in all_bands.items():
                    # Get band values for this candle
                    current_bands = {}
                    for band_type, series in bands_series.items():
                        if not series.empty and len(series) > abs(i):
                            current_bands[band_type] = series.iloc[i]
                        else:
                            current_bands[band_type] = None
                    
                    # Detect touches for this configuration
                    touches = self.detect_wick_band_touches(candle_data, current_bands, config_name)
                    all_touches.extend(touches)
                    
            except Exception as e:
                logger.error(f"Error scanning candle at index {i}: {e}")
        
        return all_touches
    
    def filter_high_confidence_touches(self, touches: List[Dict], min_confidence: float = 0.7) -> List[Dict]:
        """Filter touches by minimum confidence score"""
        high_confidence = [touch for touch in touches if touch['confidence'] >= min_confidence]
        logger.info(f"Filtered {len(high_confidence)} high-confidence touches from {len(touches)} total")
        return high_confidence