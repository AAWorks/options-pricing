# Abstract Option Class
import streamlit as st

from abc import ABC, abstractmethod
from datetime import date, timedelta
from torch import tensor


class Option(ABC):
    def __init__(self, params, with_tensors=False, name="BaseOption"):
        self._name = name

        try:
            self._maturity = params["maturity"]
            params["maturity"] = (self._maturity - date.today()) / timedelta(days=365)
            self._option_type = params["option_type"]

            if with_tensors:
                params = {k: tensor(v, requires_grad=True) for k, v in params.items() if k != "option_type"}

            self._spot = params["spot"]
            self._strike = params["strike"]
            self._time = params["maturity"]
            self._iv = params["implied_volatility"]
            self._r = params["risk_free_rate"]
            self._d = params["dividend_rate"]
        except Exception as e:
            st.error(f"Missing Params - {e}")
            raise Exception("Missing Params")

    @property
    def option_type(self):
        return self._option_type

    @property
    def strike_price(self): 
        return self._strike

    @property
    def spot_price(self): 
        return self._spot

    @property
    def time(self): 
        return self._time

    @property
    def implied_volatility(self): 
        return self._iv
    
    @property
    def risk_free_rate(self):
        return self._r

    @property
    def dividend_rate(self):
        return self._d

    @property
    @abstractmethod
    def npv(self):
        return -1

    @property
    @abstractmethod
    def greeks(self):
        pass

    def __str__(self):
        return f"Option Price ({self._name} Model): ${self.npv}"

def inputs(region_models, defaults):
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    opttype = col1.selectbox("Option Type", ["C", "P"])
    s0 = float(col2.number_input("Spot Price", defaults["spot"]))
    k = float(col3.number_input("Strike Price", defaults["strike"]))
    iv = float(col4.number_input("Volatility", defaults["volatility"]))
    d = float(col6.number_input("Dividend Rate", defaults["dividend_rate"]))
    r = float(col5.number_input("Risk Free Rate", defaults["risk_free_rate"]))
    cola, colb = st.columns(2)
    maturity = cola.date_input("Maturity Date", defaults["maturity"])
    model = colb.selectbox("Model", region_models)
    submit = st.form_submit_button("Calculate Price", use_container_width=True)

    return opttype, s0, k, iv, d, r, maturity, model, submit