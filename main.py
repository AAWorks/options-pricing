import streamlit as st
st.set_page_config(layout="wide", page_title="Options Pricing", page_icon=":gear:")

from datetime import datetime, date, timedelta

from models.abstract import inputs
from models.openai_env import OptionEnv
from models.baseline_tfa_dqn import TFAModel
from option_types import MODELS, USOption, EUOption

from polygon import Polygon
from utils.tickers import read_tickers
from utils.db_wrapper import read_rows_of_ticker

POLYGON = Polygon(yf_backup=True)

@st.cache_data
def get_tickers():
    return read_tickers()

@st.cache_data
def env_ex(_test):
    return _test.simulate_price_data()

@st.cache_data(ttl=60)
def check_nasdaq_status():
    return POLYGON.exchange_status("nasdaq")

@st.cache_data(ttl=timedelta(hours=1))
def pull_close_prices():
    return POLYGON.last_ticker_prices

@st.cache_data
def get_custom_defaults():
    defaults = {
        "maturity": date.today() + timedelta(days=1),
        "custom_maturity": date.today() + timedelta(days=365),
        "risk_free_rate": POLYGON.risk_free_rate,
        "spot": 100.0,
        "strike": 100.0,
        "implied_volatility": 0.20,
        "dividend_rate": 0.01
    }

    return defaults

DEFAULTS = get_custom_defaults()
ALL_TICKERS = get_tickers()
NASDAQ_STATUS = check_nasdaq_status()
EOD_PRICES = pull_close_prices()

test_defs = {k: v for k, v in DEFAULTS.items() if k != "maturity"}
test_defs["maturity"] = test_defs["custom_maturity"]
test_env = OptionEnv(test_defs)
test_sim_data = env_ex(test_env)

st.title('Quantitative Options Pricing') 
st.caption('Via Black Scholes, Binomial Trees, Monte Carlo Sampling, and a Deep Q-Network Model | By Alejandro Alonso and Roman Chenoweth')

nasdaq, american, eu, dqn = st.tabs(["Options Pricing: NASDAQ-100", "Options Pricing: Custom American Option", "Options Pricing: Custom European Option", "411: In-Depth Deep Q-Network Demo"])

with nasdaq:
    st.info("Pricing Options from the NASDAQ-100 | Work In Progress")
    message_type = {"open": st.success, "extended-hours": st.warning, "closed": st.error} 
    
    message_type[NASDAQ_STATUS](f"Market Status: {NASDAQ_STATUS.replace('-',' ').title()}")
    with st.expander("Note on Data Source"):
        st.caption("This project was originally designed to use real-time data from Polygon.io. All the infrastructure is present, however, due to financial constraints, we opted to terminate our subscription to Polygon.io after a month. So while this pricer can be easily reconfigured to use Polygon.io's data, we currently use a combination of EOD data from Polygon.io and Yahoo Finance [this also means you can use this pricer at all hours :) ].")

    if True: # NASDAQ_STATUS == "open":
        with st.form("nasdaq-price"):
            cola, colb = st.columns(2)
            ticker = cola.selectbox("Underlying Ticker", ALL_TICKERS)
            maturity = colb.selectbox("Expiration Date", POLYGON.expiration_dates(ticker))
            maturity = datetime.strptime(maturity, '%B %d, %Y').date()
            submit = st.form_submit_button("Update Contract Table", use_container_width=True)

        ticker_contracts = POLYGON.get_ticker_contracts_given_exp(ticker, expiration=maturity)

        st.write(ticker_contracts)
        with st.form("price-contract"):
            cola, colb = st.columns(2)
            opt_id = colb.selectbox("Contract ID", ticker_contracts["Contract ID"])
            model = cola.selectbox("Model", MODELS["us"] + ["All Models"])
            contract = ticker_contracts.loc[ticker_contracts['Contract ID'] == opt_id].to_dict('records')[0]
            submittwo = st.form_submit_button("Calculate Fair Value", use_container_width=True)
            
        if submittwo:
            model_name = "all models" if model == "All Models" else f"a {model} model"
            opt = USOption(option_type=contract["Type"],
                strike=contract["Strike"], spot=EOD_PRICES[ticker], 
                maturity=maturity, 
                implied_volatility=float(contract["Implied Volatility"][:-1].replace(",","")) / 100,
                risk_free_rate=DEFAULTS["risk_free_rate"],
                dividend_rate=0.02)
            if model == "Deep Q-Network": st.warning("Options Pricing with the DQN may take a few minutes")
            with st.spinner(f"Pricing {ticker} option #{opt_id} using {model_name}..."):
                if model == "all models": 
                    priced_options = opt.all()
                elif model == "Deep Q-Network":
                    st.error("DQN Not Yet Supported")
                    priced_options = []
                else:
                    priced_options = [opt.priced(model)]
            
            st.info(f"Contract Mark: {contract['Mark']}")
            for priced_option in priced_options:
                st.success(str(priced_option))

with american:
    st.info("Price a Custom American Option")
    with st.form("american-price"):
        opttype, s0, k, volatility, risk_free_r, d, maturity, model, submit = inputs(MODELS["us"] + ["All Models"], DEFAULTS)
    if (maturity - date.today()) / timedelta(days=1) < 0:
        st.error("Contract Expired")
    elif submit:
        model_name = "all models" if model == "All Models" else f"a {model} model"
        opt = USOption(option_type=opttype,
                    strike=k, spot=s0, 
                    maturity=maturity, 
                    implied_volatility=volatility,
                    risk_free_rate=risk_free_r,
                    dividend_rate=d)
        if model == "Deep Q-Network": st.warning("Options Pricing with the DQN may take a few minutes")
        with st.spinner(f"Pricing custom option spread using {model_name}..."):
            if model == "all models": 
                priced_options = opt.all()
            else:
                priced_options = [opt.priced(model)]

        for priced_option in priced_options:
            st.success(str(priced_option))
with eu:
    st.info("Price a Custom European Option")
    with st.form("euro-price"):
        opttype, s0, k, volatility, risk_free_r, d, maturity, model, submit = inputs(MODELS["eu"] + ["All Models"], DEFAULTS)
    if (maturity - date.today()) / timedelta(days=1) < 0:
        st.error("Contract Expired")
    elif submit:
        if maturity - date.today() < timedelta(days=1):
            st.error("Maturity Date Already Passed")
        else:
            model_name = "all models" if model == "All Models" else f"a {model} model"
            opt = EUOption(option_type=opttype,
                    strike=k, spot=s0, 
                    maturity=maturity, 
                    implied_volatility=volatility,
                    risk_free_rate=risk_free_r,
                    dividend_rate=d)
            with st.spinner(f"Pricing custom option spread using {model_name}..."):
                if model == "all models":
                    priced_options = opt.all() 
                else:
                    priced_options = [opt.priced(model)]

        for priced_option in priced_options:
            st.success(str(priced_option))

with dqn:
    st.info("Deep Q-Network Breakdown | Finishing Touches")
    st.subheader("Test Option Specs")
    del test_defs["custom_maturity"]
    ncols = len(test_defs)
    def_keys = list(test_defs.keys())
    columns = st.columns(ncols)
    for n in range(ncols):
        key = def_keys[n]
        value = test_defs[key] if key != "maturity" else test_defs[key].strftime("%m/%d/%Y")
        columns[n].metric(key.replace("_"," ").title(), str(value)[:10])

    st.divider()

    st.subheader("Simulated Option Data (Assuming No Early Excercise)")
    sim_data = {"Option Price": test_sim_data, "Time-Steps": list(range(366))}
    st.line_chart(sim_data, x="Time-Steps", y="Option Price")

    st.divider()
    go = st.button("Price Custom Option", use_container_width=True)
    if go:
        st.subheader("Model")
        option = TFAModel(OptionEnv, test_defs)
        with st.status("Building Model...", expanded=True) as status:
            st.write("Initializing Agent...")
            option.init_agent()
            st.write("Done | Building Replay Buffer...")
            option.build_replay_buffer()
            st.write("Done | Preparing to Train...")
            option.train()
            status.update(label="Model Built - Pricing Option", state="running", expanded=True)
            option.calculate_npv()
            status.update(label="Option Pricing Complete", state="complete", expanded=False)
        
        st.divider()
        st.success(str(option))
        st.divider()
        st.subheader("Train Iteration Log")
        st.dataframe(option.train_log, use_container_width=True)
        st.divider()
        st.subheader("Graphed Average Returns")
        st.line_chart(option.train_iteration_dict, x="Iterations", y="Average Return" )

# with pull:
#     with st.form("tmp_pull"):
#         tmpkey = st.text_input("Polygon.io Key")
#         pwd = st.text_input("Admin Passphrase")
#         submitted = st.form_submit_button("Pull", use_container_width=True)
    
#     if submitted:
#         key = tmpkey if tmpkey.strip() != "" else None

#         if pwd == "123457":
#             with st.spinner("Pulling..."):
#                 Polygon(key=key).store_eod_data()
