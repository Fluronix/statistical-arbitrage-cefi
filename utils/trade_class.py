from utils.exchanges import bybit
from datetime import datetime

class TRADE:

    def __init__(self, 
        exchange:any,
        user:str,
        
        base_symbol:str,
        base_side:str,
        base_size:float,
        base_price:float,
        base_contract_prop:list,
        
        quote_symbol:str,
        quote_side:str,
        quote_size:float,
        quote_price:float,
        quote_contract_prop:list,
        
        # z_score:float,
        # half_life:float,
        # hedge_ratio:float
    ):

        # Initialize class variables
        self.exchange = exchange
        self.user = user
        
        self.base_symbol = base_symbol
        self.base_side = base_side
        self.base_size = base_size
        self.base_price = base_price
        self.base_contract_prop = base_contract_prop #['size_limit', 'precision', 'contractSize', 'maxLeverage']
        
        self.quote_symbol = quote_symbol
        self.quote_side = quote_side
        self.quote_size = quote_size
        self.quote_price = quote_price
        self.quote_contract_prop = quote_contract_prop #[size_limit, precision, contractSize, 'maxLeverage']
        
        # self.z_score = z_score
        # self.half_life = half_life
        # self.hedge_ratio = hedge_ratio
        
        self.positions_status = {
            'status': '',
            'base_amount': 0, # size of the first position (in base currency)
            'base_price': 0,
            'base_order_id': '',
            
            'base_amount': 0, # size of the second position (in base currency)
            'quote_price': 0,
            'quote_order_id': '',
            
            'comment': '',
            'timestamp': ''
        }
        
    async def open_position(self):
        
        # incase any of the symbol leverage is lower than the other
        quote_max_leverage = self.quote_contract_prop[3]
        base_max_leverage = self.base_contract_prop[3]
        lower_leverage  = min(base_max_leverage, quote_max_leverage)
        
        # TODO state variable LEVERAGE
        leverage = 100
        if leverage > lower_leverage:
            leverage = lower_leverage
        
        if self.exchange.id == "bybit":
            try:
            #    open first positions
                first_position = await bybit.open_position(
                    symbol=self.base_symbol, 
                    side=self.base_side,
                    amount_usd=self.base_size,
                    current_price=self.base_price,
                    min_amount_precission=self.base_contract_prop,
                    leverage=leverage,
                    exchange=self.exchange
                )
                
                # get first positions properties
                self.positions_status['base_order_id'] = first_position['id']
                order_properties = await bybit.get_open_order(first_position['id'], self.exchange)
                self.positions_status['base_price'] = order_properties['price']
                self.positions_status['base_amount'] = order_properties['amount']

            except Exception as e:
                self.positions_status['status'] = 'error'
                self.positions_status['comment'] = str(e)
                return self.positions_status
            
            
            try:
                # open second position
                second_position = await bybit.open_position(
                    symbol=self.quote_symbol, 
                    side=self.quote_side,
                    amount_usd=self.quote_size,
                    current_price=self.quote_price,
                    min_amount_precission=self.quote_contract_prop,
                    leverage=leverage,
                    exchange=self.exchange
                )

                # get second position  properties
                self.positions_status['quote_order_id'] = second_position['id']
                order_properties = await bybit.get_open_order(second_position['id'], self.exchange)
                self.positions_status['quote_price'] = order_properties['price']
                self.positions_status['quote_amount'] = order_properties['amount']
                self.positions_status['timestamp'] = round(datetime.now().timestamp())
                self.positions_status['status'] = 'executed'
                self.positions_status['comment'] = 'Trade executed successfully'
                
            except Exception as e:
                self.positions_status['status'] = 'error'
                self.positions_status['comment'] = str(e)
                
                #close first position if second position fails
                await bybit.close_position(self.base_symbol, self.base_side, self.positions_status['base_amount'], self.exchange)
                return self.positions_status
                
            return self.positions_status


        


