# pragma version ^0.4.0
# @license MIT

"""
Automated Market Maker for Prediction Markets
O_i <> GM
Price Range is restricted to (0, 1]
"""

from ethereum.ercs import IERC20

# implements: IERC20

base_asset: public(address)
quote_asset: public(address)
reserves: public(uint256)  # reserve of each asset should be leq 2^127 - 1


@external
@view
def quote_swap(_base_amount: uint256, _is_buy: bool) -> uint256:
    return empty(uint256)


@external
def swap(_base_amount: uint256, _is_buy: bool) -> uint256:
    return empty(uint256)


@external
def add_liquidity(_amounts: uint256) -> uint256:
    return empty(uint256)


@external
def remove_liquidity(_amounts: uint256) -> uint256:
    return empty(uint256)


@internal
@pure
def _get_L(x: uint256, y: uint256, _for_swap: bool) -> uint256:
    """
    (x + L) * y = L**2

    find L via Newton's method
    """
    L_prev: uint256 = 1 << 127 - 1
    L_new: uint256 = 1 << 127 - 1

    for i: uint256 in range(128):
        L_prev = L_new
        L_new = (L_prev**2 + x * y) // (2 * L_prev - y)
        if L_new >= L_prev:
            break
    if _for_swap:
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
