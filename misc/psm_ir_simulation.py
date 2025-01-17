import numpy as np
import random
from tabulate import tabulate


class PegStabilityModule:
    def __init__(
        self,
        _GM,
        _mintFeeRate,
        _constBurnFeeRate,
        _variableBurnFeeRate,
        _burnFeeRateHalfLife,
    ):
        self.reserve = 0
        self.supply = 0
        self.GM = _GM
        self.mintFeeRate = _mintFeeRate  # in ppm
        self.constBurnFeeRate = _constBurnFeeRate  # in ppm
        self.variableBurnFeeRate = _variableBurnFeeRate  # in ppm
        self.burnFeeRateHalfLife = _burnFeeRateHalfLife  # in seconds
        self.lastRedemptionTimestamp = 0

    def deposit(self, _amount):
        self.reserve += _amount
        self.supply += _amount * (1 - self.mintFeeRate)
        self.GM.mint(_amount * (1 - self.mintFeeRate))

        return _amount * (1 - self.mintFeeRate)  # return the amount of GM minted

    def redeem(self, _amount, _timestamp):
        # update the variable burn fee rate and last redemption timestamp
        self.variableBurnFeeRate = self.variableBurnFeeRate / 2 ** int(
            (_timestamp - self.lastRedemptionTimestamp) / self.burnFeeRateHalfLife
        )  # decay the variable burn fee rate
        self.variableBurnFeeRate += (
            _amount / (2 * self.GM.totalSupply) * 10**6
        )  # update the variable burn fee rate (in ppm)
        self.lastRedemptionTimestamp = _timestamp

        # calculate fee applied
        feeApplied = (
            _amount * (self.constBurnFeeRate + self.variableBurnFeeRate) / 10**6
        )

        # reserve should be greater than or equal to the amount of USDC to be redeemed
        assert self.reserve >= _amount - feeApplied, "Insufficient reserve"

        # update the reserve and supply
        self.reserve -= _amount - feeApplied
        self.supply -= _amount
        self.GM.burn(_amount)

        return _amount - feeApplied  # return the amount of USDC the caller receives

    def quoteRedemption(self, _amount, _timestamp, _price):
        variableBurnFeeRate = self.variableBurnFeeRate / 2 ** int(
            (_timestamp - self.lastRedemptionTimestamp) / self.burnFeeRateHalfLife
        )
        variableBurnFeeRate += _amount / (2 * self.GM.totalSupply) * 10**6

        feeApplied = _amount * (self.constBurnFeeRate + variableBurnFeeRate) / 10**6

        return _amount - feeApplied - _price * _amount  # return the profit


class GoodMoney:
    def __init__(self, _totalSupply, _initialInterestRate, _targetDebtFraction, _kappa):
        self.totalSupply = _totalSupply
        self.interestRate = _initialInterestRate
        self.lastInterestRateUpdateTimestamp = 0
        self.PSM = None
        self.targetDebtFraction = _targetDebtFraction
        self.kappa = _kappa

    def setPSM(self, _PSM):
        self.PSM = _PSM

    def mint(self, amount):
        self.totalSupply += amount

    def burn(self, amount):
        self.totalSupply -= amount

    def updateInterestRate(self, _timestamp):
        """
        IR_{t + \delta t} = IR_t * exp(
            self.kappa * (self.targetDebtFraction - self.PSM.supply / self.totalSupply) * \delta t
        )
        """
        self.interestRate = self.interestRate * np.exp(
            self.kappa
            * (self.targetDebtFraction - self.PSM.supply / self.totalSupply)
            * (_timestamp - self.lastInterestRateUpdateTimestamp)
        )
        self.lastInterestRateUpdateTimestamp = _timestamp


class ConcentratedLiquidityMarketMaker:
    """
    (x + L / sqrt(P_u)) * (y + L * sqrt(P_l)) = L**2
    P_u = 1
    P_l = 0.98
    """

    def __init__(self, _x, _y, P_u, P_l):
        self.x = _x
        self.y = _y
        self.P_u = P_u
        self.P_l = P_l
        self.precision = 1e-9

    def _get_L(self):
        """
        get invariant L through Newton's method
        """
        L_prev = 1 << 128 - 1
        L_new = self.precision

        for _ in range(128):
            f = L_prev**2 - (self.x + L_prev / np.sqrt(self.P_u)) * (
                self.y + L_prev * np.sqrt(self.P_l)
            )
            f_prime = (
                2 * L_prev
                - (self.x + L_prev / np.sqrt(self.P_u)) * np.sqrt(self.P_l)
                - (self.y + L_prev * np.sqrt(self.P_l)) / np.sqrt(self.P_u)
            )
            L_new = L_prev - f / f_prime

            if abs(L_new - L_prev) < self.precision:
                break

        return L_new

    def swap(self, _amount, _quote_to_base):
        """
        _amount: amount of output asset
        _quote_to_base: True if trader sells quote asset to buy base asset, False otherwise

        return: amount of input asset needed
        """
        L = self._get_L()

        if _quote_to_base:
            _amount = np.clip(
                _amount, 0, self.x - self.precision
            )  # u cannot buy more than x

            old_x = self.x
            old_y = self.y
            new_x = old_x - _amount
            new_y = L**2 / (new_x + L / np.sqrt(self.P_u)) - L * np.sqrt(self.P_l)

            self.x = new_x
            self.y = new_y

            return new_y - old_y  # return the amount of quote asset to be paid
        else:
            _amount = np.clip(
                _amount, 0, self.y - self.precision
            )  # u cannot sell more than y

            # return the amount of quote asset the caller receives
            old_x = self.x
            old_y = self.y
            new_y = old_y - _amount
            new_x = L**2 / (new_y + L * np.sqrt(self.P_l)) - L / np.sqrt(self.P_u)

            self.x = new_x
            self.y = new_y

            return new_x - old_x  # return the amount of base asset to be paid

    def quote(self, _amount, _quote_to_base):
        L = self._get_L()

        if _quote_to_base:
            _amount = np.clip(_amount, 0, self.x - self.precision)

            old_x = self.x
            old_y = self.y
            new_x = old_x - _amount
            new_y = L**2 / (new_x + L / np.sqrt(self.P_u)) - L * np.sqrt(self.P_l)

            return new_y - old_y  # return the amount of quote asset to be paid
        else:
            _amount = np.clip(_amount, 0, self.y - self.precision)

            old_x = self.x
            old_y = self.y
            new_y = old_y - _amount
            new_x = L**2 / (new_y + L * np.sqrt(self.P_l)) - L / np.sqrt(self.P_u)

            return new_x - old_x


# each block; yield rate of USDC is determined based on CIR (Cox-Ingersoll-Ross) model
# based on current distribution of GM, the interest rate of GM is updated
# leverage traders' actions are simulated: they buy or sell GM for USDC
# to take advantage of gap between GM interest rate and USDC yield rate (mint & sell GM if P_gm * IR_gm < YR_usdc and vice versa)
# follow the reference (Liquity V2 Report & crvUSD risk analysis report) to determine the leverage traders' actions
# then arbitrageurs' actions are simulated
# they buy or sell GM on DEX pool and PSM to earn immediate profit

# parameters
# GM
iteration = 1000
blockTime = 60  # 1 minute
interval = 60 * 24 * 7 * 4  # 4 weeks
kappa = 0.001  # degree of interest rate update
target_debt_fraction = 0.5  # we want the half of GM to be minted by PSM
initial_supply = 500_000
initial_interest_rate = 0.05
# PSM
mint_fee_rate = 0.01  # 1%
const_burn_fee_rate = 0.005  # 0.5%
variable_burn_fee_rate = 0.005  # 0.5%
burn_fee_rate_half_life = 60 * 60 * 12  # 12 hours
# USDC
usdc_yield_rate = 0.05  # 5% TODO: ranomize this value

# initialize GM and PSM
GM = GoodMoney(
    initial_supply * (1 - target_debt_fraction),
    initial_interest_rate,
    target_debt_fraction,
    kappa,
)
PSM = PegStabilityModule(
    GM,
    mint_fee_rate,
    const_burn_fee_rate,
    variable_burn_fee_rate,
    burn_fee_rate_half_life,
)
GM.setPSM(PSM)
PSM.deposit(initial_supply * target_debt_fraction)
