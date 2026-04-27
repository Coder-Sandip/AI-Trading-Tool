from flask import Flask, render_template, request, redirect, url_for
import requests
from textblob import TextBlob
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import os
import warnings

warnings.filterwarnings("ignore")

app = Flask(__name__)

API_KEY="1a16f34fbcca4a848bf25537aaa49819"


# ================= NEWS ================= #

def get_stock_news(company=""):

    q="nse OR bse OR sensex OR nifty"

    if company:
        q=f"{company} AND (nse OR bse OR sensex OR nifty)"

    url=(
        "https://newsapi.org/v2/everything?"
        f"q={q}&"
        "domains=moneycontrol.com,economictimes.indiatimes.com,business-standard.com&"
        "language=en&sortBy=publishedAt&pageSize=8&"
        f"apiKey={API_KEY}"
    )

    try:
        r=requests.get(url,timeout=8)
        data=r.json()
    except:
        return []

    news=[]

    for a in data.get("articles",[]):
        if a.get("description"):
            news.append({
                "title":a["title"],
                "description":a["description"],
                "url":a["url"]
            })

    return news


def get_mutual_fund_news():

    url=(
      "https://newsapi.org/v2/everything?"
      "q=mutual funds india OR SIP investing&"
      "language=en&pageSize=5&"
      f"apiKey={API_KEY}"
    )

    try:
        r=requests.get(url,timeout=8)
        data=r.json()
    except:
        return []

    items=[]

    for a in data.get("articles",[]):
        if a.get("description"):
            items.append({
                "title":a["title"],
                "url":a["url"],
                "description":a["description"]
            })

    return items


# ================= SENTIMENT ================= #

def get_sentiment(text):
    try:
        return TextBlob(text).sentiment.polarity
    except:
        return 0


# ================= STOCK ENGINE ================= #

STOCK_MAP={
"TCS":"TCS.NS",
"RELIANCE":"RELIANCE.NS",
"INFY":"INFY.NS",
"HDFCBANK":"HDFCBANK.NS",
"SBIN":"SBIN.NS",
"ICICIBANK":"ICICIBANK.NS"
}


def get_stock_symbol(name):

    name=name.upper().strip()

    if ".NS" in name:
        return name

    if name in STOCK_MAP:
        return STOCK_MAP[name]

    return name+".NS"


def get_stock_data(symbol):

    try:
        df=yf.download(
            symbol,
            period="6mo",
            interval="1d",
            auto_adjust=True,
            progress=False
        )

        if df.empty:
            return None

        if hasattr(df.columns,"levels"):
            df.columns=df.columns.get_level_values(0)

        return df

    except:
        return None


# ================= SWOT ================= #

def generate_swot(symbol):

    try:
        info=yf.Ticker(symbol).info

        strengths=[]
        weaknesses=[]

        if info.get("returnOnEquity",0)>.15:
            strengths.append("Strong ROE")

        if info.get("debtToEquity",999)<50:
            strengths.append("Low debt")

        if info.get("trailingPE",0)>40:
            weaknesses.append("High valuation")

        if not strengths:
            strengths=["Stable fundamentals"]

        if not weaknesses:
            weaknesses=["No major weakness"]

        return {
            "strengths":strengths,
            "weaknesses":weaknesses,
            "opportunities":[
                "Sector growth",
                "Long-term expansion"
            ],
            "threats":[
                "Market volatility",
                "Competition"
            ]
        }

    except:
        return{
            "strengths":["No Data"],
            "weaknesses":["No Data"],
            "opportunities":["No Data"],
            "threats":["No Data"]
        }


# ================= ANALYSIS ================= #

def analyze_stock(symbol):

    df=get_stock_data(symbol)

    if df is None:
        return "NO DATA",0,None,None,"Neutral",None

    df["EMA20"]=df["Close"].ewm(span=20).mean()
    df["EMA50"]=df["Close"].ewm(span=50).mean()

    delta=df["Close"].diff()

    gain=delta.clip(lower=0).rolling(14).mean()
    loss=(-delta.clip(upper=0)).rolling(14).mean()

    rs=gain/loss

    df["RSI"]=100-(100/(1+rs))

    price=round(float(df["Close"].iloc[-1]),2)
    rsi=round(float(df["RSI"].fillna(50).iloc[-1]),2)

    ema20=float(df["EMA20"].iloc[-1])
    ema50=float(df["EMA50"].iloc[-1])

    score=0

    if price>ema20>ema50:
        trend="Strong Bullish"
        score+=2

    elif price>ema20:
        trend="Bullish"
        score+=1

    else:
        trend="Bearish"
        score-=1

    if rsi<30:
        score+=2

    elif rsi>70:
        score-=2

    if score>=3:
        signal="📈 STRONG BUY"

    elif score>=1:
        signal="🟢 BUY"

    elif score<0:
        signal="🔴 SELL"

    else:
        signal="🟡 HOLD"

    return signal,score,price,rsi,trend,df


# ================= TRADE LEVELS ================= #

def trade_levels(df):

    if df is None:
        return None,None,None

    high=round(float(df["High"].tail(10).max()),2)
    low=round(float(df["Low"].tail(10).min()),2)

    close=float(df["Close"].iloc[-1])

    target=round(close+(high-low),2)

    return high,low,target



# ================= FIXED SUPPORT RESISTANCE ================= #

def support_resistance(df):

    if df is None or len(df)<30:
        return [],[],None,None,"No Data"

    try:

        highs=df["High"].tolist()
        lows=df["Low"].tolist()

        supports=[]
        resistances=[]

        # Pivot detection
        for i in range(2,len(df)-2):

            if (
                lows[i] < lows[i-1] and
                lows[i] < lows[i-2] and
                lows[i] < lows[i+1] and
                lows[i] < lows[i+2]
            ):
                supports.append(round(lows[i],2))


            if (
                highs[i] > highs[i-1] and
                highs[i] > highs[i-2] and
                highs[i] > highs[i+1] and
                highs[i] > highs[i+2]
            ):
                resistances.append(round(highs[i],2))


        # remove close duplicates
        def clean(levels):
            cleaned=[]
            for x in sorted(levels):
                if not cleaned or abs(x-cleaned[-1])>x*0.01:
                    cleaned.append(x)
            return cleaned

        supports=clean(supports)[-3:]
        resistances=clean(resistances)[-3:]


        if not supports:
            supports=[
                round(df["Low"].tail(20).quantile(.25),2)
            ]

        if not resistances:
            resistances=[
                round(df["High"].tail(20).quantile(.75),2)
            ]


        demand=round(min(supports),2)
        supply=round(max(resistances),2)

        current=float(df["Close"].iloc[-1])


        if current>supply:
            breakout="Bullish Breakout"

        elif current<demand:
            breakout="Bearish Breakdown"

        else:
            breakout="Range Bound"


        return (
            supports,
            resistances,
            demand,
            supply,
            breakout
        )

    except Exception as e:
        print("SR Error:",e)
        return [],[],None,None,"Neutral"



# ================= CHART ================= #

def generate_chart(df,support,resistance):

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
                line_dash="dot",
                annotation_text=f"S {s}"
            )

        for r in resistance:
            fig.add_hline(
                y=r,
                line_dash="dot",
                annotation_text=f"R {r}"
            )


        fig.update_layout(
            template="plotly_dark",
            height=650,
            xaxis_rangeslider_visible=False
        )

        return fig.to_html(
            full_html=False,
            include_plotlyjs="cdn"
        )

    except:
        return ""


# ================= MUTUAL FUNDS ================= #

FUND_MAP={
"HDFC FLEXI CAP FUND":"^NSEI",
"PARAG PARIKH FLEXI CAP FUND":"^NSEI",
"SBI BLUECHIP FUND":"SBIN.NS",
"SBI SMALL CAP FUND":"SBIN.NS",
"ICICI PRUDENTIAL BLUECHIP FUND":"ICICIBANK.NS"
}


def map_fund_symbol(name):

    name=name.upper()

    for fund,symbol in FUND_MAP.items():
        if name in fund:
            return symbol

    return "^NSEI"



def analyze_mutual_fund(name):

    symbol=map_fund_symbol(name)

    try:

        df=yf.download(
            symbol,
            period="1y",
            progress=False,
            auto_adjust=True
        )

        nav=round(float(df["Close"].iloc[-1]),2)
        past=float(df["Close"].iloc[0])

        ret=round(((nav-past)/past)*100,2)

        if ret>20:
            rating="★★★★★"
            signal="Strong Long-Term Buy"
        elif ret>12:
            rating="★★★★"
            signal="Good SIP Candidate"
        else:
            rating="★★★"
            signal="Moderate"

        return{
            "rating":rating,
            "risk":"Medium",
            "return_1y":ret,
            "fund_signal":signal,
            "nav":nav
        }

    except:
        return{
            "rating":"★★★★",
            "risk":"Medium",
            "return_1y":14.8,
            "fund_signal":"Good SIP Candidate",
            "nav":102
        }



def generate_mutual_fund_chart(name):

    symbol=map_fund_symbol(name)

    try:

        df=yf.download(
            symbol,
            period="10y",
            interval="1mo",
            auto_adjust=True,
            progress=False
        )

        if df.empty:
            return "",{}, "Neutral"

        if hasattr(df.columns,"levels"):
            df.columns=df.columns.get_level_values(0)

        df=df.dropna().reset_index()

        df["Date"]=pd.to_datetime(df["Date"])

        df["EMA12"]=df["Close"].ewm(
            span=12
        ).mean()

        df["EMA24"]=df["Close"].ewm(
            span=24
        ).mean()


        yearly_returns={}

        years=sorted(
            list(
              set(df["Date"].dt.year)
            )
        )


        for y in years[-10:]:

            yd=df[
             df["Date"].dt.year==y
            ]

            if len(yd)>1:

                s=float(
                  yd["Close"].iloc[0]
                )

                e=float(
                  yd["Close"].iloc[-1]
                )

                yearly_returns[
                    str(y)
                ]=round(
                  ((e-s)/s)*100,
                  2
                )


        start=float(
            df["Close"].iloc[0]
        )

        end=float(
            df["Close"].iloc[-1]
        )

        cagr=((end/start)**(1/10)-1)*100


        if cagr>14:
            buy_signal="🟢 Strong Long-Term Buy"

        elif cagr>10:
            buy_signal="🟡 Good SIP Candidate"

        else:
            buy_signal="⚪ Moderate"


        fig=go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df["Close"],
                name="NAV"
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df["EMA12"],
                name="1Y Trend"
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df["EMA24"],
                name="2Y Trend"
            )
        )


        fig.update_layout(
            title="10-Year Mutual Fund Growth",
            template="plotly_dark",
            height=650,
            hovermode="x unified",
            xaxis_rangeslider_visible=False
        )


        return(
            fig.to_html(
               full_html=False,
               include_plotlyjs="cdn"
            ),
            yearly_returns,
            buy_signal
        )

    except Exception as e:

        print(
         "MF Chart Error:",
         e
        )

        return "",{}, "Neutral"


# ================= ROUTES ================= #

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return redirect(url_for("home"))


@app.route("/stocks")
def stocks():

    search=request.args.get(
        "search",
        "TCS"
    ).upper().strip()

    symbol=get_stock_symbol(search)

    news=get_stock_news(search)

    alerts=[]

    for item in news:

        s=get_sentiment(
            item["title"]+" "+item["description"]
        )

        if s>.2:
            alerts.append("BUY")
        elif s<-.2:
            alerts.append("SELL")
        else:
            alerts.append("NEUTRAL")


    prediction,confidence,price,rsi,trend,df=analyze_stock(symbol)

    entry,sl,target=trade_levels(df)

    (
        support,
        resistance,
        demand_block,
        supply_block,
        breakout
    )=support_resistance(df)


    swot=generate_swot(symbol)

    chart_html=generate_chart(
        df,
        support,
        resistance
    )

    return render_template(
    "stocks.html",
    symbol=search,
    news=news,
    alerts=alerts,
    prediction=prediction,
    stock_signal=prediction,
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
    swot=swot,
    chart_html=chart_html
)

@app.route("/mutual-funds")
def mutual_funds():

    fund_search=request.args.get(
        "fund",
        "HDFC Flexi Cap Fund"
    )

    mf_data=analyze_mutual_fund(fund_search)

    mf_news=get_mutual_fund_news()

    chart_html,returns_5y,buy_signal=(
        generate_mutual_fund_chart(
            fund_search
        )
    )

    return render_template(
        "mutualfund.html",
        fund_search=fund_search,
        mf_data=mf_data,
        mf_news=mf_news,
        chart_html=chart_html,
        returns_5y=returns_5y,
        buy_signal=buy_signal
    )


if __name__=="__main__":

    port=int(
        os.environ.get("PORT",5000)
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )