"""
🚨 Trading Signal Generation Engine
Converts wick touches into actionable trading signals with risk management
"""

import json
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime, timedelta


@dataclass
class TradingSignal:
    """Complete trading signal with all required information"""
    timestamp: str
    signal_id: str
    symbol: str
    config_name: str
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    band_value: float
    stop_loss: float
    take_profit: float
    confidence: float
    expected_profit: float
    wick_touch_type: str
    band_type: str
    timeframe: str


class SignalEngine:
    """Generates trading signals from wick touch detections"""
    
    def __init__(self):
        # Target configurations based on 96.6% win rate analysis
        self.target_configs = {
            'VWMA_12_0.1': {
                'ma_type': 'VWMA',
                'period': 12,
                'std_dev': 0.1,
                'band_type': 'middle',
                'expected_profit': 28.51,
                'win_rate': 100.0,
                'priority': 1
            },
            'WMA_43_0.1': {
                'ma_type': 'WMA',
                'period': 43,
                'std_dev': 0.1,
                'band_type': 'middle',
                'expected_profit': 26.00,
                'win_rate': 100.0,
                'priority': 2
            },
            'SMA_9_0.1': {
                'ma_type': 'SMA',
                'period': 9,
                'std_dev': 0.1,
                'band_type': 'middle',
                'expected_profit': 24.80,
                'win_rate': 100.0,
                'priority': 3
            }
        }
        
        # Active signals tracking
        self.active_signals = {}
        self.signal_history = []
        self.last_signal_time = {}
        self.cooldown_period = 3600  # 1 hour cooldown between signals
        
        # Risk management parameters
        self.stop_loss_pct = 0.30  # 30% stop loss
        self.take_profit_pct = 0.20  # 20% take profit
        self.max_signal_duration = 15 * 24 * 3600  # 15 days
        
    def generate_signal(self, wick_data: Dict, bb_data: Dict, price_data: Dict) -> Optional[TradingSignal]:
        """Generate trading signal from wick touch detection"""
        try:
            # Extract key information
            config_name = f"{bb_data['ma_type']}_{bb_data['period']}_{bb_data['std_dev']}"
            current_price = price_data['close']
            timestamp = datetime.now().isoformat()
            
            # Check if this config is in our target list
            if config_name not in self.target_configs:
                return None
                
            # Check cooldown period
            if self._is_in_cooldown(config_name):
                return None
                
            # Determine signal direction based on wick touch
            direction = self._determine_direction(wick_data, bb_data)
            if not direction:
                return None
                
            # Calculate entry levels
            entry_price = current_price
            band_value = wick_data['band_value']
            
            # Calculate stop loss and take profit
            stop_loss, take_profit = self._calculate_risk_levels(
                entry_price, direction
            )
            
            # Calculate confidence score
            confidence = self._calculate_confidence(wick_data, bb_data)
            
            # Create signal ID
            signal_id = f"{config_name}_{direction}_{int(time.time())}"
            
            # Create trading signal
            signal = TradingSignal(
                timestamp=timestamp,
                signal_id=signal_id,
                symbol=price_data.get('symbol', 'BTCUSDT'),
                config_name=config_name,
                direction=direction,
                entry_price=entry_price,
                band_value=band_value,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                expected_profit=self.target_configs[config_name]['expected_profit'],
                wick_touch_type=wick_data['touch_type'],
                band_type=bb_data['band_type'],
                timeframe=price_data.get('timeframe', '5m')
            )
            
            # Store signal
            self._store_signal(signal)
            
            return signal
            
        except Exception as e:
            print(f"❌ Error generating signal: {e}")
            return None
    
    def _determine_direction(self, wick_data: Dict, bb_data: Dict) -> Optional[str]:
        """Determine LONG/SHORT direction based on wick touch analysis"""
        try:
            touch_type = wick_data['touch_type']
            band_type = bb_data['band_type']
            
            # Middle band strategy (our best performing)
            if band_type == 'middle':
                if touch_type == 'lower_wick_touch':
                    return 'LONG'  # Price bounced up from middle band
                elif touch_type == 'upper_wick_touch':
                    return 'SHORT'  # Price rejected from middle band
                    
            # Lower band strategy
            elif band_type == 'lower':
                if touch_type == 'lower_wick_touch':
                    return 'LONG'  # Bounce from lower band
                    
            # Upper band strategy
            elif band_type == 'upper':
                if touch_type == 'upper_wick_touch':
                    return 'SHORT'  # Rejection from upper band
                    
            return None
            
        except Exception as e:
            print(f"❌ Error determining direction: {e}")
            return None
    
    def _calculate_risk_levels(self, entry_price: float, direction: str) -> tuple:
        """Calculate stop loss and take profit levels"""
        if direction == 'LONG':
            stop_loss = entry_price * (1 - self.stop_loss_pct)
            take_profit = entry_price * (1 + self.take_profit_pct)
        else:  # SHORT
            stop_loss = entry_price * (1 + self.stop_loss_pct)
            take_profit = entry_price * (1 - self.take_profit_pct)
            
        return stop_loss, take_profit
    
    def _calculate_confidence(self, wick_data: Dict, bb_data: Dict) -> float:
        """Calculate confidence score for the signal"""
        try:
            base_confidence = wick_data.get('confidence', 0.5)
            
            # Boost confidence for target configurations
            config_name = f"{bb_data['ma_type']}_{bb_data['period']}_{bb_data['std_dev']}"
            if config_name in self.target_configs:
                priority_boost = (4 - self.target_configs[config_name]['priority']) * 0.1
                base_confidence += priority_boost
                
            # Boost for middle band (best performer)
            if bb_data['band_type'] == 'middle':
                base_confidence += 0.15
                
            # Boost for exact touches
            if wick_data.get('exact_touch', False):
                base_confidence += 0.1
                
            return min(base_confidence, 1.0)
            
        except Exception:
            return 0.5
    
    def _is_in_cooldown(self, config_name: str) -> bool:
        """Check if configuration is in cooldown period"""
        if config_name not in self.last_signal_time:
            return False
            
        time_since_last = time.time() - self.last_signal_time[config_name]
        return time_since_last < self.cooldown_period
    
    def _store_signal(self, signal: TradingSignal):
        """Store signal in memory and update tracking"""
        # Add to active signals
        self.active_signals[signal.signal_id] = signal
        
        # Add to history
        self.signal_history.append(signal)
        
        # Update last signal time
        self.last_signal_time[signal.config_name] = time.time()
        
        # Clean up old signals
        self._cleanup_old_signals()
    
    def _cleanup_old_signals(self):
        """Remove old signals that exceed max duration"""
        current_time = time.time()
        signals_to_remove = []
        
        for signal_id, signal in self.active_signals.items():
            signal_time = datetime.fromisoformat(signal.timestamp).timestamp()
            if current_time - signal_time > self.max_signal_duration:
                signals_to_remove.append(signal_id)
                
        for signal_id in signals_to_remove:
            del self.active_signals[signal_id]
    
    def format_signal_json(self, signal: TradingSignal) -> str:
        """Format signal as JSON for webhooks/APIs"""
        return json.dumps(asdict(signal), indent=2)
    
    def format_signal_discord(self, signal: TradingSignal) -> str:
        """Format signal for Discord notifications"""
        direction_emoji = "🟢" if signal.direction == "LONG" else "🔴"
        
        message = f"""
🚨 **NEW TRADING SIGNAL: {signal.signal_id}**

{direction_emoji} **{signal.direction} {signal.symbol}** @ **${signal.entry_price:,.2f}**

📊 **Strategy:** {signal.config_name}
🎯 **Band Touch:** {signal.wick_touch_type} on {signal.band_type} band
⚡ **Band Value:** ${signal.band_value:,.2f}

🛡️ **Risk Management:**
🔻 **Stop Loss:** ${signal.stop_loss:,.2f} ({((signal.stop_loss/signal.entry_price-1)*100):+.1f}%)
🎯 **Take Profit:** ${signal.take_profit:,.2f} ({((signal.take_profit/signal.entry_price-1)*100):+.1f}%)

📈 **Performance Expectations:**
💡 **Confidence:** {signal.confidence:.0%}
💰 **Expected Profit:** {signal.expected_profit:.1f}%
⏰ **Timeframe:** {signal.timeframe}

🕐 **Generated:** {signal.timestamp[:19].replace('T', ' ')}
"""
        return message
    
    def get_active_signals(self) -> List[TradingSignal]:
        """Get all currently active signals"""
        return list(self.active_signals.values())
    
    def get_signal_stats(self) -> Dict:
        """Get signal generation statistics"""
        total_signals = len(self.signal_history)
        active_count = len(self.active_signals)
        
        # Count by direction
        direction_counts = {'LONG': 0, 'SHORT': 0}
        for signal in self.signal_history:
            direction_counts[signal.direction] += 1
        
        # Count by config
        config_counts = {}
        for signal in self.signal_history:
            config_counts[signal.config_name] = config_counts.get(signal.config_name, 0) + 1
        
        return {
            'total_generated': total_signals,
            'active_signals': active_count,
            'by_direction': direction_counts,
            'by_config': config_counts,
            'cooldown_status': {
                config: (time.time() - last_time) < self.cooldown_period
                for config, last_time in self.last_signal_time.items()
            }
        }


if __name__ == "__main__":
    # Test signal engine
    engine = SignalEngine()
    
    # Sample wick data
    sample_wick = {
        'confidence': 0.85,
        'touch_type': 'lower_wick_touch',
        'band_value': 42148.30,
        'exact_touch': True
    }
    
    # Sample BB data
    sample_bb = {
        'ma_type': 'VWMA',
        'period': 12,
        'std_dev': 0.1,
        'band_type': 'middle'
    }
    
    # Sample price data
    sample_price = {
        'symbol': 'BTCUSDT',
        'close': 42150.50,
        'timeframe': '5m'
    }
    
    # Generate test signal
    signal = engine.generate_signal(sample_wick, sample_bb, sample_price)
    
    if signal:
        print("🚨 Test Signal Generated:")
        print(engine.format_signal_discord(signal))
        print("\n📄 JSON Format:")
        print(engine.format_signal_json(signal))
    else:
        print("❌ No signal generated")
