#!/usr/bin/env python3
"""
bb_engine.py - Bollinger Bands Calculation Engine
Supports VWMA, WMA, SMA, EMA, SMMA with custom periods and standard deviations
Optimized for Bitcoin Trading Bot with exact configurations from analysis
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BollingerBandsEngine:
    """
    Advanced Bollinger Bands calculation engine supporting multiple MA types
    Configured for the proven Bitcoin trading configurations
    """
    
    def __init__(self):
        # Target configurations from analysis
        self.target_configs = [
            {'ma_type': 'VWMA', 'period': 12, 'stddev': 0.1, 'band_type': 'Middle'},
            {'ma_type': 'WMA', 'period': 43, 'stddev': 0.1, 'band_type': 'Middle'},
            {'ma_type': 'SMA', 'period': 9, 'stddev': 0.1, 'band_type': 'Middle'}
        ]
        
        logger.info(f"Initialized Bollinger Bands Engine with {len(self.target_configs)} target configurations")
    
    def calculate_sma(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Simple Moving Average"""
        return prices.rolling(window=period, min_periods=period).mean()
    
    def calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average"""
        return prices.ewm(span=period, adjust=False).mean()
    
    def calculate_wma(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Weighted Moving Average"""
        def wma_func(x):
            weights = np.arange(1, len(x) + 1)
            return np.average(x, weights=weights)
        
        return prices.rolling(window=period, min_periods=period).apply(wma_func, raw=True)
    
    def calculate_vwma(self, prices: pd.Series, volumes: pd.Series, period: int) -> pd.Series:
        """Calculate Volume Weighted Moving Average"""
        def vwma_func(price_vol_data):
            if len(price_vol_data) < period:
                return np.nan
            
            prices_window = price_vol_data['close'].iloc[-period:]
            volumes_window = price_vol_data['volume'].iloc[-period:]
            
            if volumes_window.sum() == 0:
                return prices_window.mean()
            
            return (prices_window * volumes_window).sum() / volumes_window.sum()
        
        # Combine prices and volumes
        combined = pd.DataFrame({'close': prices, 'volume': volumes})
        return combined.rolling(window=period, min_periods=period).apply(vwma_func, raw=False)
    
    def calculate_moving_average(self, df: pd.DataFrame, ma_type: str, period: int) -> pd.Series:
        """Calculate moving average based on type"""
        prices = df['close']
        
        if ma_type == 'SMA':
            return self.calculate_sma(prices, period)
        elif ma_type == 'EMA':
            return self.calculate_ema(prices, period)
        elif ma_type == 'WMA':
            return self.calculate_wma(prices, period)
        elif ma_type == 'VWMA':
            return self.calculate_vwma(prices, df['volume'], period)
        else:
            raise ValueError(f"Unsupported MA type: {ma_type}")
    
    def calculate_bollinger_bands(self, df: pd.DataFrame, ma_type: str, period: int, stddev_multiplier: float) -> Dict[str, pd.Series]:
        """Calculate Bollinger Bands for given configuration"""
        if len(df) < period:
            return {'Upper': pd.Series(dtype=float), 'Middle': pd.Series(dtype=float), 'Lower': pd.Series(dtype=float)}
        
        # Calculate moving average (middle band)
        middle_band = self.calculate_moving_average(df, ma_type, period)
        
        # Calculate standard deviation
        std_dev = df['close'].rolling(window=period, min_periods=period).std()
        
        # Calculate upper and lower bands
        upper_band = middle_band + (std_dev * stddev_multiplier)
        lower_band = middle_band - (std_dev * stddev_multiplier)
        
        return {'Upper': upper_band, 'Middle': middle_band, 'Lower': lower_band}
    
    def calculate_all_target_bands(self, df: pd.DataFrame) -> Dict[str, Dict[str, pd.Series]]:
        """Calculate Bollinger Bands for all target configurations"""
        all_bands = {}
        
        for config in self.target_configs:
            config_name = f"{config['ma_type']}_{config['period']}_{config['stddev']}"
            
            try:
                bands = self.calculate_bollinger_bands(
                    df=df, ma_type=config['ma_type'], period=config['period'], stddev_multiplier=config['stddev']
                )
                all_bands[config_name] = bands
            except Exception as e:
                logger.error(f"Error calculating {config_name}: {e}")
                all_bands[config_name] = {'Upper': pd.Series(dtype=float), 'Middle': pd.Series(dtype=float), 'Lower': pd.Series(dtype=float)}
        
        return all_bands