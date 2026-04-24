from flask import Flask, render_template, request
import requests
from textblob import TextBlob
import yfinance as yf
import plotly.graph_objects as go

app = Flask(__name__)

API_KEY = "1a16f34fbcca4a848bf25537aaa49819"   # replace with your key


# ---------------- NEWS ---------------- #

def get_stock_news(company=""):
    q = "nse OR bse OR sensex OR nifty"

    if company:
        q = f"{company} AND (nse OR bse OR sensex OR nifty)"

    url = (
        f"https://newsapi.org/v2/everything?"
        f"q={q}&"
        f"domains=moneycontrol.com,economictimes.indiatimes.com,business-standard.com&"
        f"language=en&"
        f"sortBy=publishedAt&"
        f"pageSize=8&"
        f"apiKey={API_KEY}"
    )

    try:
        r = requests.get(url, timeout=8)
        data = r.json()
    except:
        data = {}

    news = []

    for a in data.get("articles", []):
        if a.get("description"):
            news.append({
                "title": a["title"],
                "description": a["description"],
                "url": a["url"]
            })

    return news


# ---------------- SENTIMENT ---------------- #

def get_sentiment(text):
    try:
        return TextBlob(text).sentiment.polarity
    except:
        return 0


# ---------------- STOCK ANALYSIS ---------------- #

def analyze_stock(symbol):

    try:
        df = yf.download(
            symbol,
            period="6mo",
            progress=False,
            auto_adjust=True
        )

        if df is None or df.empty:
            return "NO DATA",0,None,None,"Neutral",None


        # Fix yfinance MultiIndex issue
        if hasattr(df.columns,"levels"):
            df.columns = df.columns.get_level_values(0)


        needed=["Open","High","Low","Close"]

        for col in needed:
            if col not in df.columns:
                return "NO DATA",0,None,None,"Neutral",None


        # Indicators
        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()

        delta = df["Close"].diff()

        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()

        rs = gain / loss

        df["RSI"] = 100 - (100/(1+rs))

        price = round(float(df["Close"].iloc[-1]),2)
        rsi = round(float(df["RSI"].fillna(50).iloc[-1]),2)

        ema20 = float(df["EMA20"].iloc[-1])
        ema50 = float(df["EMA50"].iloc[-1])

        score=0


        if price > ema20 > ema50:
            trend="Strong Bullish"
            score+=2

        elif price > ema20:
            trend="Bullish"
            score+=1

        else:
            trend="Bearish"
            score-=1


        if rsi < 30:
            score+=2

        elif rsi > 70:
            score-=2


        if score>=3:
            signal="📈 STRONG BUY"

        elif score>=1:
            signal="🟢 BUY"

        elif score<=-3:
            signal="📉 STRONG SELL"

        elif score<0:
            signal="🔴 SELL"

        else:
            signal="🟡 HOLD"


        return signal,score,price,rsi,trend,df


    except Exception as e:
        print("Analysis Error:",e)
        return "NO DATA",0,None,None,"Neutral",None



# ---------------- TRADE LEVELS ---------------- #

def trade_levels(df):

    if df is None or df.empty:
        return None,None,None

    try:
        high=round(float(df["High"].tail(10).max()),2)
        low=round(float(df["Low"].tail(10).min()),2)

        close=float(df["Close"].iloc[-1])

        target=round(close+(high-low),2)

        return high,low,target

    except:
        return None,None,None



# ---------------- SUPPORT RESISTANCE ---------------- #

def support_resistance(df):

    if df is None or df.empty:
        return [],[],None,None,"No Data"

    try:
        highs=df["High"].astype(float).tolist()
        lows=df["Low"].astype(float).tolist()

        support=[]
        resistance=[]

        for i in range(2,len(df)-2):

            if (
                highs[i] > highs[i-1]
                and highs[i] > highs[i+1]
            ):
                resistance.append(round(highs[i],2))


            if (
                lows[i] < lows[i-1]
                and lows[i] < lows[i+1]
            ):
                support.append(round(lows[i],2))


        support=sorted(list(set(support)))[:3]
        resistance=sorted(list(set(resistance)))[-3:]


        demand=round(float(df["Low"].tail(20).min()),2)
        supply=round(float(df["High"].tail(20).max()),2)

        current=float(df["Close"].iloc[-1])


        if current>supply:
            breakout="Bullish Breakout"

        elif current<demand:
            breakout="Bearish Breakdown"

        else:
            breakout="Range Bound"


        return (
            support,
            resistance,
            demand,
            supply,
            breakout
        )

    except Exception as e:
        print("SR Error:",e)
        return [],[],None,None,"Neutral"



# ---------------- CHART ---------------- #

def generate_chart(
    df,
    support,
    resistance,
    demand,
    supply,
    entry,
    sl,
    target
):

    if df is None:
        return ""

    try:

        fig=go.Figure()

        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                name="Price"
            )
        )


        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["EMA20"],
                name="EMA20"
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["EMA50"],
                name="EMA50"
            )
        )


        for s in support:
            fig.add_hline(
                y=s,
                annotation_text=f"S {s}",
                line_dash="dot"
            )


        for r in resistance:
            fig.add_hline(
                y=r,
                annotation_text=f"R {r}",
                line_dash="dot"
            )


        if demand:
            fig.add_hrect(
                y0=demand*.995,
                y1=demand*1.005,
                annotation_text="Demand",
                opacity=.15
            )


        if supply:
            fig.add_hrect(
                y0=supply*.995,
                y1=supply*1.005,
                annotation_text="Supply",
                opacity=.15
            )


        if entry:
            fig.add_hline(
                y=entry,
                annotation_text="ENTRY"
            )

        if sl:
            fig.add_hline(
                y=sl,
                annotation_text="SL"
            )

        if target:
            fig.add_hline(
                y=target,
                annotation_text="TARGET"
            )


        fig.update_layout(
            template="plotly_dark",
            title="AI Smart Money Analysis",
            height=700,
            xaxis_rangeslider_visible=False
        )


        return fig.to_html(
            full_html=False,
            include_plotlyjs="cdn"
        )


    except Exception as e:
        print("Chart Error:",e)
        return ""



# ---------------- ROUTE ---------------- #

@app.route("/")
def home():

    search=request.args.get(
        "search",
        "TCS"
    ).upper().strip()

    symbol=search+".NS"


    news=get_stock_news(search)

    alerts=[]

    for item in news:

        sentiment=get_sentiment(
            item["title"]+" "+item["description"]
        )

        if sentiment>.2:
            alerts.append("BUY")

        elif sentiment<-.2:
            alerts.append("SELL")

        else:
            alerts.append("NEUTRAL")


    prediction,confidence,price,rsi,trend,df = analyze_stock(symbol)

    entry,sl,target = trade_levels(df)

    (
        support,
        resistance,
        demand_block,
        supply_block,
        breakout
    ) = support_resistance(df)


    chart_html=generate_chart(
        df,
        support,
        resistance,
        demand_block,
        supply_block,
        entry,
        sl,
        target
    )


    return render_template(
        "index.html",

        symbol=search,
        search_value=search,

        news=news,
        alerts=alerts,

        stock_signal=prediction,
        prediction=prediction,
        confidence=confidence,

        price=price,
        rsi=rsi,
        trend=trend,

        entry=entry,
        sl=sl,
        target=target,

        support=support,
        resistance=resistance,

        demand_block=demand_block,
        supply_block=supply_block,
        breakout=breakout,

        chart_html=chart_html
    )



if __name__=="__main__":
    app.run(debug=True)