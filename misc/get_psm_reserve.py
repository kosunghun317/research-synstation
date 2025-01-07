import numpy as np
import random
from tabulate import tabulate


class PegStabilityModule:
    def __init__(self, reserve, totalSupply):
        self.reserve = reserve  # USDC in the Peg Stability Module
        self.totalSupply = totalSupply  # GM in circulation
        self.baseFeeRate = 50  # in bps

    def redeem(self, amount):
        fee = amount * self.baseFeeRate / 10000 + amount**2 / (
            self.totalSupply * 2
        )  # feeRate = baseFeeRate + (amount /(totalSupply * 2))
        assert self.reserve >= (amount - fee), "Insufficient reserve"
        self.reserve -= amount - fee
        self.totalSupply -= amount

        return amount - fee

    def quoteRedemption(self, amount, price):
        fee = amount * self.baseFeeRate / 10000 + amount**2 / (self.totalSupply * 2)
        return amount - fee - price * amount

    def deposit(self, amount):
        self.reserve += amount
        self.totalSupply += amount


def get_optimal_redeem_amount(PSM, price):
    """
    find optimal redeem amount to maximize the profit.
    we use ternary search to find the optimal amount.
    """
    precision = 1e-6
    left = precision
    right = PSM.reserve

    if price > 1 - PSM.baseFeeRate / 10000:
        return 0
    while right / left > 1 + precision:
        left_third = left + (right - left) / 3
        right_third = right - (right - left) / 3

        if PSM.quoteRedemption(left_third, price) > PSM.quoteRedemption(
            right_third, price
        ):
            right = right_third
        else:
            left = left_third

    return (left + right) / 2


PSM = PegStabilityModule(250_000, 500_000)
redemption_records = [
    [
        "Iteration",
        "Redeem Amount",
        "Profit",
        "Reserve",
        "Total Supply",
        "Supply Decrease",
        "Depeg",
    ],
    [0, 0, 0, PSM.reserve, PSM.totalSupply, "0%", "0%"],
]

i = 1
while PSM.reserve > 0 and i < 100:
    prev_supply = PSM.totalSupply
    price = (10000 - random.randint(0, 200)) / 10000
    amount = get_optimal_redeem_amount(PSM, price)
    # print(f"{i}-th quote: {price}, redeem amount: {amount}")
    profit = PSM.redeem(amount) - amount * price
    PSM.deposit(
        profit
    )  # deposit the profit back to the PSM to maintain both reserve and total supply

    redemption_records.append(
        [
            i,
            f"{amount:.0f}",
            f"{profit:.0f}",
            f"{PSM.reserve:.0f}",
            f"{PSM.totalSupply:.0f}",
            f"{100 - PSM.totalSupply / prev_supply * 100:.2f}%",
            f"{100*(1 - price):.2f}%",
        ]
    )
    i += 1
# print the redemption records with tabulate
print(tabulate(redemption_records, headers="firstrow", tablefmt="pretty"))
