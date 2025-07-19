#!/usr/bin/env python3
"""
binance_stream.py - Real-time WebSocket Data Stream for Bitcoin Trading Bot
Provides live OHLCV data for BTCUSDT across multiple timeframes
"""

import websocket
import json
import threading
import time
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BinanceDataStream:
    """
    Real-time Binance WebSocket data stream for BTCUSDT
    Supports multiple timeframes with automatic OHLCV aggregation
    """
    
    def __init__(self, symbol='BTCUSDT', timeframes=['1m', '5m', '15m']):
        self.symbol = symbol.lower()
        self.timeframes = timeframes
        self.ws = None
        self.is_running = False
        
        # Data storage - stores last 200 candles per timeframe
        self.data = {tf: deque(maxlen=200) for tf in timeframes}
        self.current_candles = {tf: None for tf in timeframes}
        
        # Callbacks for new candle data
        self.callbacks = []
        
        # WebSocket URL
        streams = [f"{self.symbol}@kline_{tf}" for tf in timeframes]
        self.ws_url = f"wss://stream.binance.com:9443/ws/{'/'.join(streams)}"
        
        logger.info(f"Initialized BinanceDataStream for {symbol} on timeframes: {timeframes}")
    
    def add_callback(self, callback_func):
        """Add callback function to be called on new candle data"""
        self.callbacks.append(callback_func)
        logger.info(f"Added callback: {callback_func.__name__}")
    
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            
            # Handle stream data
            if 'stream' in data:
                stream = data['stream']
                kline_data = data['data']['k']
                
                # Extract timeframe from stream name
                timeframe = stream.split('@kline_')[1]
                
                # Process kline data
                candle = {
                    'timestamp': pd.to_datetime(kline_data['t'], unit='ms'),
                    'open': float(kline_data['o']),
                    'high': float(kline_data['h']),
                    'low': float(kline_data['l']),
                    'close': float(kline_data['c']),
                    'volume': float(kline_data['v']),
                    'is_closed': kline_data['x']  # True if this kline is closed
                }
                
                # Store current candle
                self.current_candles[timeframe] = candle
                
                # If candle is closed, add to historical data
                if candle['is_closed']:
                    self.data[timeframe].append(candle)
                    logger.debug(f"New {timeframe} candle closed: {candle['timestamp']} - Close: ${candle['close']:.2f}")
                    
                    # Trigger callbacks for closed candles
                    for callback in self.callbacks:
                        try:
                            callback(timeframe, candle, self.get_dataframe(timeframe))
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
        
        # Auto-reconnect if we were running
        if self.is_running:
            logger.info("Attempting to reconnect in 5 seconds...")
            time.sleep(5)
            self.start()
    
    def on_open(self, ws):
        """Handle WebSocket open"""
        logger.info("WebSocket connection established")
        self.is_running = True
    
    def start(self):
        """Start the WebSocket connection"""
        logger.info(f"Starting WebSocket stream: {self.ws_url}")
        
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        # Start in separate thread
        def run_ws():
            self.ws.run_forever()
        
        ws_thread = threading.Thread(target=run_ws, daemon=True)
        ws_thread.start()
        
        # Load initial historical data
        self._load_initial_data()
        
        return ws_thread
    
    def stop(self):
        """Stop the WebSocket connection"""
        logger.info("Stopping WebSocket stream...")
        self.is_running = False
        if self.ws:
            self.ws.close()
    
    def _load_initial_data(self):
        """Load initial historical data for all timeframes"""
        import requests
        
        for timeframe in self.timeframes:
            try:
                # Get historical klines from Binance REST API
                url = "https://api.binance.com/api/v3/klines"
                params = {
                    'symbol': self.symbol.upper(),
                    'interval': timeframe,
                    'limit': 200  # Get last 200 candles
                }
                
                response = requests.get(url, params=params)
                response.raise_for_status()
                
                klines = response.json()
                
                # Convert to our format
                for kline in klines[:-1]:  # Exclude current incomplete candle
                    candle = {
                        'timestamp': pd.to_datetime(kline[0], unit='ms'),
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5]),
                        'is_closed': True
                    }
                    self.data[timeframe].append(candle)
                
                logger.info(f"Loaded {len(self.data[timeframe])} historical candles for {timeframe}")
                
            except Exception as e:
                logger.error(f"Failed to load historical data for {timeframe}: {e}")
    
    def get_dataframe(self, timeframe):
        """Get DataFrame for specific timeframe"""
        if timeframe not in self.data:
            return pd.DataFrame()
        
        candles = list(self.data[timeframe])
        if not candles:
            return pd.DataFrame()
        
        df = pd.DataFrame(candles)
        df.set_index('timestamp', inplace=True)
        df = df[['open', 'high', 'low', 'close', 'volume']]  # Remove is_closed
        
        return df
    
    def get_current_price(self):
        """Get current Bitcoin price"""
        # Try to get from 1m timeframe first
        for tf in ['1m', '5m', '15m']:
            if tf in self.current_candles and self.current_candles[tf]:
                return self.current_candles[tf]['close']
        return None
    
    def get_latest_candle(self, timeframe):
        """Get the latest closed candle for timeframe"""
        if timeframe not in self.data or not self.data[timeframe]:
            return None
        return self.data[timeframe][-1]
    
    def is_connected(self):
        """Check if WebSocket is connected and receiving data"""
        return self.is_running and self.ws is not None
    
    def get_data_status(self):
        """Get status of data for all timeframes"""
        status = {}
        for tf in self.timeframes:
            candles_count = len(self.data[tf])
            latest_time = None
            if candles_count > 0:
                latest_time = self.data[tf][-1]['timestamp']
            
            status[tf] = {
                'candles_count': candles_count,
                'latest_candle': latest_time,
                'current_price': self.get_current_price()
            }
        
        return status