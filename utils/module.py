

from utils.func import SmartError
import pandas as pd
import numpy as np
from utils.func import * #calculate_cointegration, plot_spread, retry, calculate_zscore
import math, asyncio, json
from pprint import pprint
from utils.trade_class import TRADE
from utils.exchanges import bybit
from datetime import datetime


maxopenpos= 10

class MODULE:

    def __init__(self, exchange:any, user:str):
        #NOTE user is useless for now
        self.exchange = exchange
        self.user = user
    
    # Load the markets and return the derivative symbols only   
    async def get_derivative_symbols(self) -> dict[list]:

        if self.exchange.id == 'bybit':   
            return await bybit.get_derivative_symbols(self.exchange)
        else:
            raise SmartError(f"Exchange {self.exchange.name} not supported")
    
    async def get_num_positions(self, count_only=True, symbols=None):
        if self.exchange.id == 'bybit':
            return await bybit.get_num_positions(self.exchange, count_only=count_only, symbols=symbols)
        else:
            raise SmartError(f"Exchange {self.exchange.name} not supported")

    async def close_position(self, symbol:str,side:str, amount):
        if self.exchange.id == 'bybit':
            return await bybit.close_position(symbol, side, amount, self.exchange)
        else:
            raise SmartError(f"Exchange {self.exchange.name} not supported")
    
    @retry(retries=3, delay=1, exceptions=(Exception,))
    async def fetch_candles(self, symbol:str, timeframe:str="1h", limit:int=500):
        return  await self.exchange.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
        
        
    # STRUCTURING SYMBOL DATA-FRAME
    @retry(retries=3, delay=1, exceptions=(Exception,))
    async def get_df_market_close_prices(self, derivative_symbols:list):# -[timestamp, closePrice]
       
        # get the first derivative symbol price series to be able to merge on timestamp with the rest of the derivative symbols
        symbol_ohlcv = await self.fetch_candles(symbol=derivative_symbols[0]) # --> [timestamp, open, high, low, close, volume]
        # map timestamp and close coulums only
        symbol_ohlcv = list(map(lambda x: [x[0], x[4]], symbol_ohlcv))#[timestam, closePrice]
        df_market_close_prices = pd.DataFrame(symbol_ohlcv, columns=['timestamp', derivative_symbols[0]])


        # get the rest of the derivative symbol price series
        for i, symbol in enumerate(derivative_symbols[1:]):
            symbol_ohlcv = await self.fetch_candles(symbol=symbol) # --> [timestamp, open, high, low, close, volume]
            # map timestamp and closePrice coulums only
            symbol_ohlcv = list(map(lambda x: [x[0],  x[4]], symbol_ohlcv)) #[timestam, closePrice]
            
            df1 = pd.DataFrame(symbol_ohlcv, columns=['timestamp', symbol])
            df_market_close_prices = pd.merge(df_market_close_prices, df1, how="outer", on="timestamp")

        df_market_close_prices['timestamp'] = pd.to_datetime(df_market_close_prices['timestamp'], unit='ms')

        # Check and drop any columns with NaNs if available
        nans = df_market_close_prices.columns[df_market_close_prices.isna().any()].tolist()
        if len(nans) > 0: 
            print("Dropping columns: ", nans)
            df_market_close_prices.drop(columns=nans, inplace=True)
            
        # await self.exchange.close()
        return df_market_close_prices
    
    
    # STRUCTURING SYMBOLS TO FIND COINTEGRATED PAIRS
    def scan_for_cointegration(self, df_market_close_prices:pd.DataFrame, derivative_symbols:dict, max_half_life:float=18.5):
        '''@param df_market_close_prices = [timestamp, symbol1, symbol2, symbol3, ...]'''   
        cointegrated_pairs = []
        all_symbols_list = (df_market_close_prices.columns.to_list())[1:] 
        # Start with our base pair (series_1)
        for index, base_symbol in enumerate(all_symbols_list[:-1]):
            series_1:list = df_market_close_prices[base_symbol].values.astype(np.float64).tolist()
            
            # Get Quote Pair (series_2)
            for quote_symbol in all_symbols_list[index+1:]:
                series_2:list = df_market_close_prices[quote_symbol].values.astype(np.float64).tolist()
            #   break
                cointegration = calculate_cointegration(series_1, series_2)
                if cointegration is not None:
                    hedge_ratio,  spread, half_life = cointegration
                    
                    if half_life <= max_half_life and half_life > 0:
                        cointegrated_pairs.append(
                            {
                                'base_symbol': base_symbol,
                                'quote_symbol': quote_symbol,
                                'hedge_ratio': hedge_ratio,
                                'half_life': half_life,
                                'base_contract_prop': derivative_symbols[base_symbol], # [size_limit, precision, contractSize, maxLeverage]
                                'quote_contract_prop': derivative_symbols[quote_symbol], # [size_limit, precision, contractSize, maxLeverage]
                            }
                        )   
                    # plot_spread(spread,half_life, base_symbol, quote_symbol)
        if (len(cointegrated_pairs) > 0):
            cointegrated_pairs = pd.DataFrame(cointegrated_pairs)
            cointegrated_pairs.to_csv("cointegrated_pairs.csv")
            del cointegrated_pairs
            
            print("cointegrated pairs saved to cointegrated_pairs.csv")
        else:
            print("No cointegrated pairs found")    
        

    async def scan_for_trading_opportunities(self, cointegrated_pairs_df:pd.DataFrame):
        
        #fetch all positions
        positions_dict:dict = await self.get_num_positions() #symbol: {unrealizedPnl, realizedPnl, amount, side, leverage, totalProfit}
        active_position_symbols:list = list(positions_dict.keys())
        
        # Loop through each cointegrated pair
        for index, row in cointegrated_pairs_df.iterrows():
            base_symbol = row['base_symbol']
            quote_symbol = row['quote_symbol']
            hedge_ratio = row["hedge_ratio"]
            half_life = row["half_life"]
            base_contract_prop = json.loads(row["base_contract_prop"]) # [size_limit, precision, contractSize, maxLeverage]
            quote_contract_prop = json.loads(row["quote_contract_prop"]) # [size_limit, precision, contractSize, maxLeverage]
            
            
            # check to make sure the symbol not already have any open position     
            if base_symbol in active_position_symbols or quote_symbol in active_position_symbols:
                continue
                

            trade_history = json.loads(open_file("./utils/trade_history.json"))
            #check maximum position tolerance
            num_of_open_positions = len(trade_history)
            if num_of_open_positions >= maxopenpos:
                continue

        
        
            # get the latest close prices for the cointegrated pair
            try:
                latest_close_prices_df = await self.get_df_market_close_prices([base_symbol, quote_symbol])
            except Exception as e:
                # print(f"Error fetching latest close prices for {base_symbol} and {quote_symbol}: {e}")
                continue
            
            
            series_1 = latest_close_prices_df[base_symbol].values.astype(np.float64).tolist()
            series_2 = latest_close_prices_df[quote_symbol].values.astype(np.float64).tolist()
            # convert series to numpy array
            series_1 = np.array(series_1).astype(np.float64)
            series_2 = np.array(series_2).astype(np.float64)
            
            
            if (len(series_1) < 1 or len(series_1) != len(series_2)):
                continue
            

            # Calculate the Z-score
            spread = series_1 - (hedge_ratio * series_2)
            zscore_df = calculate_zscore(spread, window=21)
            
            # get the mean of the Z-scores (avarage higher and lower Z-scores)
            average_higer_z_score, average_lower_z_score = calculate_mean_zscore(zscore_df, z_score_threshold=2)
            
  
            
            # get the current 2 Z-scores 
            cur_zscore:float = zscore_df.values.astype(np.float64).tolist()[-1]
            prev_zscore:float = zscore_df.values.astype(np.float64).tolist()[-2]
            
            #TEMP
            # plt_title = f'{base_symbol.replace(":USDT", "")} - {quote_symbol.replace(":USDT", "")}'
            # ylable = f"Avarage: {average_higer_z_score},{average_lower_z_score}"
            # zscore_img_base64 = plot(zscore_df, plt_title, f"Z-Score on entry: {cur_zscore}", xlabel=ylable, color="blue")
            # show_image_b64(zscore_img_base64)
            # continue
            # TEMP
        
            '''
            @Note we are trading the base symbol (series_1). 
            Shorting the spread means we are selling the base symbol and buying the quote symbol.
            Longing the spread means we are buying the base symbol and selling the quote symbol.
            '''
            
            # Determine the position side for each of the pairs
            base_side = "buy" if cur_zscore < 0 else "sell"
            quote_side = "buy" if cur_zscore > 0 else "sell"
            
            
            # Do not execute any buy position if cur_zscore is not up to the average lower z-score 
            if base_side == "buy" and (math.isnan(average_lower_z_score) or cur_zscore > average_lower_z_score):
                continue
            # Do not execute any sell position if cur_zscore is not up to the average higer z-score 
            elif base_side == "sell" and (math.isnan(average_higer_z_score) or cur_zscore < average_higer_z_score):
                continue
            
            # Check if the z-score is reversing up on buy or down on sell
            zscore_is_reversing = (base_side == "buy" and cur_zscore > prev_zscore) or (base_side == "sell" and cur_zscore < prev_zscore )

            
            if not zscore_is_reversing:
                continue
            
            #execute the trade
            base_price = float(series_1[-1])
            quote_price = float(series_2[-1])
            
            base_size = 5
            quote_size = 5
            
            trade = TRADE(
                exchange=self.exchange, 
                user=self.user, 
                base_symbol=base_symbol, 
                base_side=base_side, 
                base_size=base_size, 
                base_price=base_price, 
                base_contract_prop=base_contract_prop, 
                
                quote_symbol=quote_symbol, 
                quote_side=quote_side, 
                quote_size=quote_size, 
                quote_price=quote_price, 
                quote_contract_prop=quote_contract_prop, 
                
                # z_score=cur_zscore, 
                # half_life=half_life, 
                # hedge_ratio=hedge_ratio
            )
            
            positions_status = await trade.open_position() 
            
            if positions_status['status'] == 'error':
                print(f"Position failed to open on {base_symbol} - {quote_symbol}. Error:.", positions_status['comment'])
                del trade
            else:
                positions_status['base_symbol'] = base_symbol
                positions_status['base_side'] = base_side
                positions_status['quote_symbol'] = quote_symbol
                positions_status['quote_side'] = quote_side
                positions_status['zscore'] = cur_zscore
                positions_status['half_life'] = half_life
                positions_status['hedge_ratio'] = hedge_ratio
                
                # add the plot of the spread and zscore to the positions_status        
                plt_title = f'{base_symbol.replace(":USDT", "")} - {quote_symbol.replace(":USDT", "")}'
                ylable = f"Avarage: {average_higer_z_score},{average_lower_z_score}"
                
                zscore_img_base64 = plot(zscore_df, plt_title, f"Z-Score on entry: {cur_zscore}", xlabel=ylable, color="blue")
                positions_status["zscore_img"] = zscore_img_base64
                
                spread_img_base64 = plot(spread, plt_title, f"Spread on entry: {spread[-1]}", xlabel="index", color="red")
                positions_status["spread_img"] = spread_img_base64
                del trade
                
                # save the position to position json
                trade_history = json.loads(open_file("./utils/trade_history.json"))
                trade_history.append(positions_status)
                save_file("./utils/trade_history.json", json.dumps(trade_history))
                
                # TODO send alert
                sendtlm(f'Position opened {base_side} {base_symbol} - {quote_symbol}', YOUR_TELEGRAM_ID)
      
                
    async def manage_all_positions(self, trade_history:list, manage_only:bool=True):
        #NOTE  if manage_only is false then return the position properties

        if len(trade_history)==0:
            return
        
        #fetch all positions
        positions_dict:dict = await self.get_num_positions() #symbol: {unrealizedPnl, realizedPnl, amount, side, leverage, totalProfit}
        active_position_symbols:list = list(positions_dict.keys())
        
        position_properties = [list] 

        # pprint(positions_dict)

        for position in trade_history[2:3]:
            base_amount = float(position["base_amount"])
            base_price = float(position["base_price"])
            base_symbol = position["base_symbol"]
            base_order_id = position["base_order_id"]
            base_side = position["base_side"]
            
            quote_amount = float(position["quote_amount"])
            quote_price = float(position["quote_price"])
            quote_symbol = position["quote_symbol"]
            quote_order_id = position["quote_order_id"]
            quote_side = position["quote_side"]
            
            timestamp = position["timestamp"]
            zscore_executed = position["zscore"]
            half_life = position["half_life"]
            hedge_ratio = position["hedge_ratio"]
            zscore_img = position["zscore_img"]
            spread_img = position["spread_img"]
            
            current_timestamp = round(datetime.now().timestamp())
            position_duration_seconds, position_duration =  [calculate_time_ago(timestamp, current_timestamp, unit=unit) for unit in ["seconds", ""]]

            
            '''
            In a senerio where the user have manually closed one of the positions, 
            then we should not manage the positions anymore but close the paired position
            '''
            # check if the position is still active
            base_pos_is_active = base_symbol in active_position_symbols
            quote_pos_is_active = quote_symbol in active_position_symbols
            
            both_pair_status = pair_status(base_pos_is_active, quote_pos_is_active)

    
            def delete_position(position: dict): 
                # @NOTE: fetch from db 
                try:
                    trade_hist = json.loads(open_file("./utils/trade_history.json"))
                    position_index = trade_hist.index(position)
                    del trade_hist[position_index]
                    save_file("./utils/trade_history.json", json.dumps(trade_hist))
                except Exception as e:
                    pass
            
            if both_pair_status == "both closed":
                """Delete the position from the trade history"""
                delete_position(position)
                continue
                
                
            elif both_pair_status == "base active" and position_duration_seconds >= 50:
                """Close the base position"""
                
                delete_position(position)
                try:
                    await self.close_position(base_symbol, base_side, base_amount)
                    delete_position(position)
                except:
                    None
                finally:
                    continue        

                
            elif both_pair_status == "quote active" and position_duration_seconds >= 50:
                 # @NOTE: fetch from db 
                """Close the quote position"""
                try:
                    await self.close_position(quote_symbol, quote_side, quote_amount)
                    delete_position(position)
                except:
                    None
                finally:
                    continue      

            
            # get position properties from positions_dict
            base_symbol_pos_prop = positions_dict[base_symbol]
            base_total_profit = base_symbol_pos_prop["totalProfit"]
            
            quote_symbol_pos_prop = positions_dict[quote_symbol]
            quote_total_profit = quote_symbol_pos_prop["totalProfit"]
            
            overall_total_profit = base_total_profit + quote_total_profit
            
            # print(base_symbol, quote_symbol, overall_total_profit)
            
            # get the latest close prices for the position pair
            try:
                latest_close_prices_df = await self.get_df_market_close_prices([base_symbol, quote_symbol])
            except Exception as e:
                print(f"Error fetching latest close prices for {base_symbol} and {quote_symbol}: {e}")
                continue
            
            series_1 = latest_close_prices_df[base_symbol].values.astype(np.float64).tolist()
            series_2 = latest_close_prices_df[quote_symbol].values.astype(np.float64).tolist()
            # convert series to numpy array
            series_1 = np.array(series_1).astype(np.float64)
            series_2 = np.array(series_2).astype(np.float64)
            
            # Calculate the Z-score
            spread = series_1 - (hedge_ratio * series_2)
            zscore_df = calculate_zscore(spread, window=21)
            cur_zscore:float = zscore_df.values.astype(np.float64).tolist()[-1]

            # show_image_b64(zscore_img)
            # show_image_b64(spread_img)
            
            # plot the current zscore and spread
            # plt_title = f'{base_symbol.replace(":USDT", "")} - {quote_symbol.replace(":USDT", "")}'
            # zscore_img_base64 = plot(zscore_df, plt_title, f"Current Z-Score: {cur_zscore}", xlabel='index', color="blue")
            # spread_img_base64 = plot(spread, plt_title, f"Current Spread: {spread[-1]}", xlabel="index", color="red")
            
            # show_image_b64(zscore_img_base64)
            # show_image_b64(spread_img_base64)
            # break
            
            # print(
            #         base_symbol,
            #         quote_symbol, 
            #         overall_total_profit,
            #         zscore_executed,
            #         cur_zscore
            #     )
            
            
            # return the position properties for telegram logging if not manage_only
            if not manage_only:
                position_properties.append({
                    'history': position,
                    'position_duration': position_duration,
                    'overall_total_profit': overall_total_profit,
                    # 'zscore_img_base64': zscore_img_base64,
                    # 'spread_img_base64':spread_img_base64
                    
                })
                continue
            
            # check for conditions to close the position
            z_score_cross_up = zscore_executed < 0  and  cur_zscore >= 0
            z_score_cross_down = zscore_executed > 0  and  cur_zscore <= 0
            
            if z_score_cross_up or z_score_cross_down:
                await self.close_position(base_symbol, base_side, base_amount)
                await self.close_position(quote_symbol, quote_side, quote_amount)
                delete_position(position)
                sendtlm(f"Position closed {base_symbol} - {quote_symbol} realized profit: {round(overall_total_profit, 2)} USDT. Duration: {position_duration}", YOUR_TELEGRAM_ID) # @NOTE: send alert
                continue
            
        return position_properties
            

            
      

            
            
