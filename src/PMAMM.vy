# pragma version ^0.4.0
# @license MIT

"""
Automated Market Maker for Prediction Markets
O_i <> GM
Price Range is restricted to (0, 1]
"""

from ethereum.ercs import IERC20
from snekmate.auth import ownable
from snekmate.tokens import erc20

initializes: ownable
initializes: erc20[ownable := ownable]

exports: erc20.__interface__

fee_rate: public(uint256)  # in bps
base_asset: public(address)
quote_asset: public(address)
reserves: public(uint256)  # reserve of each asset should be leq 2**126 - 1
gauge: public(address)  # gauge contract


@deploy
def __init__(
    _base_asset: address,
    _quote_asset: address,
    _reserves: uint256,
    _fee_rate: uint256,
    _gauge: address,
    _recipient: address,
):
    ownable.__init__()
    erc20.__init__("SynStation LP", "SSLP", 18, "SynStation", "1.0.0")
    self.fee_rate = _fee_rate
    self.base_asset = _base_asset
    self.quote_asset = _quote_asset
    self.reserves = _reserves
    self.gauge = _gauge

    reserves: uint256[2] = self._unpack(_reserves)
    x: uint256 = reserves[0]
    y: uint256 = reserves[1]
    L: uint256 = self._get_L(x, y, False)  # round down
    L_fee: uint256 = L * (10000 - self.fee_rate) // 10000

    erc20._mint(ownable.owner, L_fee)
    erc20._mint(_recipient, L - L_fee)

    # pull the assets
    assert extcall IERC20(self.base_asset).transferFrom(
        msg.sender, self, x, default_return_value=True
    ), "Swap: failed to pull base asset"
    assert extcall IERC20(self.quote_asset).transferFrom(
        msg.sender, self, y, default_return_value=True
    ), "Swap: failed to pull quote asset"


@external
def swap(_base_amount: uint256, _is_buy: bool) -> uint256:
    unpacked_reserves: uint256[2] = self._unpack(self.reserves)
    old_x: uint256 = unpacked_reserves[0]
    old_y: uint256 = unpacked_reserves[1]
    L: uint256 = self._get_L(old_x, old_y, False)  # round down
    quote_amount: uint256 = 0

    if _is_buy:
        # get new reserves
        new_x: uint256 = old_x - _base_amount
        new_y: uint256 = L**2 // (new_x + L) + 1  # round up

        # calculate the amount of quote asset to receive
        quote_amount = (new_y - old_y) * 10000 // (10000 - self.fee_rate) + 1

        # update reserves
        self.reserves = self._pack([new_x, new_y])

        # pull the quote asset from the sender
        assert extcall IERC20(self.quote_asset).transferFrom(
            msg.sender, self, quote_amount, default_return_value=True
        ), "Swap: failed to pull quote asset"

        # transfer the fee to gauge
        assert extcall IERC20(self.quote_asset).transfer(
            self.gauge,
            quote_amount - (new_y - old_y),
            default_return_value=True,
        ), "Swap: failed to transfer fee"

        # transfer the base asset to the sender
        assert extcall IERC20(self.base_asset).transfer(
            msg.sender, _base_amount, default_return_value=True
        ), "Swap: failed to transfer base asset"
    else:
        # get new reserves
        new_x: uint256 = old_x + _base_amount
        new_y: uint256 = L**2 // (new_x + L) + 1  # round up

        # calculate the amount of quote asset to transfer
        quote_amount = (old_y - new_y) * (10000 - self.fee_rate) // 10000

        # update reserves
        self.reserves = self._pack([new_x, new_y])

        # pull the base asset from the sender
        assert extcall IERC20(self.base_asset).transferFrom(
            msg.sender, self, _base_amount, default_return_value=True
        ), "Swap: failed to pull base asset"

        # transfer the fee to gauge
        assert extcall IERC20(self.quote_asset).transfer(
            self.gauge,
            (old_y - new_y) - quote_amount,
            default_return_value=True,
        ), "Swap: failed to transfer fee"

        # transfer the quote asset to the sender
        assert extcall IERC20(self.quote_asset).transfer(
            msg.sender, quote_amount, default_return_value=True
        ), "Swap: failed to transfer quote asset"

    return quote_amount


@external
def add_liquidity(_amounts: uint256) -> uint256:
    return empty(uint256)


@external
def remove_liquidity(_amounts: uint256) -> uint256:
    return empty(uint256)


@internal
@pure
def _get_L(_x: uint256, _y: uint256, _round_up: bool) -> uint256:
    """
    (x + L) * y = L**2

    find L via Newton's method

    return value always satisfies followings:
        (x + L) * y >= L**2
        (x + L + 1) * y < (L + 1)**2
    """
    assert _x < 2**126 - 1 and _y < 2**126 - 1, "Reserves: overflow"

    L_prev: uint256 = 0
    L_new: uint256 = _x + _y + 1  # (x + (x + y + 1)) * y < (x + y + 1)**2

    for i: uint256 in range(128):
        L_prev = L_new
        L_new = (L_prev**2 + _x * _y) // (2 * L_prev - _y)
        if L_new >= L_prev:
            break
    if _round_up:
        return L_prev
    else:
        return L_prev + 1


@internal
@pure
def _unpack(_reserves: uint256) -> uint256[2]:
    return [_reserves >> 128, _reserves & (1 << 128 - 1)]


@internal
@pure
def _pack(_reserves: uint256[2]) -> uint256:
    return _reserves[0] << 128 | _reserves[1]
