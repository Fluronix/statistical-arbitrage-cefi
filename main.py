import ccxt.async_support as ccxt 
from pprint import pprint as pp
import asyncio, json
from utils.module import MODULE
import pandas as pd
from utils.func import *
from pprint import pprint
from colorama import Back, Fore, Style
import colorama
colorama.init(autoreset=True)
# from utils.exchanges import bybit

exchange_class = getattr(ccxt, "bybit")
exchange:ccxt.bybit = exchange_class({
    'apiKey': BYBIT_API_KEY,
    'secret': BYBIT_API_SECRET
})

module = MODULE(exchange=exchange, user="fluronix.com")


async def cleanup(exchange):
    await exchange.close()
    


    
async def main():
    print(Fore.YELLOW+"WARNING: This is a prototype bot for experimental purposes. There is no guarantee of profit!")
    #NOTE These methods should be call once only when you want to structure cointegrated pairs--------------------------------------
    derivative_symbols = await module.get_derivative_symbols() # {symbol: [size_limit, precision, contractSize, maxLeverage]}

    print("geting df_market_close_prices...")
    df_market_close_prices = await module.get_df_market_close_prices(list(derivative_symbols.keys()))
    print("scanning for cointegration...")
    module.scan_for_cointegration(df_market_close_prices, derivative_symbols, max_half_life=18.5)
    # --------------------------------------------------------------------------------------------------------------------------
    

    # Load cointegrated pairs
    cointegrated_pairs_df = pd.read_csv("cointegrated_pairs.csv")
    
    while True:
        try:
            # Create tasks for each chunk
            tasks = []        
            for cointegrated_pairs_chunk in split_dataframe(cointegrated_pairs_df, 100):
                tasks.append(module.scan_for_trading_opportunities(cointegrated_pairs_chunk))

                
            # Run tasks concurrently
            await asyncio.gather(*tasks)
            
            
        except KeyboardInterrupt:
            # Catch KeyboardInterrupt to handle Ctrl+C gracefully
            print("\nProcess interrupted by user (Ctrl+C). Exiting gracefully...")
            await exchange.close()
            exit()
        except Exception as e:
            # Catch any other exceptions
            print(e)
            sendtlm(f"An error occurred: {e}", YOUR_TELEGRAM_ID)
        # finally:
        #     await exchange.close()
        #     print("exchange closed...")
        
    
    



# Run the program
if __name__ == "__main__":
    asyncio.run(main())
    


