import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

# Ustawienia pod ekrany mobilne
st.set_page_config(
    page_title="Gold Trading Assistant PRO",
    page_icon="🥇",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Automatyczne odświeżanie strony co 15 sekund
st_autorefresh(interval=15000, limit=None, key="gold_autorefresh")

st.markdown("""
    <style>
    .stApp { max-width: 600px; margin: 0 auto; }
    .buy-badge { background-color: #26a69a; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 22px; text-align: center; color: white; }
    .sell-badge { background-color: #ef5350; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 22px; text-align: center; color: white; }
    .neutral-badge { background-color: #787b86; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 22px; text-align: center; color: white; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=10)
def load_market_data(interval_choice):
    tickers = ["GC=F", "DX-Y.NYB"]
    period_map = {"1m": "1d", "5m": "1d", "15m": "5d", "1h": "1mo", "4h": "3mo", "1d": "1y"}
    period = period_map.get(interval_choice, "5d")
    
    data = yf.download(tickers=tickers, period=period, interval=interval_choice, progress=False)
    if data.empty:
        return None, None

    df_gold = data['Close']['GC=F'].dropna() if 'GC=F' in data['Close'].columns else data['Close'].dropna()
    df_dxy = data['Close']['DX-Y.NYB'].dropna() if 'DX-Y.NYB' in data['Close'].columns else None

    df = pd.DataFrame({'Close': df_gold})
    df['Open'] = data['Open']['GC=F'] if 'Open' in data else df['Close']
    df['High'] = data['High']['GC=F'] if 'High' in data else df['Close']
    df['Low'] = data['Low']['GC=F'] if 'Low' in data else df['Close']
    df = df.dropna()

    df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()

    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean()

    dxy_trend = "Neutralny"
    if df_dxy is not None and not df_dxy.empty:
        dxy_change = df_dxy.iloc[-1] - df_dxy.iloc[-2]
        dxy_trend = "Wzrostowy (Presja spadkowa na Złoto)" if dxy_change > 0 else "Spadkowy (Wsparcie dla Złota)"

    return df, dxy_trend

st.title("🥇 XAU/USD Live Assistant")

# Płynny wybór interwału bezpośrednio na górze
interval = st.select_slider(
    "Interwał czasowy:",
    options=["1m", "5m", "15m", "1h", "4h", "1d"],
    value="15m"
)

data, dxy_info = load_market_data(interval)

if data is not None and not data.empty:
    latest = data.iloc[-1]
    prev = data.iloc[-2]
    price = float(latest['Close'])
    prev_price = float(prev['Close'])
    price_change = price - prev_price
    rsi = float(latest['RSI']) if not np.isnan(latest['RSI']) else 50.0
    atr = float(latest['ATR']) if not np.isnan(latest['ATR']) else 5.0

    st.metric(
        label="Cena Złota (XAUUSD)",
        value=f"${price:,.2f}",
        delta=f"{price_change:+.2f} USD"
    )

    score = 0
    reasons = []

    if latest['EMA_9'] > latest['EMA_21']:
        score += 1
        reasons.append("EMA9 > EMA21 (Trend wzrostowy)")
    else:
        score -= 1
        reasons.append("EMA9 < EMA21 (Trend spadkowy)")

    if rsi < 35:
        score += 2
        reasons.append(f"RSI wyprzedane ({rsi:.1f})")
    elif rsi > 65:
        score -= 2
        reasons.append(f"RSI wykupione ({rsi:.1f})")

    signal = "NEUTRAL"
    if score >= 2:
        signal = "BUY (LONG)"
    elif score <= -2:
        signal = "SELL (SHORT)"

    st.markdown("### 🎯 Sygnał rynkowy")
    if signal == "BUY (LONG)":
        st.markdown('<div class="buy-badge">🚀 KUPUJ (LONG)</div>', unsafe_allow_html=True)
    elif signal == "SELL (SHORT)":
        st.markdown('<div class="sell-badge">🔻 SPRZEDAJ (SHORT)</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="neutral-badge">⏳ NEUTRALNY (CZEKAJ)</div>', unsafe_allow_html=True)

    st.write("")

    if signal != "NEUTRAL":
        sl = price - (1.5 * atr) if "BUY" in signal else price + (1.5 * atr)
        tp = price + (3.0 * atr) if "BUY" in signal else price - (3.0 * atr)

        col1, col2 = st.columns(2)
        with col1:
            st.error(f"🛑 Stop Loss: *${sl:.2f}*")
        with col2:
            st.success(f"🎯 Take Profit: *${tp:.2f}*")

    st.markdown("---")
    st.markdown("### 🌐 Filtr Makro (DXY)")
    st.info(f"DXY: *{dxy_info}*")

    with st.expander("🧮 Kalkulator wielkości pozycji"):
        capital = st.number_input("Kapitał (USD):", value=2000, step=100)
        risk_percent = st.slider("Ryzyko (%):", 0.5, 5.0, 1.0)
        
        risk_amount = capital * (risk_percent / 100)
        sl_pips = abs(price - (price - 1.5 * atr)) * 10
        
        if sl_pips > 0:
            lot_size = risk_amount / (sl_pips * 10)
            st.write(f"Maks. strata: *${risk_amount:.2f}*")
            st.success(f"Wolumen: *{lot_size:.2f} Lota*")

    with st.expander("🔍 Szczegóły wskaźników"):
        for r in reasons:
            st.write(f"• {r}")
        st.write(f"• RSI: {rsi:.2f} | ATR: {atr:.2f}")

else:
    st.error("Błąd pobierania danych.")
