import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint
from scipy.stats import linregress

import matplotlib.pyplot as plt
import pandas as pd
import functools,io,base64
import time,random
from PIL import Image
import requests, uuid

TELEGRAM_BOT_API:str = "" #paste your telegram bot token
YOUR_TELEGRAM_ID:int = 0 #paste your numeric telegram id

BYBIT_API_KEY:str = "" #paste your API key
BYBIT_API_SECRET:str = "" #paste your API secret key



def x_percent_of_y(x, y):
   return  (x / 100) * y

def percent_of_x_in_y(x, y):
    return (x / y) * 100

def open_file(fpath):
    with open(fpath, encoding="utf8") as f:
        file = f.read()
    return file

def save_file(path, file):
    with open(path, "w") as fp:
        fp.write(file)
        return True


def calculate_time_ago(timestamp1: float, timestamp2: float, unit:str='') -> str|float:
    # Calculate the absolute difference in seconds (float)
    seconds_diff = abs(timestamp2 - timestamp1)
    # Convert seconds to minutes, hours, and days
    minutes_diff = round(seconds_diff / 60, 2)
    hours_diff = round(minutes_diff / 60, 2)
    days_diff = round(hours_diff / 24, 2)
    
    match unit:
        case 'seconds':
            return seconds_diff
        case 'minutes':
            return minutes_diff
        case 'hours':
            return hours_diff
        case 'days':
            return days_diff
        case '':
            if days_diff >= 1:
                return f"{days_diff} days ago"
            elif hours_diff >= 1:
                return f"{hours_diff} hours ago"
            elif minutes_diff >= 1:
                return f"{minutes_diff} minutes ago"
            else:
                return f"{seconds_diff} seconds ago"
            
def pair_status(base:bool, quote:bool):
    if base and quote:
        return "both active"
    elif base:
        return "base active"
    elif quote:
        return "quote active"
    else:
        return "both closed"

def gen_order_id():
    lower_char = 'abcdefghijklmnopqrstuvwxyz'
    uppper_char = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    number = '0123456789'
    allalpha = lower_char + uppper_char + number
    unique_id = ''.join(random.sample(allalpha,6))
    return f"FluronixDumperbot-{unique_id}"

def retry(retries=3, delay=1, exceptions=(Exception,)):
    """
    Decorator that retries running a function up to `retries` times with a `delay` between retries
    if the function raises an exception listed in `exceptions`.
    
    :param retries: Number of times to retry the function.
    :param delay: Delay (in seconds) between retries.
    :param exceptions: Tuple of exceptions to catch and retry upon.
    """
    def decorator_retry(func):
        @functools.wraps(func)
        def wrapper_retry(*args, **kwargs):
            attempt = 0
            while attempt < retries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= retries:
                        raise  # Raise the last exception if all retries failed
                    print(f"Attempt {attempt} failed for function '{func.__name__}': {e}. Retrying in {delay} seconds...")
                    time.sleep(delay)
        return wrapper_retry
    return decorator_retry

def sendtlm(message, telegram_id, pass_mode=True):
    # for teleid in telegram_ids:
    if pass_mode:
         return requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_API}/sendmessage?chat_id={telegram_id}&text={message}&parse_mode=Markdown")
    else:
         return requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_API}/sendmessage?chat_id={telegram_id}&text={message}")

# Function to split the DataFrame into chunks
def split_dataframe(df, chunk_size):
    for i in range(0, len(df), chunk_size):
        yield df[i:i + chunk_size]

class SmartError(Exception):
  pass
# Calculate halflife for mean reversion
def half_life_mean_reversion(series):
  if len(series) <= 1:
    raise SmartError("Series length must be greater than 1.")
  difference  = np.diff(series)
  
  lagged_series = series[:-1]
  slope, _, _, _, _ = linregress(lagged_series, difference)
  if np.abs(slope) < np.finfo(np.float64).eps:
    raise SmartError("Cannot calculate half life. Slope value is too close to zero.")
  half_life = -np.log(2) / slope
  return half_life


# Function to calculate cointegration
def calculate_cointegration(series_1:list, series_2:list):
    series_1 = np.array(series_1).astype(np.float64)
    series_2 = np.array(series_2).astype(np.float64)

    
    # Perform cointegration test
    """
    @dev: coint() function expects the series to be in numpy array format.
    @note: coint_t should be less than crit_value to be considered cointegrated (level 5 mostly used).
    @note: p_value should be less than 0.05 to be considered cointegrated.
    @note: crit_value is the critical value at 1%, 5%, and 10% significance levels.   
    """
    coint_t, p_value, crit_value = coint(series_1, series_2)
    is_cointegrated = coint_t < crit_value[1] and p_value < 0.05
    if not is_cointegrated:
        return None
    
    # Calculate hedge ratio
    series_2_with_constant = sm.add_constant(series_2) 
    model = sm.OLS(series_1, series_2_with_constant)
    results = model.fit() #[intercept, slope]
    hedge_ratio = results.params[1] #this is the amount of series_2 needed to buy 1 unit of series_1 (in average)
    intercept = results.params[0] #this represent the price of series_1 if series_2 is 0
    
    # Calculate the spread
    series_2_price_in_amount_of_series_1 = series_2 * hedge_ratio
    spread = series_1 - series_2_price_in_amount_of_series_1 - intercept
    
    # calculate half life
    try:
        half_life = round(half_life_mean_reversion(spread), 2)
    except SmartError as e:
        return None
    
    # # Calculate revised hedge ratio and spread for series_2
    # """
    # @note: This section revises the hedge ratio for series_2 based on series_1, similar to the original but flipping the calculation.
    # """

    # # Example of revising the hedge ratio (re-run OLS to get updated hedge ratio for series_2)
    # revised_model = sm.OLS(series_2, sm.add_constant(series_1))  # Re-run OLS to get updated hedge ratio
    # revised_results = revised_model.fit()
    # revised_hedge_ratio = revised_results.params[1]  # This is the revised hedge ratio for series_2
    # revised_intercept = revised_results.params[0]  # Revised intercept

    # # Recalculate the revised spread using the new hedge ratio for series_2
    # revised_series_1_price = series_1 * revised_hedge_ratio
    # revised_spread = series_2 - revised_series_1_price - revised_intercept    

    
    # return hedge_ratio,revised_hedge_ratio,  spread, revised_spread
    return hedge_ratio,  spread, half_life


# Calculate ZScore using a rolling window
def calculate_zscore(spread, window=21):
    spread_series = pd.Series(spread)
    
    # Rolling mean and standard deviation
    mean = spread_series.rolling(window=window).mean()
    std = spread_series.rolling(window=window).std()
    
    # Current spread value (latest)
    x = spread_series.rolling(window=1).mean()
    
    # Calculate the Z-score
    zscore = (x - mean) / std
    
    # Return the latest Z-score value
    return zscore

def calculate_mean_zscore(zscore_df:pd.DataFrame, z_score_threshold:float=2):
    higer_z_score = zscore_df[zscore_df.values >= z_score_threshold]
    lower_z_score = zscore_df[zscore_df.values <= -z_score_threshold]
    average_higer_z_score = higer_z_score.mean()
    average_lower_z_score = lower_z_score.mean()
    return average_higer_z_score, average_lower_z_score


def plot_spread(spread, half_life,
        series_1_symbol:str, 
        series_2_symbol:str, 
        title:str='Spread',
        color:str='red',
        ylabel:str='Spread Value'
    ):
    # plt.figure(figsize=(10, 6))
    # plt.subplot(2, 1, 2)
    # plt.plot(spread, label=f'Spread ({series_1_symbol} - {series_2_symbol})', color='red')
    # plt.plot(spread2, label='Spread2', color='blue')  # Add another line for spread2
    # plt.title('Spread Between two assets')
    # plt.legend()
    # plt.grid(True)

    # plt.tight_layout()
    # plt.show()
    # Plotting both spreads on the same chart
    plt.figure(figsize=(10, 4))
    plt.plot(spread, label=f'{series_1_symbol} {series_2_symbol}', color=color)
    # plt.plot(revised_spread, label=f'Revised Spread {series_2_symbol} ', color='blue')
    

    # Adding labels, title, and legend
    plt.title(title)
    plt.xlabel('Time')
    plt.ylabel(ylabel)
    plt.legend()
    plt.grid(True)

    # Display the chart
    plt.tight_layout()
    plt.show()
  
  
def plot(plot_series:any, title:str, label:str,xlabel:str='series', color:str='blue'):
    
    # Creating a BytesIO object to hold the image
    img_buffer = io.BytesIO()
    
    # Recreate the plot
    plt.figure(figsize=(10,6))
    plt.plot(plot_series, label=label , color=color)
    
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel('series')
    plt.legend()
    plt.grid(True)

    # Save the figure to the BytesIO object
    plt.savefig(img_buffer, format='jpeg', dpi=300)# dpi=300 ensures high quality
    plt.close()
    
    
    # Convert the image buffer to base64 string
    img_buffer.seek(0)# Seek to the beginning of the BytesIO object so it can be read
    img_base64 = base64.b64encode(img_buffer.read()).decode('utf-8')

    del img_buffer
    return img_base64

def show_image_b64(img_base64:str, save=False):
    # Decode the Base64 string back to binary data
    img_binary = base64.b64decode(img_base64)

    # Load the image from the binary data using BytesIO
    img_buffer = io.BytesIO(img_binary)
    img_loaded = Image.open(img_buffer)

    # Display the loaded image
    # img_loaded.show()
    # Generate a random file name
    random_name = f"./images/{uuid.uuid4().hex}.png"  # Generates a unique name with .png extension

    # Save the image to a file
    img_loaded.save(random_name)