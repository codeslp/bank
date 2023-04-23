from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.schema import PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, jsonify, abort, request, make_response
from flask_migrate import Migrate
import uuid
import secrets
import hashlib
from werkzeug.exceptions import HTTPException, BadRequest
import json
import requests
from datetime import datetime
from datetime import timedelta

# configure an instance and connect to db. This would otherwise be in __init__.py
app = Flask(__name__, instance_relative_config=True)
app.config.from_mapping(
    SECRET_KEY='dev',
    SQLALCHEMY_DATABASE_URI='postgresql://postgres@localhost:5432/bank',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ECHO=True
)

##### SCRAMBLE PASSWORD #####
def scramble(password: str):
    """ hash and salt the given password"""
    salt = secrets.token_hex(16)
    return hashlib.sha512((password + salt).encode('utf-8')).hexdigest()




######## ERROR HANDLING #########

@app.errorhandler(HTTPException)
def handle_exception(e):
    """Return JSON instead of HTML for HTTP errors."""
    # start with the correct headers and status code from the error
    response = e.get_response()
    # replace the body with JSON
    response.data = json.dumps({
        "code": e.code,
        "name": e.name,
        "description": e.description,
    })
    print("Something went wrong: ", e)
    response.content_type = "application/json"
    return response

@app.errorhandler(BadRequest)
def handle_bad_request(e):
    response = e.get_response()
    response.data = json.dumps({
        "code": e.code,
        "name": e.name,
        "description": e.description,
    })
    print("Something went wrong: ", e)
    response.content_type = "application/json"
    return response



###### MODELS: #######

##If you change anything in these classes in these models you need to do an upgrade and migrate-- 
# BC this is all in one file now

db = SQLAlchemy()
db.init_app(app)
migrate = Migrate(app, db)

class Customers(db.Model):
    __tablename__ = "customers"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = db.Column(db.String(128), nullable=False)
    last_name = db.Column(db.String(128), nullable=False)
    pin = db.Column(db.Integer, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    portfolio_id = db.Column(UUID(as_uuid=True), db.ForeignKey('portfolios.id'), nullable=True)

    # serialize tells us what each table should return, telling what columns to return and giving us
    # a chance in python to optimize the data types we want to returnflask 
    def serialize(self):
        return {
            'id': str(self.id),
            'first_name': self.first_name,
            'last_name': self.last_name,
            'pin': self.pin,
            'password': self.password,
            'portfolio_id': str(self.portfolio_id)
        }


class Accounts(db.Model):
    __tablename__ = "accounts"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    balance = db.Column(db.Numeric, nullable=False, default=0.00)
    hold = db.Column(db.Boolean, nullable=False, default=False)
    acct_type_id = db.Column(db.Integer, db.ForeignKey('account_types.id'), nullable=False)
    customer_id = db.Column(UUID(as_uuid=True), db.ForeignKey('customers.id'), nullable=False)

    def serialize(self):
        return {
            'id': str(self.id),
            'balance': float(self.balance),
            'acct_type_id': self.acct_type_id,
            'hold': self.hold
        }


class AccountTypes(db.Model):
    __tablename__ = "account_types"
    id = db.Column(db.Integer, autoincrement = True, primary_key=True)
    type = db.Column(db.String(128), nullable=False)
    interest_rate = db.Column(db.Numeric, nullable=False, default=0.0)
    min_balance = db.Column(db.Numeric, nullable=False, default=0.0)
    # accounts = db.relationship('Accounts', backref='account_types', lazy=True)

    def serialize(self):
        return {
            'id': self.id,
            'type': self.type,
            'interest_rate': float(self.interest_rate),
            'min_balance': float(self.min_balance)
        }

class Portfolios(db.Model):
    __tablename__ = "portfolios"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = db.Column(UUID(as_uuid=True), db.ForeignKey('customers.id'), nullable=False)
    # customer = db.relationship('Customers', back_populates='portfolio')
    # positions = db.relationship('Positions', back_populates='portfolio')

    def serialize(self):
        return {
            'id': str(self.id),
            'customer_id': str(self.customer_id)
        }

class Positions(db.Model):
    __tablename__ = "positions"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker_id = db.Column(UUID(as_uuid=True), db.ForeignKey('tickers.id'), nullable=True)
    portfolio_id = db.Column(UUID(as_uuid=True), db.ForeignKey('portfolios.id'), nullable=False)
    # tickers = db.relationship('Tickers', back_populates='positions')

    def serialize(self):
        return {
            'id': str(self.id),
            'ticker_id': str(self.ticker_id),
            'portfolio_id': str(self.portfolio_id)
        }

class Tickers(db.Model):
    __tablename__ = "tickers"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = db.Column(db.String(128), nullable=False)
    price = db.Column(db.Numeric, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    # positions = db.relationship('Positions', back_populates='tickers')

    def serialize(self):
        return {
            'id': str(self.id),
            'ticker': self.ticker,
            'price': float(self.price),
            'quantity': self.quantity,
        }

class Transactions(db.Model):
    __tablename__ = "transactions"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    amount = db.Column(db.Numeric, nullable=False)
    note = db.Column(db.String(128), nullable=False)
    debit_id = db.Column(UUID(as_uuid=True), nullable=True)
    credit_id = db.Column(UUID(as_uuid=True), nullable=True)
    customer_id = db.Column(UUID(as_uuid=True), db.ForeignKey('customers.id'), nullable=False)

    def serialize(self):
        return {
            'id': str(self.id),
            'amount': float(self.amount),
            'note': self.note,
            'debit_id': str(self.debit_id),
            'credit_id': str(self.credit_id),
            'customer_id': str(self.customer_id)
        }

class AccountsCustomers(db.Model):
    __tablename__ = "accounts_customers"
    account_id = db.Column(UUID(as_uuid=True), db.ForeignKey('accounts.id'), nullable=False)
    customer_id = db.Column(UUID(as_uuid=True), db.ForeignKey('customers.id'), nullable=False)
    __table_args__ = (
        db.PrimaryKeyConstraint('account_id', 'customer_id'),
        {})

    def serialize(self):
        return {
            'account_id': str(self.account_id),
            'customer_id': str(self.customer_id)
        }


# Customers.accounts = db.relationship('Accounts', secondary='accounts_customers', back_populates='customers')
# Accounts.account_types = db.relationship('AccountTypes', back_populates='accounts')








####### API endpoints ########


##### START OF Customers endpoints   #####

# customers_index
@app.route('/customers', methods = ['GET']) # this decorator takes a path and a list of HTTP verbs
def customer_index():
    customers = Customers.query.all()  # this is the ORM performing a SELECT query
    result = []
    for t in customers:
        result.append(t.serialize()) # buid list of customers as dictionaries
    return jsonify(result) # this returns a JSON result


# customer_id
@app.route('/customers/<id>', methods = ['GET'])
def customer_show(id: int):
    customer = Customers.query.get_or_404(id)
    return jsonify(customer.serialize())



# customer_create
@app.route('/customers', methods = ['POST'])
def customer_create():
    if 'first_name' in request.json and 'last_name' in request.json and 'pin' in request.json and 'password' in request.json:
        customer = Customers(
            first_name = request.json['first_name'], 
            last_name = request.json['last_name'], 
            pin = request.json['pin'], 
            password = scramble(request.json['password']))
        
        db.session.add(customer)
        db.session.commit()
        return jsonify(customer.serialize()), 201
    else:
        return jsonify({"error": "Missing required fields"}), abort(400)
    


# customer_update
@app.route('/customers/<id>', methods = ['PUT'])
def customer_update(id: int):
    customer = Customers.query.get_or_404(id)
    if 'first_name' in request.json:
        customer.first_name = request.json['first_name']
    if 'last_name' in request.json:
        customer.last_name = request.json['last_name']
    if 'pin' in request.json:
        customer.pin = request.json['pin']
    if 'password' in request.json:
        customer.password = scramble(request.json['password'])
    db.session.commit()
    
    try:
        db.session.commit()
        return jsonify(customer.serialize())
    except:
        return jsonify({"error": "Could not add user"}), abort(400)

##### END OF CUSTOMERS ENDPOINTS #####



######## START ACCOUNTS ENDPOINTS ########

# accounts_index
@app.route('/accounts', methods = ['GET']) 
def account_index():
    accounts = Accounts.query.all()  
    result = []
    for t in accounts:
        result.append(t.serialize()) 
    return jsonify(result)


# account_id
@app.route('/accounts/<id>', methods = ['GET'])
def account_show(id: int):
    accounts = Accounts.query.get_or_404(id)
    return jsonify(accounts.serialize())


# customer_accounts (get all accounts for a customer)  
@app.route('/customers/<id>/accounts', methods = ['GET'])
def customer_accounts(id: int):
    customer_id = id
    accounts = Accounts.query.filter(Accounts.customer_id == customer_id).all()
    result = []
    for t in accounts:
        result.append(t.serialize()) 
    return jsonify(result)


# account_create
@app.route('/accounts', methods = ['POST'])
def account_create():
    if 'balance' in request.json and 'acct_type_id' and 'customer_id' and 'debit_id' in request.json:
        accounts = Accounts(
            balance = request.json['balance'], 
            acct_type_id = request.json['acct_type_id'],
            customer_id = request.json['customer_id'])
        
        db.session.add(accounts)
        db.session.commit()

        transaction_data = {
            'customer_id': request.json['customer_id'],
            'amount': request.json['balance'],
            'note': f"Initial deposit at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            'debit_id': request.json['debit_id'],
            'credit_id': accounts.id
        }

        transaction = Transactions(**transaction_data)
        db.session.add(transaction)
        db.session.commit()

        return jsonify(accounts.serialize()), 201
    else:
        return jsonify({"error": "Missing required fields"}), abort(400)


# account_withdrawal
@app.route('/accounts/<id>/withdrawal', methods = ['GET','POST'])
def account_withdrawal(id: int):
    if 'amount' in request.json and 'customer_id' in request.json and request.method == 'POST' and request.json['amount'] != 0 and 'pin' in request.json:
        account = Accounts.query.get_or_404(id)
        amount = float(request.json['amount'])
        pin = request.json['pin']
        customer = Customers.query.get_or_404(request.json['customer_id'])

        if account is None:
            return jsonify({"error": "Account not found"}), abort(400)
        
        if account.balance >= amount and str(account.customer_id) == request.json['customer_id'] and int(customer.pin) == pin:
            account.balance = float(account.balance) - amount
            db.session.add(account)
            db.session.commit()

            transaction_data = {
                'customer_id': request.json['customer_id'],
                'amount': request.json['amount'],
                'note': f"Withdrawal at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                'debit_id': account.id,
                'credit_id': None
            }
            transaction = Transactions(**transaction_data)
            db.session.add(transaction)
            db.session.commit()

            return jsonify({"account": account.serialize(), "transaction": transaction.serialize()})

        elif float(account.balance) < amount:
            return jsonify({"error": "Insufficient Funds"}), abort(400)
        
        elif customer.pin != request.json['pin']:
            return jsonify({"error": "Incorrect PIN"}), abort(400)
        
    else:
        return jsonify({"error": "Missing required fields"}), abort(400)
        

# account deposit
@app.route('/accounts/<id>/deposit', methods = ['GET','POST'])
def account_deposit(id: int):
    if 'amount' in request.json and 'customer_id' in request.json and request.method == 'POST' and request.json['amount'] != 0 and 'pin' in request.json:
        account = Accounts.query.get_or_404(id)
        amount = float(request.json['amount'])
        pin = request.json['pin']
        customer = Customers.query.get_or_404(request.json['customer_id'])

        if account is None:
            return jsonify({"error": "Account not found"}), abort(400)
        
        if str(account.customer_id) == request.json['customer_id'] and int(customer.pin) == pin:
            account.balance = float(account.balance) + amount
            db.session.add(account)
            db.session.commit()
                
            transaction_data = {
                'customer_id': request.json['customer_id'],
                'amount': request.json['amount'],
                'note': f"Deposit at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                'debit_id': None,
                'credit_id': account.id
            }
            transaction = Transactions(**transaction_data)
            db.session.add(transaction)
            db.session.commit()

            return jsonify({"account": account.serialize(), "transaction": transaction.serialize()})
        
        elif customer.pin != request.json['pin']:
            return jsonify({"error": "Incorrect PIN"}), abort(400)
    
    else:
        return jsonify({"error": "Missing required fields"}), abort(400)



#######  END OF ACCOUNTS ENDPOINTS #########



######## START OF TRANSACTIONS ENDPOINTS ########

# transactions_index           
@app.route('/transactions', methods = ['GET'])
def transactions_index():
    transactions = Transactions.query.all()
    result = []
    for t in transactions:
        result.append(t.serialize()) 
    return jsonify(result)

#transactions_customer (get all transactions for a customer) 
@app.route('/customers/<id>/transactions', methods = ['GET'])
def customer_transactions(id: int):
    customer_id = id
    transactions = Transactions.query.filter(Transactions.customer_id == customer_id).all()
    result = []
    for t in transactions:
        result.append(t.serialize()) 
    return jsonify(result)

#transactions_account (get all transactions for an account) 
@app.route('/accounts/<id>/transactions', methods = ['GET'])
def account_transactions(id: int):
    account_id = id
    transactions = Transactions.query.filter(Transactions.debit_id == account_id).all()
    result = []
    for t in transactions:
        result.append(t.serialize()) 
    return jsonify(result)

######## END OF TRANSACTIONS ENDPOINTS ########

############ START OF (PORTFOLIO) & POSITIONS ENDPOINTS ###########

# portfolios_index
@app.route('/portfolios', methods = ['GET'])
def portfolios_index():
    portfolios = Portfolios.query.all()
    result = []
    for p in portfolios:
        result.append(p.serialize()) 
    return jsonify(result)

#portfolio_customer (get all portfolios for a customer) ###untested
@app.route('/customers/<id>/portfolios', methods = ['GET'])
def customer_portfolios(id: int):
    customer_id = id
    portfolios = Portfolios.query.filter(Portfolios.customer_id == customer_id).all()
    result = []
    for p in portfolios:
        result.append(p.serialize()) 
    return jsonify(result)

# customer_portfolio_positions (show portfolio positions for a customer) 
# JOIN customer, on customer_id w    portfolios    on portfolio_id w    positions    on ticker_id with    tickers 

@app.route('/customers/<id>/positions', methods = ['GET'])
def customer_positions(id: int):
    customer_id = id
    portfolio_id = Portfolios.query.filter(Portfolios.customer_id == customer_id).first()
    print(portfolio_id)
    positions = Positions.query.filter(Positions.portfolio_id == portfolio_id.id).all()
    result = []
    for p in positions:
        result.append(p.serialize())
    return jsonify(result)

# customer portfolio positions tickers
# JOIN customer, on customer_id w    portfolios    on portfolio_id w    positions    on ticker_id with    tickers 

@app.route('/customers/<id>/tickers', methods = ['GET'])
def customer_tickers(id: int):
    customer_id = id
    portfolio = Portfolios.query.filter(Portfolios.customer_id == customer_id).first()
    positions = Positions.query.filter(Positions.portfolio_id == portfolio.id).all()
    positions_result = []
    for p in positions:
        positions_result.append(p.serialize())
    
    result = []
    ticker_list = []

    for r in positions_result:
        ticker_id = r['ticker_id']
        ticker_list.append(ticker_id)


    for t in ticker_list:
        tickers = Tickers.query.filter(Tickers.id == t).all()
        for t in tickers:
                result.append(t.serialize())
    return jsonify(result)




# customer positions tickers (Get ticker sell price from polygon API)
@app.route('/positions/<id>/tickers', methods = ['GET'])

def positions_tickers(id: int):
    position_id = id
    ticker_id = Positions.query.filter(Positions.id == position_id).first()
    ticker_row = Tickers.query.filter(Tickers.id == ticker_id.ticker_id).first()
    ticker = ticker_row.ticker
  
    ##############  POLYGON API CALL  ######################################

    """Get the current price of a ticker.

    :param ticker: The ticker to get the price of.
    :type ticker: str
    :return: The current price of the ticker.
    :rtype: float
    """
    api_key = "6dUHDmEeO0iPwf0NJ3g3ehpw_8YgLLXd"
    yest_date = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    url = f"https://api.polygon.io/v1/open-close/{ticker}/{yest_date}?adjusted=true&apiKey={api_key}"
    # print(url)
    response = requests.get(url)
    if response.status_code == 200:
        # print(response.json()['close'])
        ticker_value = response.json()["close"] * ticker_row.quantity
        ticker_value_dict = {f"{ticker}_position_value": ticker_value}
        ######THIS IS NOT "JSONIFIED", BC I NEED TO USE THE RETURN VALUE IN ANOTHER FUNCTION, AND IF YOU JSONIFY IT, IT WILL NOT BE SERIALIZABLE########
        return (ticker_value_dict)
    else:
        raise Exception('Error getting price of ticker: ' + ticker)
    
    ############### END OF POLYGON API CALL  ################################


# # get price of ticker from polygon API
# @app.route('/ticker_price')
# def ticker_price():
#     if "ticker" in request.json and "quantity" in request.json:
#         ticker = request.json(['ticker'])
#         quantity = request.json(['quantity'])
#         api_key = "6dUHDmEeO0iPwf0NJ3g3ehpw_8YgLLXd"
#         yest_date = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
#         url = f"https://api.polygon.io/v1/open-close/{ticker}/{yest_date}?adjusted=true&apiKey={api_key}"
#         # print(url)
#         response = requests.get(url)
#         if response.status_code == 200:
#             # print(response.json()['close'])
#             ticker_value = response.json()["close"] * quantity
#             ticker_value_dict = {f"{ticker}_position_value": ticker_value}
#             ######THIS IS NOT "JSONIFIED", BC I NEED TO USE THE RETURN VALUE IN ANOTHER FUNCTION, AND IF YOU JSONIFY IT, IT WILL NOT BE SERIALIZABLE########
#             return (ticker_value_dict)


# portfolio_positions (show portfolio positions VALUES for a portfolio)
@app.route('/portfolios/<id>/positions', methods = ['GET'])
def portfolio_positions(id: int):
    portfolio_id = id
    positions = Positions.query.filter(Positions.portfolio_id == portfolio_id).all()
    result = []
    for p in positions:
        position_value = positions_tickers(p.id)
        result.append(position_value)
    return (jsonify(result))

# portfolio_positions_tickers (BUY stock with money from checking acct)
@app.route('/portfolios/<id>/positions/buy', methods = ['POST'])
def buy_ticker(id: int):
    portfolio_id = id
    if "ticker" in request.json and "quantity" in request.json and "account_id" in request.json:
        ticker = request.json["ticker"]
        # ticker_row = Tickers.query.filter(Tickers.ticker == ticker).first()
        # ticker_id = ticker_row.id
        quantity = request.json["quantity"]
        account_id = request.json["account_id"]
        account_row = Accounts.query.filter(Accounts.id == account_id).first()


   ##########  POLYGON API CALL ######################################
        api_key = "6dUHDmEeO0iPwf0NJ3g3ehpw_8YgLLXd"
        yest_date = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        url = f"https://api.polygon.io/v1/open-close/{ticker}/{yest_date}?adjusted=true&apiKey={api_key}"
        response = requests.get(url)
        if response.status_code == 200:
            ticker_value = response.json()["close"]
        else:
            raise Exception('Error getting price of ticker: ' + ticker)
   ############ END OF POLYGON API CALL ##############################

        total_cost = ticker_value * quantity
        # check to see if account if account is a checking account and has enough money to buy stock
        if account_row.acct_type_id == 1:
            balance = float(account_row.balance)
            if balance >= total_cost:
                balance -= total_cost
                balance = round(balance, 2)
                account_row.balance = balance
                db.session.commit()

                # check to see if ticker in any positions, if so, add quantity to that ticker:
                
                all_portfolios_positions = Positions.query.filter(Positions.portfolio_id == portfolio_id).all()
                all_position_ticker_ids = []
                all_position_tickers = []
                print("===================================== all portfolios positions line 621", all_portfolios_positions)
                for p in all_portfolios_positions:
                    all_position_ticker_ids.append(p.ticker_id)
                for i in all_position_ticker_ids:
                    ticker_row = Tickers.query.filter(Tickers.id == i).first()
                    all_position_tickers.append(ticker_row.ticker)
                print("===================================== all position ticker_ids line 625", all_position_ticker_ids)
                print("===================================== all position line 626", all_position_tickers)
                # is this ticker in the list?
                if ticker in all_position_tickers:
                    for p in all_position_tickers:
                        if p == ticker:
                            match_ticker_id = Tickers.query.filter(Tickers.ticker == ticker).first()
                            ticker_to_update = Tickers.query.filter(Tickers.id == match_ticker_id.id).first()
                            ticker_to_update.quantity += quantity
                            db.session.commit()
                            customer_id = Customers.query.filter(Customers.id == portfolio_id).first()
                            transaction_data = {
                                "id": uuid.uuid4(),
                                "customer_id": customer_id,
                                "debit_id": account_id,
                                "credit_id": portfolio_id,
                                "amount": total_cost,
                                "note": f"Buy, added {quantity} shares of {ticker} for {total_cost}; added to position at {datetime.now()}"
                            }
                            updated_ticker_row = Tickers.query.filter(Tickers.id == match_ticker_id).first()
                            new_transaction = Transactions(**transaction_data)
                            db.session.add(new_transaction)
                            db.session.commit()
                            return jsonify(updated_ticker_row.serialize(), new_transaction.serialize())

                # if ticker not in any positions, create new ticker and position:
                else:
                    new_ticker_id = uuid.uuid4()
                    new_position_id = uuid.uuid4()

                    new_ticker = Tickers(id = new_ticker_id, ticker = ticker, price = ticker_value, quantity = quantity)
                    db.session.add(new_ticker)
                    db.session.commit()

                    new_position = Positions(id = new_position_id, ticker_id = new_ticker_id, portfolio_id = portfolio_id)
                    db.session.add(new_position)
                    db.session.commit()
                    customer_row = Customers.query.filter(Customers.id == account_row.customer_id).first()

                    customer_id = customer_row.id
                    portfolio_id = new_position.portfolio_id
                    transaction_data = {
                        "id": uuid.uuid4(),
                        "customer_id": customer_id,
                        "debit_id": account_id,
                        "credit_id": portfolio_id,
                        "amount": total_cost,
                        "note": f"Buy {quantity} shares of {ticker} for {total_cost}; created new position, credited to portfolio at {datetime.now()}"
                    }
                    new_transaction = Transactions(**transaction_data)
                    db.session.add(new_transaction)
                    db.session.commit()

                    return jsonify(new_ticker.serialize(), new_position.serialize(), new_transaction.serialize())
            else:
                return jsonify("Insufficient funds")
        else:
            return jsonify("Funding account must be a checking account")
    else:
        return jsonify("Missing required fields")
    

# @app.route('/portfolios/<id>/positions/sell', methods = ['POST'])
# def sell_ticker(id: int):
#     portfolio_id = id
    





############# END OF (PORTFOLIO) POSITIONS ENDPOINTS ###########

# This is where we tell it to start runnning and start listening
##### this would go in your wsgi.py file if you were using a more separated file structure

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug = True)