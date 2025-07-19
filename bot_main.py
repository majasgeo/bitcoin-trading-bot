"""
🤖 Bitcoin Trading Bot - Main Controller
Orchestrates all components for real-time Bitcoin trading signal detection
Based on 96.6% win rate analysis of Bollinger Bands + Wick Touch patterns
"""

import sqlite3
import json
import time
import signal
import sys
import requests
from datetime import datetime
from pathlib import Path

# Import our custom modules
from binance_stream import BinanceWebSocket
from bb_engine import BollingerBandsEngine
from wick_detector import WickDetector
from signal_engine import SignalEngine


class BitcoinTradingBot:
    """Main Bitcoin Trading Bot Controller"""
    
    def __init__(self):
        # Initialize components
        self.binance_ws = BinanceWebSocket()
        self.bb_engine = BollingerBandsEngine()
        self.wick_detector = WickDetector()
        self.signal_engine = SignalEngine()
        
        # Configuration
        self.config = {
            'symbol': 'BTCUSDT',
            'timeframes': ['5m', '15m'],
            'log_file': 'bitcoin_bot.log',
            'db_file': 'bitcoin_bot.db',
            'signals_dir': 'signals',
            'discord_webhook_url': None,  # Set this for Discord alerts
            'paper_trading': True,
            'status_interval': 300,  # 5 minutes
        }
        
        # Runtime tracking
        self.start_time = time.time()
        self.running = True
        self.stats = {
            'signals_generated': 0,
            'candles_processed': 0,
            'uptime_hours': 0.0,
            'last_price': 0.0
        }
        
        # Setup
        self._setup_logging()
        self._setup_database()
        self._setup_directories()
        self._setup_signal_handlers()
        
    def _setup_logging(self):
        """Setup logging system"""
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config['log_file']),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def _setup_database(self):
        """Initialize SQLite database for signal storage"""
        try:
            self.db_conn = sqlite3.connect(self.config['db_file'])
            cursor = self.db_conn.cursor()
            
            # Create signals table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    signal_id TEXT UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    config_name TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    confidence REAL NOT NULL,
                    expected_profit REAL NOT NULL,
                    band_type TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create candles table for data tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS candles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    volume REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create bot_stats table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    signals_count INTEGER NOT NULL,
                    candles_count INTEGER NOT NULL,
                    current_price REAL NOT NULL,
                    uptime_hours REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.db_conn.commit()
            self.logger.info("✅ Database initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Database setup failed: {e}")
            sys.exit(1)
    
    def _setup_directories(self):
        """Create necessary directories"""
        Path(self.config['signals_dir']).mkdir(exist_ok=True)
        
    def _setup_signal_handlers(self):
        """Setup graceful shutdown handlers"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"🛑 Received shutdown signal {signum}")
        self.shutdown()
    
    def start(self):
        """Start the Bitcoin Trading Bot"""
        self.logger.info("🚀 Bitcoin Trading Bot starting...")
        self.logger.info("📊 Strategy: Bollinger Bands + Wick Touch Detection")
        self.logger.info("🎯 Target: 96.6% Win Rate Historical Analysis")
        self.logger.info("=" * 60)
        
        try:
            # Setup WebSocket callbacks
            self.binance_ws.set_callback(self._process_candle_data)
            
            # Start WebSocket connection
            self.logger.info("📡 Connecting to Binance WebSocket...")
            self.binance_ws.start()
            
            self.logger.info("✅ Bot started successfully")
            self.logger.info("🎯 Monitoring for Bollinger Band wick touches...")
            
            # Main monitoring loop
            last_status_time = time.time()
            
            while self.running:
                current_time = time.time()
                
                # Periodic status update
                if current_time - last_status_time >= self.config['status_interval']:
                    self._print_status()
                    self._save_stats()
                    last_status_time = current_time
                
                time.sleep(1)  # Small sleep to prevent high CPU usage
                
        except Exception as e:
            self.logger.error(f"❌ Bot error: {e}")
        finally:
            self.shutdown()
    
    def _process_candle_data(self, candle_data):
        """Process incoming candle data for signal detection"""
        try:
            symbol = candle_data['symbol']
            timeframe = candle_data['timeframe']
            
            # Update stats
            self.stats['candles_processed'] += 1
            self.stats['last_price'] = candle_data['close']
            
            # Log candle to database
            self._log_candle(candle_data)
            
            # Get historical data for analysis
            historical_data = self.binance_ws.get_data(symbol, timeframe)
            if len(historical_data) < 50:  # Need sufficient data for BB calculation
                return
            
            # Process each target configuration
            for config_name, config in self.signal_engine.target_configs.items():
                self._analyze_configuration(
                    historical_data, 
                    config, 
                    config_name, 
                    candle_data
                )
                
        except Exception as e:
            self.logger.error(f"❌ Error processing candle data: {e}")
    
    def _analyze_configuration(self, data, config, config_name, latest_candle):
        """Analyze single configuration for signal generation"""
        try:
            # Calculate Bollinger Bands
            bb_result = self.bb_engine.calculate_bollinger_bands(
                data=data,
                ma_type=config['ma_type'],
                period=config['period'],
                std_dev=config['std_dev'],
                band_type=config['band_type']
            )
            
            if not bb_result:
                return
            
            # Detect wick touches
            wick_result = self.wick_detector.detect_wick_touches(
                data=data,
                bb_data=bb_result,
                tolerance=0.0001  # ±0.01% tolerance
            )
            
            if not wick_result or not wick_result.get('touches'):
                return
            
            # Get the most recent touch
            latest_touch = wick_result['touches'][-1]
            
            # Generate signal if conditions are met
            signal = self.signal_engine.generate_signal(
                wick_data=latest_touch,
                bb_data=bb_result,
                price_data={
                    'symbol': latest_candle['symbol'],
                    'close': latest_candle['close'],
                    'timeframe': latest_candle['timeframe']
                }
            )
            
            if signal:
                self._handle_new_signal(signal)
                
        except Exception as e:
            self.logger.error(f"❌ Error analyzing {config_name}: {e}")
    
    def _handle_new_signal(self, signal):
        """Handle new trading signal generation"""
        try:
            self.logger.info(f"🚨 NEW SIGNAL: {signal.signal_id}")
            
            # Update stats
            self.stats['signals_generated'] += 1
            
            # Save to database
            self._save_signal(signal)
            
            # Save to JSON file
            self._save_signal_json(signal)
            
            # Send Discord alert if configured
            if self.config['discord_webhook_url']:
                self._send_discord_alert(signal)
            
            # Print signal details
            self._print_signal(signal)
            
        except Exception as e:
            self.logger.error(f"❌ Error handling signal: {e}")
    
    def _save_signal(self, signal):
        """Save signal to SQLite database"""
        try:
            cursor = self.db_conn.cursor()
            cursor.execute('''
                INSERT INTO signals (
                    timestamp, signal_id, symbol, config_name, direction,
                    entry_price, stop_loss, take_profit, confidence,
                    expected_profit, band_type, timeframe
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal.timestamp, signal.signal_id, signal.symbol,
                signal.config_name, signal.direction, signal.entry_price,
                signal.stop_loss, signal.take_profit, signal.confidence,
                signal.expected_profit, signal.band_type, signal.timeframe
            ))
            self.db_conn.commit()
            
        except Exception as e:
            self.logger.error(f"❌ Error saving signal to DB: {e}")
    
    def _save_signal_json(self, signal):
        """Save signal to JSON file"""
        try:
            filename = f"{self.config['signals_dir']}/{signal.signal_id}.json"
            with open(filename, 'w') as f:
                f.write(self.signal_engine.format_signal_json(signal))
                
        except Exception as e:
            self.logger.error(f"❌ Error saving signal JSON: {e}")
    
    def _send_discord_alert(self, signal):
        """Send Discord webhook alert"""
        try:
            message = self.signal_engine.format_signal_discord(signal)
            payload = {"content": message}
            
            response = requests.post(
                self.config['discord_webhook_url'],
                json=payload,
                timeout=10
            )
            
            if response.status_code == 204:
                self.logger.info("✅ Discord alert sent successfully")
            else:
                self.logger.warning(f"⚠️ Discord alert failed: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"❌ Discord alert error: {e}")
    
    def _log_candle(self, candle):
        """Log candle data to database"""
        try:
            cursor = self.db_conn.cursor()
            cursor.execute('''
                INSERT INTO candles (
                    timestamp, symbol, timeframe, open_price,
                    high_price, low_price, close_price, volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                candle['timestamp'], candle['symbol'], candle['timeframe'],
                candle['open'], candle['high'], candle['low'],
                candle['close'], candle['volume']
            ))
            self.db_conn.commit()
            
        except Exception as e:
            # Don't log every candle error to avoid spam
            pass
    
    def _save_stats(self):
        """Save current statistics to database"""
        try:
            self.stats['uptime_hours'] = (time.time() - self.start_time) / 3600
            
            cursor = self.db_conn.cursor()
            cursor.execute('''
                INSERT INTO bot_stats (
                    timestamp, signals_count, candles_count,
                    current_price, uptime_hours
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                self.stats['signals_generated'],
                self.stats['candles_processed'],
                self.stats['last_price'],
                self.stats['uptime_hours']
            ))
            self.db_conn.commit()
            
        except Exception as e:
            self.logger.error(f"❌ Error saving stats: {e}")
    
    def _print_signal(self, signal):
        """Print signal in formatted way"""
        direction_emoji = "🟢" if signal.direction == "LONG" else "🔴"
        
        print(f"""
🚨 NEW TRADING SIGNAL: {signal.signal_id}
   {direction_emoji} {signal.direction} {signal.symbol} @ ${signal.entry_price:,.2f}
   SL: ${signal.stop_loss:,.2f} | TP: ${signal.take_profit:,.2f}
   Confidence: {signal.confidence:.0%} | Expected: {signal.expected_profit:.1f}%
""")
    
    def _print_status(self):
        """Print current bot status"""
        uptime_hours = (time.time() - self.start_time) / 3600
        
        # Get signal stats
        signal_stats = self.signal_engine.get_signal_stats()
        
        print(f"""
============================================================
🤖 BITCOIN TRADING BOT STATUS
============================================================
📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
⏱️ Uptime: {uptime_hours:.1f}h
💰 Current BTC Price: ${self.stats['last_price']:,.2f}
🔗 Connection: {"✅ Connected" if self.binance_ws.connected else "❌ Disconnected"}

📊 DATA STATUS:
   5m: {len(self.binance_ws.get_data('BTCUSDT', '5m'))} candles
   15m: {len(self.binance_ws.get_data('BTCUSDT', '15m'))} candles

🚨 SIGNAL STATISTICS:
   Total Generated: {signal_stats['total_generated']}
   By Direction: {signal_stats['by_direction']}
   Active Signals: {signal_stats['active_signals']}
""")
    
    def shutdown(self):
        """Graceful shutdown of the bot"""
        self.logger.info("🛑 Shutting down Bitcoin Trading Bot...")
        self.running = False
        
        try:
            # Stop WebSocket
            if hasattr(self, 'binance_ws'):
                self.binance_ws.stop()
            
            # Close database connection
            if hasattr(self, 'db_conn'):
                self.db_conn.close()
            
            # Final statistics
            uptime_hours = (time.time() - self.start_time) / 3600
            
            print(f"""
============================================================
🏁 FINAL SESSION SUMMARY
============================================================
⏱️ Total Uptime: {uptime_hours:.1f} hours
📊 Candles Processed: {self.stats['candles_processed']:,}
🚨 Signals Generated: {self.stats['signals_generated']}
💾 Database: {self.config['db_file']}
📁 Signal Files: {self.config['signals_dir']}/

🎯 THE BITCOIN TRADING BOT SESSION COMPLETE!
============================================================
""")
            
        except Exception as e:
            self.logger.error(f"❌ Shutdown error: {e}")
        
        self.logger.info("✅ Bitcoin Trading Bot shutdown complete")


def main():
    """Main entry point"""
    print("""
🤖 Bitcoin Trading Bot - Bollinger Bands Strategy
Based on 96.6% Win Rate Historical Analysis
============================================================
""")
    
    try:
        # Create and start bot
        bot = BitcoinTradingBot()
        bot.start()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
