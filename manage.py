import ccxt.async_support as ccxt 
from pprint import pprint as pp
import asyncio, json
from utils.module import MODULE
import pandas as pd
from utils.func import *
from pprint import pprint

from utils.exchanges import bybit

exchange_class = getattr(ccxt, "bybit")
exchange:ccxt.bybit = exchange_class({
    'apiKey': BYBIT_API_KEY,
    'secret': BYBIT_API_SECRET
})

module = MODULE(exchange=exchange, user="Tom")

    
async def main():
    
    while True:
        try:
            trade_history = json.loads(open_file("./utils/trade_history.json"))
            positions = await module.manage_all_positions(trade_history, True)
            
        except KeyboardInterrupt:
            # Catch KeyboardInterrupt to handle Ctrl+C gracefully
            print("\nProcess interrupted by user (Ctrl+C). Exiting gracefully...")
            await exchange.close()
            # exit()
        except Exception as e:
            # Catch any other exceptions
            sendtlm(f"An error occurred: {e}", YOUR_TELEGRAM_ID)
        # finally:
        #     await exchange.close()
        #     print("exchange closed...")
    
    
    
# Run the program
if __name__ == "__main__":
    asyncio.run(main())


