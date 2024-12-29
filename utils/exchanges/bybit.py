from utils.func import gen_order_id
from pprint import pprint
from utils.func import retry



async  def fetch_tickers(exchange, with_spot_ticker=True):
    derivative1 = await exchange.fetch_tickers(params={
        "category": "linear"
    })

    # sort only USDT perpertual contracts
    derivative = {}
    for symbol in derivative1.keys():
        if "USDT:USDT" in symbol:
            derivative[symbol] = derivative1[symbol]

    if with_spot_ticker:
        spot = await exchange.fetch_tickers(params={
            "category": "spot"
        })
        return [derivative, spot]
    else:
        return derivative


# Load the markets and return the derivative symbols only   
async def get_derivative_symbols(exchange) -> dict[list]:
    markets = await exchange.load_markets()
    derivative_symbols = {}
    for symbol, market in markets.items(): 
        if market['type'] == 'swap' and market['active'] and symbol.endswith('USDT:USDT') and not symbol.startswith('USD'):
            " min order amount, symbol precision, contractSize"
            size_limit =  market['limits']['amount']['min']
            max_leverage =  market['limits']['leverage']['max']
            precision = market['precision']['amount']
            contractSize = market['contractSize']
            derivative_symbols[symbol] = [size_limit, precision, contractSize, max_leverage]
    
    return derivative_symbols

@retry(retries=3, delay=1)
async def get_num_positions(exchange, count_only=False, symbols=None):
    position_dict = dict()
    # await exchange.load_markets()
    position = await exchange.fetch_positions(symbols=symbols, params = {
        "category": "linear"
    })

    for pos in position:
        symbol= pos['symbol']
        unrealizedPnl = pos['unrealizedPnl'] if pos['unrealizedPnl']  != None else  0
        curRealisedPnl = pos['info']['curRealisedPnl'] if pos['info']['curRealisedPnl'] != None else  0
        
        position_dict[symbol] = {
            'unrealizedPnl': unrealizedPnl,
            'realizedPnl': curRealisedPnl,
            'amount': pos['contracts'],
            'side': pos['side'], # long/short
            'leverage': pos['leverage'],
            'totalProfit': float(curRealisedPnl) + float(unrealizedPnl),

        } 
    
    return position_dict


# GET OPEN ORDER PROPERTIES
async def get_open_order(order_id, exchange):
    open_order = await exchange.fetch_open_order(order_id)
    return  {
                'price': open_order['average'],
                'amount': open_order['filled'],
            }

async def get_min_amount_precision(symbol, exchange):
    "return min order amount, symbol precision, contractSize"
    market =  exchange.market(symbol)
    size_limit =  market['limits']['amount']['min']
    precision = market['precision']['amount']
    contractSize = market['contractSize']
    return size_limit, precision, contractSize


async def get_total_wallet_bal(exchange, bal_type=""):
    balance = await exchange.fetch_balance({'type': 'swap'})
    if bal_type =="dict":
        return balance['USDT']
    else:
       return balance['USDT']["total"]

@retry(retries=3, delay=1)
async def set_leverage(leverage:int, symbol:str, exchange):
    await exchange.set_leverage(leverage, symbol, params={
        'category':'linear'
    })    

@retry(retries=3, delay=1)
async def open_position(symbol:str, side:str, amount_usd:float, current_price:float , min_amount_precission:list, leverage:float, exchange):
    """@params min_amount_precission = [size_limit, precision, contractSize]"""
    
    contract_size = min_amount_precission[2]
    contract_value_usd = current_price * contract_size
    size_in_contracts = round(amount_usd / contract_value_usd)
    
    try:# Make the API request to set the position mode
        params = {
            'category': 'linear',  # Specify the category (linear, inverse)
            'mode': 0,  # Position mode. 0: Merged Single. 3: Both Sides
            'symbol': symbol.replace("/","").replace(":USDT","")
        }
        
        response = await exchange.request('/v5/position/switch-mode', 
            api="private", 
            method="POST", 
            params=params
        )
        await set_leverage(leverage, symbol, exchange)
    except:
        None

    try: #set margin mode
        await exchange.set_margin_mode("cross", symbol, params= {
            'category': 'linear',
            # "buyLeverage": leverage,
            # 'sellLeverage': leverage 
            })  
    except:
        None

    order_properties = await exchange.create_order(symbol,
        "market",
        side=side,
        amount=size_in_contracts,
        # price = price,
        params = {
            "orderLinkId": gen_order_id(),
            "category": "linear",
            'positionIdx': 0 # 0: one-way mode 1: hedge-mode Buy side 2: hedge-mode Sell side
           
        }
    )
    return order_properties


@retry(retries=3, delay=1)
async def close_position(symbol:str,side:str, amount, exchange):
    side = 'sell' if side == 'buy' else 'buy'
    return await exchange.create_order(symbol, 'market', side, amount, params={
        "category": "linear",
        'reduceOnly':True,
        'positionIdx': 0 # 0: one-way mode 1: hedge-mode Buy side 2: hedge-mode Sell side
    })

def get_realized_pnl(position):
    return float(position['info']['curRealisedPnl'])