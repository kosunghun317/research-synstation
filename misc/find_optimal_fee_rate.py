from research_synstation import amm
import numpy as np
import tabulate


def spectral_market_simulation(
    bid,  # initial bid for proposing new market
    fee_rates,  # fee in basis points
    daily_transaction,  # number of transaction per day. Polymarket: around 200k
    min_size,  # minimum size of trade
    max_size,  # maximum size of trade
    initial_price,  # initial price of underlying asset
    volatility,  # daily volatility
    block_time,  # seconds
    period,  # days
    sigma_level=2,  # confidence level for price range
):
    """
    price follows GBM
    arbitrageur comes every block and try to make profit
    noise trader arrival is Poisson process,
    with size of trade is Uniform(0,100)
    """
    # initialize market
    markets = [amm.BinaryMarket(bid=bid, fee_bps=fee_bps) for fee_bps in fee_rates]
    initial_values = [market.get_value(0.5) for market in markets]

    # generate price of underlying asset
    W = np.random.normal(
        0, volatility * np.sqrt(block_time / 86400), int(period * 86400 / block_time)
    ).cumsum()
    P = initial_price * np.exp(W)

    # fundamental value of UP token
    P_ext = np.clip(
        0.5
        * (
            1 + np.log(P / initial_price) / (volatility * np.sqrt(period) * sigma_level)
        ),
        0,
        1,
    )

    # generate poisson arrival of noise trader
    arrival_rate = daily_transaction / 86400 * block_time
    num_trades = np.random.poisson(arrival_rate * len(P))
    arrival_times = np.sort(np.random.randint(0, len(P), num_trades))

    # generate size of trade
    trade_size = np.random.uniform(min_size, max_size, num_trades)

    # simulate markets
    noise_arrival = 0
    for i in range(len(P)):
        # arbitrageur comes every block
        for market in markets:
            market.arbitrage(P_ext[i])

        # noise trader arrival follows poisson process
        if i in arrival_times:
            for market in markets:
                market.noise_trade(trade_size[noise_arrival])
            noise_arrival += 1

    final_values = [market.get_value(P_ext[-1]) for market in markets]
    earned_noise_fees = [market.total_noise_fee() for market in markets]
    earned_arb_fees = [market.total_arb_fee() for market in markets]
    pnl = [
        final_value - initial_value
        for final_value, initial_value in zip(final_values, initial_values)
    ]

    return pnl, earned_noise_fees, earned_arb_fees


if __name__ == "__main__":
    # testing fee rates: 1, 5, 10, 20, 30, 50, 100 (bps)
    fee_rates = [1, 5, 10, 20, 30, 50, 100]
    pnls_arr = []
    earned_noise_fees_arr = []
    earned_arb_fees_arr = []

    # set parameters
    _bid = 10000
    _daily_transaction = 200
    _min_size = 1
    _max_size = 100
    _initial_price = 4000
    _volatility = 0.01
    _block_time = 2
    _period = 90
    _sigma_level = 3

    # print
    max_price = int(
        _initial_price * np.exp(_volatility * np.sqrt(_period) * _sigma_level)
    )
    min_price = int(
        _initial_price / np.exp(_volatility * np.sqrt(_period) * _sigma_level)
    )
    print(f"Price Range: {min_price} - {max_price}")

    # repeat 50 times
    for i in range(50):
        print(f"\rRunning simulation {i+1}/50 ...", end="")
        pnls, earned_fees, earned_fees_from_arb = spectral_market_simulation(
            bid=_bid,
            fee_rates=fee_rates,
            daily_transaction=_daily_transaction,
            min_size=_min_size,
            max_size=_max_size,
            initial_price=_initial_price,
            volatility=_volatility,
            block_time=_block_time,
            period=_period,
            sigma_level=_sigma_level,
        )
        pnls_arr.append(pnls)
        earned_noise_fees_arr.append(earned_fees)
        earned_arb_fees_arr.append(earned_fees_from_arb)

    # show results (mean & std) using tabulate
    headers = [
        "Fee Rate (bps)",
        "PnL Mean",
        "PnL Std",
        "Noise Fee Mean",
        "Noise Fee Std",
        "Arb Fee Mean",
        "Arb Fee Std",
    ]
    data = []
    for i, fee_rate in enumerate(fee_rates):
        data.append(
            [
                fee_rate,
                np.mean([pnl[i] for pnl in pnls_arr]),
                np.std([pnl[i] for pnl in pnls_arr]),
                np.mean([fee[i] for fee in earned_noise_fees_arr]),
                np.std([fee[i] for fee in earned_noise_fees_arr]),
                np.mean([fee[i] for fee in earned_arb_fees_arr]),
                np.std([fee[i] for fee in earned_arb_fees_arr]),
            ]
        )
    print("\n")
    print(tabulate.tabulate(data, headers=headers, tablefmt="pretty"))
