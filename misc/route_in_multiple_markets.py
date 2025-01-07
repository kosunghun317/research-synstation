import numpy as np
from tabulate import tabulate


class AMM:
    def __init__(self, X, p, fee_bps):
        """
        Invariant Curve: (X + L) * Y = L**2
        """
        self.X = X
        self.L = X * np.sqrt(p) / (1 - np.sqrt(p))
        self.Y = self.L * np.sqrt(p)
        self.fee_bps = fee_bps
        self.fee_X = 0
        self.fee_Y = 0
        self.precision = 1e-6

    def buy_X(self, dx):
        dx = np.clip(
            dx, 0, self.X - self.precision
        )  # you cannot buy more than the pool has

        new_X = self.X - dx
        new_Y = self.L**2 / (new_X + self.L)
        fee_accu = (new_Y - self.Y) * self.fee_bps / (10**4 - self.fee_bps)
        dy = new_Y - self.Y + fee_accu

        self.fee_Y += fee_accu
        self.X = new_X
        self.Y = new_Y

        return dy

    def sell_X(self, dx):
        fee_accu = dx * self.fee_bps / 10**4
        new_X = self.X + dx - fee_accu
        new_Y = self.L**2 / (new_X + self.L)
        dy = self.Y - new_Y

        self.fee_X += fee_accu
        self.X = new_X
        self.Y = new_Y

        return dy

    def get_prob(self):
        return self.Y / (self.X + self.L)

    def get_quote(self, dx, is_buy):
        if is_buy:
            dx = np.clip(dx, 0, self.X - self.precision)

            new_X = self.X - dx
            new_Y = self.L**2 / (new_X + self.L)
            fee_accu = (new_Y - self.Y) * self.fee_bps / (10**4 - self.fee_bps)
            dy = new_Y - self.Y + fee_accu
        else:
            fee_accu = dx * self.fee_bps / 10**4
            new_X = self.X + dx - fee_accu
            new_Y = self.L**2 / (new_X + self.L)
            dy = self.Y - new_Y

        return dy  # dy should be always positive


def buy_quote(amms, i, dx, dx_i):
    """
    return the amount of GM required to buy dx amount of O_i

    i: index of outcome token to be bought
    dx: amount of total outcome token to be bought
    dx_i: amount of O_i to be bought at O_i <-> GM pool
    """
    n = len(amms)

    # GM -> O_i
    quote_i = amms[i].get_quote(dx_i, True)

    # GM -> O_j for j in range(n)
    # O_j -> GM for j != i
    quote_j = np.sum([amms[j].get_quote(dx - dx_i, False) for j in range(n) if j != i])

    dy = quote_i + dx - dx_i - quote_j

    return dy


def buy_multiple(amms, i, dx, dx_i):
    """
    buy dx amount of O_i and return the GM spent

    i: index of outcome token to be bought
    dx: amount of total outcome token to be bought
    dx_i: amount of O_i to be bought at O_i <-> GM pool
    """
    n = len(amms)

    # GM -> O_i
    dy_i = amms[i].buy_X(dx_i)

    # GM -> O_j for j in range(n)
    # O_j -> GM for j != i
    dy_j = np.sum([amms[j].sell_X(dx - dx_i) for j in range(n) if j != i])

    dy = dy_i + dx - dx_i - dy_j

    return dy


def sell_quote(amms, i, dx, dx_i):
    """
    return the amount of GM received by selling dx amount of O_i

    i: index of outcome token to be sold
    dx: amount of total outcome token to be sold
    dx_i: amount of O_i to be sold at O_i <-> GM pool
    """
    n = len(amms)

    # O_i -> GM
    quote_i = amms[i].get_quote(dx_i, False)

    # GM -> O_j for j != i
    # O_j -> GM for j in range(n)
    quote_j = np.sum([amms[j].get_quote(dx - dx_i, True) for j in range(n) if j != i])

    dy = quote_i + dx - dx_i - quote_j

    return dy


def sell_multiple(amms, i, dx, dx_i):
    """
    return the amount of GM received by selling dx amount of O_i

    i: index of outcome token to be sold
    dx: amount of total outcome token to be sold
    dx_i: amount of O_i to be sold at O_i <-> GM pool
    """
    n = len(amms)

    # O_i -> GM
    dy_i = amms[i].sell_X(dx_i)

    # GM -> O_j for j != i
    # O_j -> GM for j in range(n)
    dy_j = np.sum([amms[j].buy_X(dx - dx_i) for j in range(n) if j != i])

    dy = dy_i + dx - dx_i - dy_j

    return dy


def find_optimal_split(amms, i, dx, is_buy):
    """
    Find the optimal split of weights for a given trade via ternary search

    return the optimal amount of O_i to be traded at O_i <-> GM pool
    """
    precision = 1e-6

    if is_buy:
        left = precision
        right = min(dx, amms[i].X * (1 - precision))
    else:
        left = max(
            precision,
            dx - min([amms[j].X for j in range(len(amms)) if j != i]) + precision,
        )
        right = dx

    if is_buy:
        while right / left > 1 + precision:
            mid1 = left + (right - left) / 3
            mid2 = right - (right - left) / 3

            f1 = buy_quote(amms, i, dx, mid1)
            f2 = buy_quote(amms, i, dx, mid2)

            if f1 > f2:
                left = mid1
            else:
                right = mid2
    else:
        while right / left > 1 + precision:
            mid1 = left + (right - left) / 3
            mid2 = right - (right - left) / 3

            f1 = sell_quote(amms, i, dx, mid1)
            f2 = sell_quote(amms, i, dx, mid2)

            if f1 < f2:
                left = mid1
            else:
                right = mid2

    return (left + right) / 2


def generate_input(n=0, fee_bps=0, total_dx=0):
    """
    Generate random input for testing: AMMs and trade size
    """
    if n == 0:
        n = np.random.randint(2, 25)
    if fee_bps == 0:
        fee_bps = np.random.choice([1, 5, 10, 30, 100])
    if total_dx == 0:
        total_dx = np.random.randint(1, 100_000) * np.sqrt(n)

    i = n - 1  # np.random.randint(0, n - 1)
    L_array = [10_000 + np.random.randint(0, 100_000) for _ in range(n)]
    p_array = [np.random.randint(1, 100) for _ in range(n)]
    p_sum = sum(p_array)  # * np.random.choice([0.8, 0.9, 1.0, 1.1, 1.2])
    for j in range(n):
        p_array[j] /= p_sum

    amms = [AMM(L_array[i], p_array[i], fee_bps) for i in range(n)]

    return amms, i, total_dx


def test_buy():
    print("-" * 100)
    print("Test Optimal Split for Buying\n")
    amms, i, total_dx = generate_input(32, 0, 0)
    print(f"fee rate: {amms[0].fee_bps} bps\n")

    # Optimal Split
    optimal_dx_i = find_optimal_split(amms, i, total_dx, True)
    data_split = [
        ["Buy on O_i <-> GM", optimal_dx_i],
        ["Mint & Sell on O_j <-> GM", (total_dx - optimal_dx_i)],
    ]
    print("Optimal Split:")
    print(tabulate(data_split, headers=["Path", "Amount"], floatfmt=".0f") + "\n")

    # Before the trade
    data_amm = []
    for idx, amm in enumerate(amms):
        data_amm.append([idx, int(amm.X), int(amm.Y), amm.get_prob()])
    data_amm.append(["Total", "", "", sum([amm.get_prob() for amm in amms])])

    # After the trade
    buy_multiple(amms, i, total_dx, optimal_dx_i)
    for idx, amm in enumerate(amms):
        data_amm[idx].extend([int(amm.X), int(amm.Y), amm.get_prob()])
    data_amm[-1].extend(["", "", sum([amm.get_prob() for amm in amms])])

    # Print the states before and after the trade in one table
    # rows: each index and sum
    # columns: index, X (before), Y (before), P (before), X (after), Y (after), P (after)
    print(
        tabulate(
            data_amm,
            headers=[
                "Index",
                "X (before)",
                "Y (before)",
                "P (before)",
                "X (after)",
                "Y (after)",
                "P (after)",
            ],
            floatfmt=".4f",
        )
        + "\n"
    )


def test_sell():
    print("-" * 100)
    print("Test Optimal Split for Selling\n")
    amms, i, total_dx = generate_input(32, 0, 0)
    print(f"fee rate: {amms[0].fee_bps} bps\n")

    # Optimal Split
    optimal_dx_i = find_optimal_split(amms, i, total_dx, False)
    data_split = [
        ["Sell on O_i <-> GM", optimal_dx_i],
        ["Burn & Buy on O_j <-> GM", (total_dx - optimal_dx_i)],
    ]
    print("Optimal Split:")
    print(tabulate(data_split, headers=["Path", "Amount"], floatfmt=".0f") + "\n")

    # Before the trade
    data_amm = []
    for idx, amm in enumerate(amms):
        data_amm.append([idx, int(amm.X), int(amm.Y), amm.get_prob()])
    data_amm.append(["Total", "", "", sum([amm.get_prob() for amm in amms])])

    # After the trade
    sell_multiple(amms, i, total_dx, optimal_dx_i)
    for idx, amm in enumerate(amms):
        data_amm[idx].extend([int(amm.X), int(amm.Y), amm.get_prob()])
    data_amm[-1].extend(["", "", sum([amm.get_prob() for amm in amms])])

    # Print the states before and after the trade in one table
    # rows: each index and sum
    # columns: index, X (before), Y (before), P (before), X (after), Y (after), P (after)
    print(
        tabulate(
            data_amm,
            headers=[
                "Index",
                "X (before)",
                "Y (before)",
                "P (before)",
                "X (after)",
                "Y (after)",
                "P (after)",
            ],
            floatfmt=".4f",
        )
        + "\n"
    )


if __name__ == "__main__":
    test_buy()
    test_sell()
