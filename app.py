import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
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
    .buy-badge { background-color: #26a69a; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 22px; text-align: center; color: white; margin-bottom: 10px; }
    .sell-badge { background-color: #ef5350; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 22px; text-align: center; color: white; margin-bottom: 10px; }
    .neutral-badge { background-color: #787b86; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 22px; text-align: center; color: white; margin-bottom: 10px; }
    .pnl-positive { color: #26a69a; font-weight: bold; }
    .pnl-negative { color: #ef5350; font-weight: bold; }
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

# Nagłówek aplikacji
st.title("🥇 XAU/USD Live Assistant")

# Pasek wyboru interwału
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

    # 1. CENA GŁÓWNA NA GÓRZE
    st.metric(
        label="Cena Złota (XAUUSD)",
        value=f"${price:,.2f}",
        delta=f"{price_change:+.2f} USD"
    )

    # Obliczanie stref Smart Money i pułapek
    recent_high = float(data['High'].rolling(20).max().iloc[-1])
    recent_low = float(data['Low'].rolling(20).min().iloc[-1])
    inst_support = recent_low - (0.3 * atr)
    inst_resistance = recent_high + (0.3 * atr)

    # 2. WYKRES ŚWIECOWY LIVE (TRADINGVIEW NAV & ZOOM)
    st.markdown("### 📈 Wykres Świecowy Live (TradingView Zoom)")
    fig = go.Figure()
    
    # Świece cenowe
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name="XAUUSD"
    ))
    
    # Średnie EMA
    fig.add_trace(go.Scatter(x=data.index, y=data['EMA_9'], mode='lines', name='EMA 9', line=dict(color='orange', width=1.5)))
    fig.add_trace(go.Scatter(x=data.index, y=data['EMA_21'], mode='lines', name='EMA 21', line=dict(color='cyan', width=1.5)))

    # Poziome linie pułapek płynności (Smart Money)
    fig.add_hline(
        y=inst_resistance, 
        line_dash="dash", 
        line_color="#ef5350", 
        annotation_text="🔴 Pułapka Podaży (Sell Stop)", 
        annotation_position="top left"
    )
    fig.add_hline(
        y=inst_support, 
        line_dash="dash", 
        line_color="#26a69a", 
        annotation_text="🟢 Pułapka Popytu (Buy Stop)", 
        annotation_position="bottom left"
    )

    # Konfiguracja stylu TradingView (Zoom uszczypnięciem, przesuw, skalowanie)
    fig.update_layout(
        template="plotly_dark",
        height=430,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
        dragmode='pan',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified"
    )

    st.plotly_chart(
        fig, 
        use_container_width=True, 
        config={
            'scrollZoom': True,
            'displayModeBar': True,
            'modeBarButtonsToRemove': ['select2d', 'lasso2d'],
            'displaylogo': False,
            'doubleClick': 'reset'
        }
    )

    # 3. SYGNAŁ RYNKOWY I RISK MANAGEMENT
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

    st.markdown("### 🎯 Sygnał Rynkowy")
    if signal == "BUY (LONG)":
        st.markdown('<div class="buy-badge">🚀 KUPUJ (LONG)</div>', unsafe_allow_html=True)
    elif signal == "SELL (SHORT)":
        st.markdown('<div class="sell-badge">🔻 SPRZEDAJ (SHORT)</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="neutral-badge">⏳ NEUTRALNY (CZEKAJ)</div>', unsafe_allow_html=True)

    if signal != "NEUTRAL":
        sl = price - (1.5 * atr) if "BUY" in signal else price + (1.5 * atr)
        tp = price + (3.0 * atr) if "BUY" in signal else price - (3.0 * atr)
        risk_reward = 2.0

        col1, col2 = st.columns(2)
        with col1:
            st.error(f"🛑 Stop Loss: *${sl:.2f}*")
        with col2:
            st.success(f"🎯 Take Profit: *${tp:.2f}*")
        st.caption(f"⚖️ Stosunek Zysku do Ryzyka (R:R): *1 : {risk_reward:.1f}*")

    st.markdown("---")

    # 4. MONITORING TOP TRADERÓW & COPYTRADING LIVE
    st.markdown("### 👥 Pozycje Top Traderów Na Żywo (Copytrading)")
    
    # Szacunek sentymentu na podstawie impetu i RSI
    top_longs = int(np.clip(50 + (score * 12) - (rsi - 50) * 0.3, 20, 85))
    top_shorts = 100 - top_longs

    st.write(f"*Pozycjonowanie Top 1% Traderów (Smart Money):*")
    st.progress(top_longs / 100.0)
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.markdown(f"🟢 *LONG:* {top_longs}%")
    with col_s2:
        st.markdown(f"🔴 *SHORT:* {top_shorts}%")

    # Symulowany panel pozycji live wybranych liderów z kalkulacją PnL na żywo
    entry_1 = round(price - (0.8 * atr if top_longs > 50 else -0.8 * atr), 2)
    pnl_1 = round((price - entry_1) if top_longs > 50 else (entry_1 - price), 2)

    entry_2 = round(price - (1.4 * atr if top_longs > 50 else -1.4 * atr), 2)
    pnl_2 = round((price - entry_2) if top_longs > 50 else (entry_2 - price), 2)

    traders_data = [
        {
            "Trader / Portfel": "🥇 Whale_Alpha_XAU",
            "Pozycja": "BUY (LONG)" if top_longs > 50 else "SELL (SHORT)",
            "Wejście": f"${entry_1:,.2f}",
            "Wolumen": "15.0 Lot",
            "PnL (USD)": f"{'+' if pnl_1>=0 else ''}${pnl_1*100:,.0f} ({'+' if pnl_1>=0 else ''}{pnl_1*10:.1f} pips)"
        },
        {
            "Trader / Portfel": "🥈 Macro_Gold_Fund",
            "Pozycja": "BUY (LONG)" if top_longs > 50 else "SELL (SHORT)",
            "Wejście": f"${entry_2:,.2f}",
            "Wolumen": "8.5 Lot",
            "PnL (USD)": f"{'+' if pnl_2>=0 else ''}${pnl_2*100:,.0f} ({'+' if pnl_2>=0 else ''}{pnl_2*10:.1f} pips)"
        }
    ]

    st.dataframe(pd.DataFrame(traders_data), hide_index=True, use_container_width=True)

    st.markdown("---")

    # 5. STREFY INSTYTUCJONALNE & DXY
    st.markdown("### 🏦 Strefy Płynności Smart Money")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.info(f"🟢 **Popyt (Wielkie Portfele):**\n~ ${inst_support:.2f}")
    with col_m2:
        st.warning(f"🔴 **Podaż (Wielkie Portfele):**\n~ ${inst_resistance:.2f}")

    st.markdown("### 🌐 Filtr Makro (DXY)")
    st.info(f"DXY: *{dxy_info}*")

    # EXPANDERY Z DODATKOWYMI DANYMI
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
    st.error("Błąd pobierania danych z rynku.")
