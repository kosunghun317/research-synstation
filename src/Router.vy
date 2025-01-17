# pragma version ^0.4.0
# @license MIT

"""
Router for finding optimal path for buying/selling outcome tokens
Use ternary search to find the optimal path


For Buying:
    1. GM => O_i
    2. GM => mint O_j for j in [n] => Swap O_j into GM for j != i

For Selling:
    1. O_i => GM
    2. Swap GM into O_j for j != i => burn O_j for j in [n] => GM
"""

PHI_NUM: constant(uint256) = 16180
PHI_DEN: constant(uint256) = 10000
PRECISION: constant(uint256) = 1  # in bps


@external
@view
def get_quote(
    _marketId: uint256,
    _is_buy: bool,
    _base_amount: uint256,
    _option_index: uint256,
) -> uint256:
    """
    Get quote amount for buying/selling
    """
    # get market info

    # find the optimal split

    # get quote amount
    return empty(uint256)


@internal
@pure
def _get_optimal_split(
    _is_buy: bool,
    _base_amount: uint256,
    _packed_reserves: DynArray[uint256, 32],
    _fee_rate: uint256,
    option_index: uint256,
) -> uint256[2]:
    """
    find the optimal split using golden section search.
    """
    left: uint256 = empty(uint256)
    right: uint256 = empty(uint256)
    a: uint256 = empty(uint256)
    b: uint256 = empty(uint256)
    if _is_buy:
        left = 1
        right = self._unpack(_packed_reserves[option_index])[0]
        a = right - (right - left) * PHI_DEN // PHI_NUM
        b = left + (right - left) * PHI_DEN // PHI_NUM

        f_a: uint256 = self._get_quote_amount_multi(
            _is_buy, _base_amount, a, _fee_rate, option_index, _packed_reserves
        )
        f_b: uint256 = self._get_quote_amount_multi(
            _is_buy, _base_amount, b, _fee_rate, option_index, _packed_reserves
        )

        for i: uint256 in range(
            16
        ):  # 0.618**16 ~= 0.0004 (maximum 0.02% error)
            if a >= b:
                break
            if f_a < f_b:  # a is better; update right boundary
                right = b
                b = a
                a = right - (right - left) * PHI_DEN // PHI_NUM
                f_b = f_a
                f_a = self._get_quote_amount_multi(
                    _is_buy,
                    _base_amount,
                    a,
                    _fee_rate,
                    option_index,
                    _packed_reserves,
                )
            else:  # b is better; update left boundary
                left = a
                a = b
                b = left + (right - left) * PHI_DEN // PHI_NUM
                f_a = f_b
                f_b = self._get_quote_amount_multi(
                    _is_buy,
                    _base_amount,
                    b,
                    _fee_rate,
                    option_index,
                    _packed_reserves,
                )
    else:
        left = _base_amount - self._get_min_reserve(_packed_reserves, True)
        right = _base_amount
        a = right - (right - left) * PHI_DEN // PHI_NUM
        b = left + (right - left) * PHI_DEN // PHI_NUM

        f_a: uint256 = self._get_quote_amount_multi(
            _is_buy, _base_amount, a, _fee_rate, option_index, _packed_reserves
        )
        f_b: uint256 = self._get_quote_amount_multi(
            _is_buy, _base_amount, b, _fee_rate, option_index, _packed_reserves
        )

        for i: uint256 in range(
            16
        ):  # 0.618**16 ~= 0.0004 (maximum 0.02% error)
            if f_a > f_b:  # a is better; update right boundary
                right = b
                b = a
                a = right - (right - left) * PHI_DEN // PHI_NUM
                f_b = f_a
                f_a = self._get_quote_amount_multi(
                    _is_buy,
                    _base_amount,
                    a,
                    _fee_rate,
                    option_index,
                    _packed_reserves,
                )
            else:  # b is better; update left boundary
                left = a
                a = b
                b = left + (right - left) * PHI_DEN // PHI_NUM
                f_a = f_b
                f_b = self._get_quote_amount_multi(
                    _is_buy,
                    _base_amount,
                    b,
                    _fee_rate,
                    option_index,
                    _packed_reserves,
                )
    path1: uint256 = (left + right) // 2
    path2: uint256 = _base_amount - path1

    return [path1, path2]


@internal
@pure
def _get_min_reserve(
    _packed_reserves: DynArray[uint256, 32],
    _is_x: bool,
) -> uint256:
    min_reserve: uint256 = 2**126 - 1

    for packed_reserve: uint256 in _packed_reserves:
        reserves: uint256[2] = self._unpack(packed_reserve)
        if _is_x:
            min_reserve = min(min_reserve, reserves[0])
        else:
            min_reserve = min(min_reserve, reserves[1])
    return min_reserve


@internal
@pure
def _get_quote_amount_multi(
    _is_buy: bool,
    _base_amount: uint256,
    _path1_amount: uint256,
    _fee_rate: uint256,
    _option_index: uint256,
    _packed_reserves: DynArray[uint256, 32],
) -> uint256:
    """
    Calculate quote amount for buying/selling
    """
    return empty(uint256)


@internal
@pure
def _get_quote_amount_single(
    _is_buy: bool,
    _base_amount: uint256,
    _base_reserve: uint256,
    _quote_reserve: uint256,
    _fee_rate: uint256,
) -> uint256:
    """
    Calculate quote amount for buying/selling
    """
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
