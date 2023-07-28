import streamlit as st

from models.binomial_tree import BinomialTreeOption
from models.black_scholes import BlackScholesOption
from models.monte_carlo import MonteCarloOption

from polygon import Polygon

st.set_page_config(layout="wide", page_title="Options Pricing", page_icon=":gear:")
st.title('Quantitative Options Pricing') 
st.caption('Via Black Scholes, Binomial Trees, and Monte Carlo Sampling')
st.caption("Alejandro Alonso and Roman Chenoweth")


binomial, blk = st.tabs(["Binomial Model", "Black Scholes"])

with binomial:
    st.info("Binomial Options Pricing")
with blk:
    st.info("Black Scholes Model for European Options Pricing")

