import pandas as pd
import research_analysis as bot


o=[100,101,105,103,101,100,102,104,107,111,112,113]
h=[102,110,106,104,103,103,105,108,112,113,114,115]
l=[ 99,100,102,100, 99, 98,101,103,106,109,110,111]
c=[101,105,103,101,100,102,104,107,111,112,113,114]
v=[100]*12; v[5]=200
d4 = pd.DataFrame({"open_time":pd.date_range("2022-01-01",periods=12,freq="4h"),
                   "open":o,"high":h,"low":l,"close":c,"volume":v})
r4 = bot.compute_indicators(d4)
print([round(x,3) for x in r4["ATR_200"]])
for ob in bot.compute_smc(r4): print(ob)