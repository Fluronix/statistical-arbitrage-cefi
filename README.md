# statistical-arbitrage-cef

This is the prototype of the statistical arbitrage bot.
Statistical arbitrage is a popular trading strategy that involves taking advantage of price differences between correlated assets. 
Note: This is a prototype bot for experimental purposes. There is no guarantee of profit!

# Features
Check out https://youtu.be/OWJS7Y8IHA4?si=A1XvTIORR_m5ExYz

# Prerequisites
python 3.10 (or later) installed

# Installation

1. Clone the repository:
   
        git clone https://github.com/Fluronix/statistical-arbitrage-cefi.git
        cd base-arbitrage-bot
2. create and activate virtual environment

        python3 -m venv venv  
   
     (Linux/Mac)
   
        source venv/bin/activate  
        pip install --upgrade pip 
        pip install -r requirements.txt 
   
     (Windows)

        venv\Scripts\activate
        pip install --upgrade pip 
        pip install -r requirements.txt 

3. Config:

    cd to utils and set your params in the func.py

          TELEGRAM_BOT_API:str = "" #paste your telegram bot token
          YOUR_TELEGRAM_ID:int = 0 #paste your numeric telegram id
          
          BYBIT_API_KEY:str = "" #paste your API key
          BYBIT_API_SECRET:str = "" #paste your API secret key

5. Run CMD

    run python3 main.py and python3 manage.py in different CLI
