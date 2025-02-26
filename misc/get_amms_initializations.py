import math
from tabulate import tabulate
import random

DECIMAL = 6

class PMAMM:
    """
    Invariant Curve:
    (x + L) * y = L**2
    x, y are strictly positive integers less than 2**126
    """

    def __init__(self, x: int, y: int):
        self.x = max(1, x)
        self.y = max(1, y)
        self.total_supply = self.get_L(self.x, self.y, True)

    def set_by_L_and_p(self, L, p):
        """
        L: unit of liquidity
        p: price
        """
        self.x = max(1, math.isqrt(int(L**2 / p)) - L)
        self.y = max(1, math.isqrt(int(L**2 * p)))

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

    def get_p(self):
        L = self.get_L(self.x, self.y, True)
        return self.y / (self.x + L)

    def swap(self, dx: int, dy: int):
        # compute invariants before and after swap
        L_old = self.get_L(self.x, self.y, True)
        L_new = self.get_L(self.x + dx, self.y + dy, False)

        # check validity of swap
        assert L_old <= L_new, (
            f"Invariant Curve Violated: x: {self.x}, y: {self.y}, dx: {dx}, dy: {dy}"
        )

        # update x and y
        self.x += dx
        self.y += dy

        return True

def generate_amms(cash, probabilities):
    """
    probability should be a integer between 1 and 10**6 - 1 (the unit is ppm)
    """
    assert sum(probabilities) == 10**DECIMAL, "sum of probabilities should be 1"

    probabilities = [p / 10**DECIMAL for p in probabilities]
    O_i_amount = int(
        cash / (1 + sum([math.sqrt(p) / (math.sqrt(1 / p) - 1) for p in probabilities]))
    )
    amms = [
        PMAMM(
            O_i_amount, max(1, int(O_i_amount * math.sqrt(p) / (math.sqrt(1 / p) - 1)))
        )
        for p in probabilities
    ]

    return amms

def generate_amms_random(n, cash):
    """
    This function generates n AMMs with total cost (almost) equal to cash.
    """
    # generate probabilities
    p_list = [0, 10**6]
    for _ in range(n - 1):
        num = random.randint(1, 10**6 - 1)
        while num in p_list:
            num = random.randint(1, 10**6 - 1)
        p_list.append(num)
    p_list.sort()
    p_list = [(p_list[i + 1] - p_list[i]) / 10**6 for i in range(n)]
    p_list.sort(reverse=True)
    O_i_amount = int(
        cash / (1 + sum([math.sqrt(p) / (math.sqrt(1 / p) - 1) for p in p_list]))
    )
    amms = [
        PMAMM(
            O_i_amount, max(1, int(O_i_amount * math.sqrt(p) / (math.sqrt(1 / p) - 1)))
        )
        for p in p_list
    ]

    return amms

def print_amms(amms):
    # Prepare headers and collect results for each pool
    headers = [
        "Pool",
        "x",
        "y",
        "Price",
    ]
    table_data = []

    for i, amm in enumerate(amms):
        # Append the row: note that cash is in GM (scaled by 10**6)
        table_data.append(
            [
                i,
                amm.x / 10**DECIMAL,
                amm.y / 10**DECIMAL,
                round(amm.get_p(), 6),
            ]
        )

    table_data.append(
        [
            "Total",
            "None",
            "None",
            round(
                sum([amm.get_p() for amm in amms]),
                6,
            ),
        ]
    )
    print(tabulate(table_data, headers=headers, tablefmt="pretty"))

if __name__ == "__main__":
    # Test generate_amms
    cash = 1000 * 10**DECIMAL
    probabilities = [400_000, 400_000, 200_000]
    amms = generate_amms(cash, probabilities)
    print("Deterministically Generated AMMs:")
    print_amms(amms)

    # Test generate_amms_random
    amms = generate_amms_random(random.randint(2,16), cash)
    print("Randomly Generated AMMs:")
    print_amms(amms)
