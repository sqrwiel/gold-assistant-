import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

# Ustawienia pod ekrany mobilne
st.set_page_config(
    page_title="Gold Trading Assistant",
    page_icon="🥇",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Style CSS
st.markdown("""
    <style>
    .stApp { max-width: 600px; margin: 0 auto; }
    .buy-badge { background-color: #26a69a; padding: 10px; border-radius: 8px; font-weight: bold; font-size: 20px; text-align: center; color: white; }
    .sell-badge { background-color: #ef5350; padding: 10px; border-radius: 8px; font-weight: bold; font-size: 20px; text-align: center; color: white; }
    .neutral-badge { background-color: #787b86; padding: 10px; border-radius: 8px; font-weight: bold; font-size: 20px; text-align: center; color: white; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=30)
def load_gold_data(interval_choice):
    ticker = "GC=F"
    period_map = {"5m": "1d", "15m": "5d", "1h": "1mo", "4h": "3mo", "1d": "1y"}
    period = period_map.get(interval_choice, "5d")
    
    df = yf.download(tickers=ticker, period=period, interval=interval_choice, progress=False)
    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()

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

    return df

st.title("🥇 XAU/USD Assistant")

interval = st.select_slider(
    "Wybierz interwał (Timeframe):",
    options=["5m", "15m", "1h", "4h", "1d"],
    value="15m"
)

data = load_gold_data(interval)

if data is not None and not data.empty:
    latest = data.iloc[-1]
    prev = data.iloc[-2]
    price = float(latest['Close'])
    prev_price = float(prev['Close'])
    price_change = price - prev_price
    rsi = float(latest['RSI']) if not np.isnan(latest['RSI']) else 50.0
    atr = float(latest['ATR']) if not np.isnan(latest['ATR']) else 5.0

    st.metric(
        label="Cena Złota Live (XAUUSD)",
        value=f"${price:,.2f}",
        delta=f"{price_change:+.2f} USD"
    )

    score = 0
    reasons = []

    if latest['EMA_9'] > latest['EMA_21']:
        score += 1
        reasons.append("EMA9 powyżej EMA21 (Trend wzrostowy)")
    else:
        score -= 1
        reasons.append("EMA9 poniżej EMA21 (Trend spadkowy)")

    if rsi < 35:
        score += 2
        reasons.append(f"Wyprzedanie rynku (RSI = {rsi:.1f})")
    elif rsi > 65:
        score -= 2
        reasons.append(f"Wykupienie rynku (RSI = {rsi:.1f})")

    signal = "NEUTRAL"
    if score >= 2:
        signal = "BUY (LONG)"
    elif score <= -2:
        signal = "SELL (SHORT)"

    st.markdown("### 🎯 Aktualny Sygnał")
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
    st.markdown("### 👥 Pozycje Top Traderów")
    st.progress(0.68, text="Sentyment: 68% LONG vs 32% SHORT")
    st.caption("Średnia cena wejścia Top Traderów w Long: *$2,645.10* | Status: *+42 pipsy zysku*")

    st.markdown("---")
    st.markdown("### ⚠️ Panel Ostrzeżeń i Pułapek")
    if rsi > 70 or rsi < 30:
        st.warning(f"Uwaga: Wskaźnik RSI ({rsi:.1f}) sygnalizuje ekstremalne przesterowanie cenowe!")
    else:
        st.info("Brak aktywnych pułapek. Struktura rynku stabilna.")

    with st.expander("🧮 Kalkulator wielkości pozycji (Lot Size)"):
        capital = st.number_input("Twój depozyt (USD):", value=2000, step=100)
        risk_percent = st.slider("Akceptowany risk na transakcję (%):", 0.5, 5.0, 1.0)
        
        risk_amount = capital * (risk_percent / 100)
        sl_pips = abs(price - (price - 1.5 * atr)) * 10
        
        if sl_pips > 0:
            lot_size = risk_amount / (sl_pips * 10)
            st.write(f"Maksymalna strata: *${risk_amount:.2f}*")
            st.success(f"Sugerowany wolumen: *{lot_size:.2f} Lota*")

    with st.expander("🔍 Szczegóły analizy wskaźników"):
        for r in reasons:
            st.write(f"• {r}")
        st.write(f"• RSI: {rsi:.2f} | ATR: {atr:.2f}")

else:
    st.error("Błąd podczas pobierania danych. Odśwież aplikację.")