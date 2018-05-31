from config.global_conf import Global
from config.shared_mongo_client import SharedMongoClient
from trader.risk_free_arb_bot import RiskFreeArbBot2
import logging
import numpy as np
from analyzer.analyzer import Analyzer

Global.configure_default_root_logging(log_level=logging.CRITICAL, should_log_to_file=False)

# SharedMongoClient.KORBIT_DB_NAME = "korbit"
SharedMongoClient.COINONE_DB_NAME = "coinone"
SharedMongoClient.GOPAX_DB_NAME = "gopax"
SharedMongoClient.initialize(should_use_localhost_db=True)

start_time = Global.convert_local_datetime_to_epoch("2018.05.28 09:00:00", timezone="kr")
end_time = Global.convert_local_datetime_to_epoch("2018.05.29 09:00:00", timezone="kr")

# FIXME: Adjust balances at RiskFreeArbBot2 before run
# Initial Setting to start
MAX_COIN_TRADING_UNIT = np.arange(start=0.001, stop=0.01, step=float(0.001)).tolist()
MIN_COIN_TRADING_UNIT = 0
MAX_OB_INDEX_NUM = 2
NEW_SPREAD_THRESHOLD = np.arange(start=0, stop=25, step=1).tolist()
REV_SPREAD_THRESHOLD = np.arange(start=0, stop=1, step=1).tolist()
REV_FACTOR = np.arange(start=1, stop=2, step=1).tolist()

# Total Count
total_counts = len(list(MAX_COIN_TRADING_UNIT)) * len(list(NEW_SPREAD_THRESHOLD)) * len(list(
    REV_SPREAD_THRESHOLD)) * len(list(REV_FACTOR))
print("Total Count: %d" % total_counts)

# Loop Through
result = list()
# retrieve data
counter = 0
for max_unit in MAX_COIN_TRADING_UNIT:
    for new_th in NEW_SPREAD_THRESHOLD:
        for rev_th in REV_SPREAD_THRESHOLD:
            for rev_f in REV_FACTOR:
                print("Conducting %d out of %d" % (counter + 1, total_counts))
                bot = RiskFreeArbBot2(target_currency="bch", should_db_logging=False, is_backtesting=True,
                                      is_init_setting_opt=True,
                                      start_time=start_time, end_time=end_time)
                bot.MAX_COIN_TRADING_UNIT = max_unit
                bot.MIN_COIN_TRADING_UNIT = MIN_COIN_TRADING_UNIT
                bot.MAX_OB_INDEX_NUM = MAX_OB_INDEX_NUM
                bot.NEW_SPREAD_THRESHOLD = new_th
                bot.REV_SPREAD_THRESHOLD = rev_th
                bot.REV_FACTOR = rev_f
                bot.run()
                krw_total_balance = bot.total_krw_bal
                result.append([krw_total_balance, max_unit, new_th, rev_th, rev_f])
                counter += 1

# Return Result
opt_result_list = Analyzer.get_opt_initial_setting_list(result)
print("Finished!!")

for result in opt_result_list:
    print("[OPT] KRW_earned: %.4f, Max_Coin_Unit: %.5f, NEW_Threshold: %.3f, REV_Threshold: %.3f, REV_factor: %.2f" % (
        result[0], result[1], result[2], result[3], result[4]))
