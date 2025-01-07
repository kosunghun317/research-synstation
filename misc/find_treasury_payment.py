import numpy as np
import matplotlib.pyplot as plt


def get_y_0_y_1(x_0, p_0):
    """
    computes y_0 and y_1 values for the given x_0 and p_0.
    p_0: initial probability estimation of the outcome O_i
    x_0: initial O_i token being depositted to the pool
    y_0: initial USD token being depositted to the pool
    y_1: USD token left in the pool after O_i happened
    """
    assert x_0 > 0
    assert p_0 < 1 and p_0 > 0

    L = x_0 * np.sqrt(p_0) / (1 - np.sqrt(p_0))

    y_0 = L * np.sqrt(p_0)
    y_1 = L

    return (y_0, y_1)


def get_expected_treasury_payment(B, p_array):
    """
    Given payment from proposer and probability distribution of outcomes,
    this function calculates the expectation of leftover fund after settlement,
    and returns the amount that the treasury should pay.
    """
    assert B > 0
    for p in p_array:
        assert p > 0 and p < 1

    # caculate the expected leftover fund after settlement,
    # when the 1 USD is used for minting outcome tokens (i.e, X == 1)
    # this is the maximum amount that the treasury can pay
    expected_fund_share = np.sum([get_y_0_y_1(1, p)[1] * p for p in p_array])

    deployer_share = (
        1 + sum([get_y_0_y_1(1, p)[0] for p in p_array]) - expected_fund_share
    )

    X = B / deployer_share

    return X * expected_fund_share


def get_guaranteed_treasury_payment(B, p_array):
    """
    Given payment from proposer and probability distribution of outcomes,
    this function calculates the minimum leftover fund after settlement,
    and returns the amount that the treasury should pay.
    We assume sum of probabilities is 1.
    """
    assert B > 0
    for p in p_array:
        assert p > 0 and p < 1

    # caculate the guaranteed leftover fund after settlement,
    # when the 1 USD is used for minting outcome tokens (i.e, X == 1)
    # this is the maximum amount that the treasury can pay
    guaranteed_fund_share = np.min([get_y_0_y_1(1, p)[1] for p in p_array])

    deployer_share = (
        1 + sum([get_y_0_y_1(1, p)[0] for p in p_array]) - guaranteed_fund_share
    )

    X = B / deployer_share

    return X * guaranteed_fund_share


def test_uniform_dist(n=2, B=1_000):
    """
    Test the result of the treasury payment calculation
    under uniform distribution of outcomes.
    """
    p_array = [1 / n for _ in range(n)]
    q_array = [1 / n for _ in range(n)]

    print(f"n= {n}")
    print(f"exp: {get_expected_treasury_payment(B, p_array)}")
    print(f"min: {get_guaranteed_treasury_payment(B, q_array)}")


def test_non_uniform_dist(n=2, B=1_000):
    """
    Test the result of the treasury payment calculation
    under non-uniform distribution of outcomes.
    """
    p_array = np.random.rand(n)
    p_array = p_array / np.sum(p_array)

    print(f"{n}-outcomes distribution: {p_array}")
    print(f"exp: {get_expected_treasury_payment(B, p_array)}")
    print(f"min: {get_guaranteed_treasury_payment(B, p_array)}")


def plot_treasury_payment(max_N=10, B=1000):
    """
    Plot the treasury payment for different number of outcomes.
    We assume the probability distribution of outcomes is uniform.
    """
    assert max_N > 1
    assert B > 0

    N = np.arange(2, max_N + 1)
    expected_payment_uniform = []
    expected_payment_nonuniform = []
    guaranteed_payment_nonuniform = []

    for n in N:
        # generate uniform probability distribution
        p_array = [1 / n for _ in range(n)]

        # generate random probability distribution
        q_array = np.random.rand(n)
        q_array = q_array / np.sum(q_array)

        expected_payment_uniform.append(get_expected_treasury_payment(B, p_array))
        expected_payment_nonuniform.append(get_expected_treasury_payment(B, q_array))
        guaranteed_payment_nonuniform.append(
            get_guaranteed_treasury_payment(B, q_array)
        )

    plt.figure(figsize=(8, 6))
    plt.plot(N, expected_payment_uniform, label="In Expectation (Uniform)")
    plt.plot(N, expected_payment_nonuniform, label="In Expectation (Non-uniform)")
    plt.plot(N, guaranteed_payment_nonuniform, label="Guaranteed (Non-uniform)")

    plt.grid(True)
    plt.title("Maximum Possible Treasury Payment Under Profitability Constraints")
    plt.xlabel("Number of Outcomes (N)")
    plt.ylabel("Treasury Payment")
    plt.legend()
    plt.savefig("plots/treasury_payment.png")
    plt.show()


if __name__ == "__main__":
    np.random.seed(1337)
    print("seed: 1337")

    plot_treasury_payment(10, 1000)
