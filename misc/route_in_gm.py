import math
from tabulate import tabulate
import random


def div_up(a, b):
    return (a + b - 1) // b


def get_dx(amm, dy):
    # check new_y range
    new_y = amm.y + dy
    assert new_y > 0, "new_y Out of range"

    # get new_x and check range
    L = amm.get_L(amm.x, amm.y, True)
    new_x = max(1, div_up(L**2, new_y) - L)
    assert new_x > 0, "new_x Out of range"

    # return dx
    return new_x - amm.x


def get_dy(amm, dx):
    # check new_x range
    new_x = amm.x + dx
    assert new_x > 0, "new_x Out of range"

    # get new_y and check range
    L = amm.get_L(amm.x, amm.y, True)
    new_y = div_up(L**2, new_x + L)
    assert new_y > 0, "new_y Out of range"

    # return dy
    return new_y - amm.y


class AMM:
    def __init__(self, L, p, fee_bps):
        """
        Invariant Curve: (X + L) * Y = L**2
        """
        assert L > 0
        assert 0 < p and p < 1
        assert fee_bps >= 0

        self.x = max(1, math.isqrt(int(L**2 / p)) - L)
        self.y = max(1, math.isqrt(int(L**2 * p)))
        self.fee_bps = fee_bps

    def get_L(self, x, y, round_up):
        assert x > 0, "x Out of range"
        assert y > 0, "y Out of range"

        L = (math.isqrt(y * y + ((x * y) << 2)) + y) >> 1

        if L * L == (x + L) * y:
            return L
        elif round_up:
            return L + 1
        else:
            return L

    def swap(self, dx, dy):
        assert self.x + dx > 0, "x Out of range"
        assert self.y + dy > 0, "y Out of range"

        old_L = self.get_L(self.x, self.y, True)
        new_L = self.get_L(self.x + dx, self.y + dy, False)
        assert new_L >= old_L, "L"

        self.x += dx
        self.y += dy


def quote_exact_input_single(amm, amount_in, is_buy):
    if is_buy:
        L = amm.get_L(amm.x, amm.y, True)
        dy = max(0, min(L - 1, amount_in))  # clip dy so that new_y is in [1, L)
        dx = get_dx(amm, dy)

        return -dx
    else:
        dx = max(0, amount_in)
        dy = get_dy(amm, dx)

        return -dy


def quote_exact_output_single(amm, amount_out, is_buy):
    if is_buy:
        dx = -amount_out
        dx = max(1 - amm.x, dx)
        dy = get_dy(amm, dx)

        return dy
    else:
        assert amm.y - amount_out > 0, "y Out of range"
        dy = -amount_out
        dx = get_dx(amm, dy)

        return dx


def find_flashloan_limit(amms, i, cash):
    """
    find debt limit D which will be used for buying O_i with amount_in GM

    lhs = amount_in + sum([cash from selling D O_j for j != i])
    rhs = D

    find maximal D such that lhs >= rhs
    """
    left = 0
    right = cash + sum(
        [amms[j].y for j in range(len(amms)) if j != i]
    )  # trivial upper bound

    while left + 1 < right:
        mid = (left + right) // 2

        lhs = cash + sum(
            [
                quote_exact_input_single(amms[j], mid, False)
                for j in range(len(amms))
                if j != i
            ]
        )  # cash after selling O_j for j != i
        rhs = mid  # debt

        if lhs >= rhs:
            left = mid
        else:
            right = mid

    return left


def quote_buy_exact_input_multiple(amms, i, amount_in, amount_flashloan):
    """ """
    cash = amount_in
    amount_out = amount_flashloan
    cash += sum(
        [
            quote_exact_input_single(amms[j], amount_flashloan, False)
            for j in range(len(amms))
            if j != i
        ]
    )  # cash after selling O_j for j != i
    cash -= amount_flashloan  # cash after repaying flashloan debt
    amount_out += quote_exact_input_single(amms[i], cash, True)  # amount of O_i bought

    return amount_out


def find_optimal_flashloan(amms, i, amount_in):
    """
    find optimal amount of flashloan for buying O_i with amount_in GM
    we use ternary search
    """
    left = 0
    right = find_flashloan_limit(amms, i, amount_in)

    while left + 3 <= right:
        mid1 = left + (right - left) // 3
        mid2 = right - (right - left) // 3

        f1 = quote_buy_exact_input_multiple(amms, i, amount_in, mid1)
        f2 = quote_buy_exact_input_multiple(amms, i, amount_in, mid2)

        if f1 >= f2:
            right = mid2
        else:
            left = mid1

    mid = (left + right) // 2
    output = quote_buy_exact_input_multiple(amms, i, amount_in, mid)

    return mid, output


def generate_amms(n):
    L_list = [10**6 * random.randint(1_000, 1_000_000) for _ in range(n)]
    p_list = [0, 10**6]
    for _ in range(n - 1):
        num = random.randint(1, 10**6 - 1)
        while num in p_list:
            num = random.randint(1, 10**6 - 1)
        p_list.append(num)
    p_list.sort()
    p_list = [(p_list[i + 1] - p_list[i]) / 10**6 for i in range(n)]
    fee_bps = random.choice([1, 5, 10, 30, 100])

    return [AMM(L_list[i], p_list[i], fee_bps) for i in range(n)]


def test_quote_exact_input_buy_multiple():
    n = 9
    amms = generate_amms(n)
    # cash is in "GM" units scaled by 10**6 (as per original code)
    cash = 10**6 * random.randint(10**3, 10**6)

    # Prepare headers and collect results for each pool
    headers = [
        "Pool",
        "x",
        "y",
        "Price",
        "Swap @ Price (O_i)",
        "Swap @ Pool (O_i)",
        "Flashloan Swap (O_i)",
    ]
    table_data = []

    for i, amm in enumerate(amms):
        # Compute pool price as defined
        L_val = amm.get_L(amm.x, amm.y, True)
        price = amm.y / (amm.x + L_val)
        # Swap result if using just the price (idealized)
        swap_price = round(cash / price, 6)
        # Swap result using pool's function
        swap_pool = quote_exact_input_single(amm, cash, True) / 10**6
        # Swap result using an optimal flashloan
        flashloan_param, flashloan_swap = find_optimal_flashloan(amms, i, cash)

        # Append the row: note that cash is in GM (scaled by 10**6)
        table_data.append(
            [
                i,
                amm.x,
                amm.y,
                round(price, 6),
                swap_price,
                round(swap_pool, 6),
                round(flashloan_swap / 1e6, 6),
            ]
        )

    print("\nSimulation Results:")
    print(tabulate(table_data, headers=headers, tablefmt="pretty"))


def print_amms(amms, before_swap=True):
    # Prepare headers and collect results for each pool
    headers = [
        "Pool",
        "x",
        "y",
        "Price",
    ]
    table_data = []

    for i, amm in enumerate(amms):
        # Compute pool price as defined
        L_val = amm.get_L(amm.x, amm.y, True)
        price = amm.y / (amm.x + L_val)

        # Append the row: note that cash is in GM (scaled by 10**6)
        table_data.append(
            [
                i,
                amm.x,
                amm.y,
                round(price, 6),
            ]
        )

    table_data.append(
        [
            "Total",
            "NaN",
            "NaN",
            round(
                sum(
                    [(amm.y / (amm.x + amm.get_L(amm.x, amm.y, True))) for amm in amms]
                ),
                6,
            ),
        ]
    )
    before_or_after = "Before" if before_swap else "After"
    print(f"\n Pool Status {before_or_after} Swap:")
    print(tabulate(table_data, headers=headers, tablefmt="pretty"))


def test_swap_exact_input_buy_multiple():
    n = random.randint(2, 16)
    idx = 0  # random.randint(0, n - 1)
    amms = generate_amms(n)
    # cash is in "GM" units scaled by 10**6 (as per original code)
    cash = 10**6 * random.randint(10**3, 10**6)
    cash_before_flashloan_and_sell = cash

    # Print the status before the trade
    print_amms(amms)

    # Find optimal flashloan amount
    optimal_flashloan_amount, quote = find_optimal_flashloan(amms, idx, cash)
    bought = optimal_flashloan_amount

    # Mint & Swap O_j into GM for j != i
    for j in range(n):
        if j != idx:
            cash_received = quote_exact_input_single(
                amms[j], optimal_flashloan_amount, False
            )
            amms[j].swap(optimal_flashloan_amount, -cash_received)
            cash += cash_received

    # Swap GM into O_i
    cash -= optimal_flashloan_amount
    O_idx_received = quote_exact_input_single(amms[idx], cash, True)
    amms[idx].swap(-O_idx_received, cash)
    bought += (
        O_idx_received  # sign should be negative; dx and dy is in perspective of pool
    )

    # Print the status after the trade
    print_amms(amms, False)
    print(f"\ncash before flashloan: {cash_before_flashloan_and_sell/10**6}")
    print(f"cash after flashloan: {cash/10**6}")
    print(f"quote: {quote/10**6}")
    print(f"bought: {bought/10**6}")


if __name__ == "__main__":
    # test_quote_exact_input_buy_multiple()
    test_swap_exact_input_buy_multiple()
