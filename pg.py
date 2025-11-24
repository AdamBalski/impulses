from typing import List, Tuple
import statistics
import collections
import operator
import datetime
from impulses_sdk import models
from impulses_sdk import client
from impulses_sdk import operations as impulse_ops
import math
import draw

import pandas as pd
df = pd.read_csv("/Users/abalski/Downloads/Lista_transakcji_nr_0221825480_260925.csv", sep=";", encoding="cp1250")
dps = []
for idx, row in df.iterrows():
    if "Waluta" not in row:
        continue
    dims = {"currency": row["Waluta"], "counterparty": row["Dane kontrahenta"], "account": row["Konto"],
            "id": row["Nr transakcji"]}
    for k, v in dims.items():
        if type(v) == float and math.isnan(v):
            dims[k] = "nil"
    amount = float(str(row["Kwota transakcji (waluta rachunku)"]).replace(",", "."))
    date = datetime.datetime.strptime(row["Data transakcji"], "%Y-%m-%d")
    timestamp = int(date.timestamp() * 1000)
    if math.isnan(amount):
        continue
    dps.append(models.Datapoint(timestamp, amount, dims))
series = models.DatapointSeries(series = dps)


remote = client.ImpulsesClient("https://frog02-20850.wykr.es")
local_client = client.ImpulsesClient("http://localhost:8000")


remote.delete_metric_name("transactions")
remote.upload_datapoints("transactions", series)
exit()
deltas = remote.fetch_datapoints("transactions")

# series is dps of transaction amounts (deltas), real acc is the prefix sum of series
acc = impulse_ops.prefix_op(deltas, sum)
expenses = deltas.filter(lambda datapoint: datapoint.value < 0)
income = deltas.filter(lambda datapoint: datapoint.value >= 0)

expenses_30d = impulse_ops.sliding_window(expenses, 30, sum)
expenses_30d_neg = expenses_30d.map(lambda dp: models.Datapoint(dp.timestamp, -dp.value))
income_30d = impulse_ops.sliding_window(income, 30, sum)

delta_30d = impulse_ops.sliding_window(deltas, 30, sum)

def safe_stdev(lst):
    return 0 if len(lst) <= 1 else statistics.stdev(lst)
expense_volatility_30d = impulse_ops.sliding_window(expenses, 30, safe_stdev)
def savings_rate(vals):
    income_sum = sum(v for v in vals if v > 0)
    expense_sum = sum(-v for v in vals if v < 0)
    if income_sum + expense_sum == 0:
        return 0
    return (income_sum - expense_sum) / (income_sum + expense_sum)
savings_rate_30d = impulse_ops.sliding_window(deltas, 30, savings_rate)

expenses_year_avg = impulse_ops.sliding_window(expenses, 365, sum, False).map(
    lambda dp: models.Datapoint(dp.timestamp, -dp.value / 365)
)
monthly_expenses_year_avg = expenses_year_avg.map(lambda dp: models.Datapoint(dp.timestamp, 30.5 * dp.value))

def safe_div(lst):
    if lst[1] < 0.1:
        return 0
    return operator.truediv(*lst)
runway = impulse_ops.compose_impulses([acc, expenses_year_avg], safe_div)\
    .filter(lambda dp: dp.timestamp > datetime.date(2023, 1, 1).toordinal())

def aggregate_buckets(impulse: models.DatapointSeries, bucket_days: int):
    buckets = collections.defaultdict(float)
    
    for dp in impulse:
        bucket_idx = dp.timestamp // bucket_days
        # timestamp = end of bucket
        bucket_ts = (bucket_idx + 1) * bucket_days
        buckets[bucket_ts] += dp.value

    result = [models.Datapoint(ts, val) for ts, val in sorted(buckets.items())]
    return models.DatapointSeries(result, impulse.get_init_val())

expenses_30d_bucket = aggregate_buckets(expenses, 30).map(lambda dp: models.Datapoint(dp.timestamp + 10, -dp.value))\
    .filter(lambda dp: dp.timestamp > datetime.date(2023, 1, 1).toordinal())
income_30d_bucket = aggregate_buckets(income, 30)\
    .filter(lambda dp: dp.timestamp > datetime.date(2023, 1, 1).toordinal())

dashboard = draw.Dashboard([[
    draw.Chart("30-Day Rolling Expenses vs Income", {
        "Expenses": expenses_30d_neg,
        "Income": income_30d
    }, y_tick=5000),
    draw.Chart("30 day buckets sum of Expenses vs Income - Bar", {
        "Expenses": expenses_30d_bucket,
        "Income": income_30d_bucket
    }, y_tick=5000, kind="bar"),
    
    draw.Chart("Net Worth\nCalculated as prefix sum of transaction values", {"Net Worth": acc}, y_tick=1000),
    draw.Chart("Safety net in days based on lagging year expenses avg", {
         "Runway": runway,
         "Last year expenses avg": expenses_year_avg,
         "acc": acc
    }, axes=[["Runway"], ["Last year expenses avg", "acc"]]),
    draw.Chart("Events duration", {
        "dur": remote.fetch_datapoints("imp.events.duration")
        }, kind="bar")], [
    
    draw.Chart("30-Day Expense Volatility", {"Std Dev": expense_volatility_30d}),
    
    draw.Chart("30-Day Savings Rate", {"Savings %": savings_rate_30d}),
    draw.Chart("Monthly expenses (last year average)", {"Monthly expenses average over year": monthly_expenses_year_avg}),
    draw.Text("Title", "text\nblah\nblah blah"),
    draw.Chart("Distance in meters, running", {
        "distance": remote.fetch_datapoints("imp.events.custom.distance_meters")
        }, kind="bar")
    ]])

print("drawing..")
dashboard.create_figure().savefig("dash.png", bbox_inches="tight", dpi=150)
