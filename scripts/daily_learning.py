#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')

import logging
from runtime.learning_brain import LearningBrain
from adapters.broker.mt5_broker import MT5BrokerAdapter
from config.live import GATEWAY_URL, GATEWAY_TOKEN

logging.basicConfig(level=logging.INFO)

def run():
    broker = MT5BrokerAdapter(GATEWAY_URL, GATEWAY_TOKEN)
    brain = LearningBrain(broker)
    brain.run_daily_analysis()

if __name__ == "__main__":
    run()
