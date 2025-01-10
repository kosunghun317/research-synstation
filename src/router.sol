// SPDX-License-Identifier: MIT

pragma solidity ^0.8.0;

contract outcomeBuyRouter {
    uint constant PHI_NUM = 16180; // in bps
    uint constant PHI_DEN = 10000; // in bps
    uint constant precision = 100; // in bps

    // This should be called off-chain since it costs too much gas
    // for 10 outcomes and 1% precision, assuming 200k gas per swap, it costs around 20M gas
    // which is too much for on-chain tx but affordable for off-chain calls for most of providers
    // for instance, 550M cap for Alchemy, 10x block limit for Infura
    function quoteBuy(
        uint marketId,
        uint outcomeIndex,
        uint numberOfOutcomes,
        uint amount
    )
        external
        returns (uint path1Amount, uint path2Amount, uint goodMoneyRequired)
    {
        (path1Amount, path2Amount, goodMoneyRequired) = _getBuySplits(
            marketId,
            outcomeIndex,
            numberOfOutcomes,
            amount
        );
    }

    function _getBuySplits(
        uint marketId,
        uint outcomeIndex,
        uint numberOfOutcomes,
        uint amount
    )
        internal
        returns (uint path1Amount, uint path2Amount, uint goodMoneyRequired)
    {
        // find the optimal split between the two paths through golden section search
        uint left = 0;
        uint right = amount;
        uint a = left + ((right - left) * PHI_NUM) / PHI_DEN;
        uint b = right - ((right - left) * PHI_NUM) / PHI_DEN;
        uint f_a = _getGoodMoneyRequired(
            marketId,
            outcomeIndex,
            numberOfOutcomes,
            a,
            true
        ) +
            _getGoodMoneyRequired(
                marketId,
                outcomeIndex,
                numberOfOutcomes,
                amount - a,
                false
            );
        uint f_b = _getGoodMoneyRequired(
            marketId,
            outcomeIndex,
            numberOfOutcomes,
            b,
            true
        ) +
            _getGoodMoneyRequired(
                marketId,
                outcomeIndex,
                numberOfOutcomes,
                amount - b,
                false
            );

        while ((10_000 * right) / left - 10_000 > precision) {
            if (f_a < f_b) {
                right = b; // a costs less than b, so we should move the right bound to b
                b = a; // b becomes a
                f_b = f_a; // reuse the value of f_a
                a = left + ((right - left) * PHI_NUM) / PHI_DEN; // calculate the new a
                f_a =
                    _getGoodMoneyRequired(
                        marketId,
                        outcomeIndex,
                        numberOfOutcomes,
                        a,
                        true
                    ) +
                    _getGoodMoneyRequired(
                        marketId,
                        outcomeIndex,
                        numberOfOutcomes,
                        amount - a,
                        false
                    ); // calculate the new f_a
            } else {
                left = a; // b costs less than a, so we should move the left bound to a
                a = b; // a becomes b
                f_a = f_b; // reuse the value of f_b
                b = right - ((right - left) * PHI_NUM) / PHI_DEN; // calculate the new b
                f_b =
                    _getGoodMoneyRequired(
                        marketId,
                        outcomeIndex,
                        numberOfOutcomes,
                        b,
                        true
                    ) +
                    _getGoodMoneyRequired(
                        marketId,
                        outcomeIndex,
                        numberOfOutcomes,
                        amount - b,
                        false
                    ); // calculate the new f_b
            }
        }

        // we take the average of the two bounds as the optimal split
        path1Amount = (a + b) / 2;
        path2Amount = amount - path1Amount;
        goodMoneyRequired =
            _getGoodMoneyRequired(
                marketId,
                outcomeIndex,
                numberOfOutcomes,
                path1Amount,
                true
            ) +
            _getGoodMoneyRequired(
                marketId,
                outcomeIndex,
                numberOfOutcomes,
                path2Amount,
                false
            );
    }

    function _getGoodMoneyRequired(
        uint marketId,
        uint outcomeIndex,
        uint numberOfOutcomes,
        uint amount,
        bool isPath1
    ) internal returns (uint goodMoneyRequired) {
        // get the amount of good money required to buy the amount of outcome tokens for the given path
        if (isPath1) {
            // 1. buy the outcome token directly from GM <> O_i pool
            goodMoneyRequired = _quoteExactOutputSingle(amount);
        } else {
            // 1. mint every outcome token from GM
            goodMoneyRequired = amount;

            // 2. sell the outcome tokens to GM <> O_j pool for every j != i
            for (uint j = 0; j < numberOfOutcomes; j++) {
                if (j != outcomeIndex) {
                    goodMoneyRequired -= _quoteExactInputSingle(amount);
                }
            }
        }
    }

    function _quoteExactOutputSingle(uint amount) internal returns (uint) {}

    function _quoteExactInputSingle(uint amount) internal returns (uint) {}
}

contract outcomeSellRouter {
    uint constant PHI_NUM = 16180; // in bps
    uint constant PHI_DEN = 10000; // in bps
    uint constant precision = 100; // in bps

    /**
     * @dev Quotes how much Good Money (GM) you receive when selling a certain amount
     *      of outcomeIndex tokens for marketId. Uses GSS to find optimal split
     *      between (1) direct outcome->GM swap and (2) forming full set & burning.
     */
    function quoteSell(
        uint marketId,
        uint outcomeIndex,
        uint numberOfOutcomes,
        uint amount
    )
        external
        returns (uint path1Amount, uint path2Amount, uint goodMoneyReceived)
    {
        (path1Amount, path2Amount, goodMoneyReceived) = _getSellSplits(
            marketId,
            outcomeIndex,
            numberOfOutcomes,
            amount
        );
    }

    function _getSellSplits(
        uint marketId,
        uint outcomeIndex,
        uint numberOfOutcomes,
        uint amount
    )
        internal
        returns (uint path1Amount, uint path2Amount, uint goodMoneyReceived)
    {
        uint left = 0;
        uint right = amount;

        // Golden section points
        uint a = left + ((right - left) * PHI_NUM) / PHI_DEN;
        uint b = right - ((right - left) * PHI_NUM) / PHI_DEN;

        // Evaluate how much GM we get at each point
        uint f_a = _getGoodMoneyReceived(
            marketId,
            outcomeIndex,
            numberOfOutcomes,
            a,
            true
        ) +
            _getGoodMoneyReceived(
                marketId,
                outcomeIndex,
                numberOfOutcomes,
                amount - a,
                false
            );

        uint f_b = _getGoodMoneyReceived(
            marketId,
            outcomeIndex,
            numberOfOutcomes,
            b,
            true
        ) +
            _getGoodMoneyReceived(
                marketId,
                outcomeIndex,
                numberOfOutcomes,
                amount - b,
                false
            );

        // Golden Section Search (maximize revenue)
        while (
            (10_000 * right) / left - 10_000 > precision &&
            left < right &&
            left != 0
        ) {
            if (f_a > f_b) {
                // a is better (gives more GM), move right bound
                right = b;
                b = a;
                f_b = f_a;
                a = left + ((right - left) * PHI_NUM) / PHI_DEN;
                f_a =
                    _getGoodMoneyReceived(
                        marketId,
                        outcomeIndex,
                        numberOfOutcomes,
                        a,
                        true
                    ) +
                    _getGoodMoneyReceived(
                        marketId,
                        outcomeIndex,
                        numberOfOutcomes,
                        amount - a,
                        false
                    );
            } else {
                // b is better, move left bound
                left = a;
                a = b;
                f_a = f_b;
                b = right - ((right - left) * PHI_NUM) / PHI_DEN;
                f_b =
                    _getGoodMoneyReceived(
                        marketId,
                        outcomeIndex,
                        numberOfOutcomes,
                        b,
                        true
                    ) +
                    _getGoodMoneyReceived(
                        marketId,
                        outcomeIndex,
                        numberOfOutcomes,
                        amount - b,
                        false
                    );
            }
        }

        // Take midpoint
        path1Amount = (a + b) / 2;
        path2Amount = amount - path1Amount;
        goodMoneyReceived =
            _getGoodMoneyReceived(
                marketId,
                outcomeIndex,
                numberOfOutcomes,
                path1Amount,
                true
            ) +
            _getGoodMoneyReceived(
                marketId,
                outcomeIndex,
                numberOfOutcomes,
                path2Amount,
                false
            );
    }

    /**
     * @dev Calculates how much GM you receive by selling `amount` of outcome tokens
     *      along one of two conceptual paths:
     *         - If `isPath1` = true => direct swap in O_i->GM pool.
     *         - If `isPath1` = false => combine with other outcomes, then burn.
     * @return goodMoneyReceived The amount of GM tokens you end up receiving.
     */
    function _getGoodMoneyReceived(
        uint marketId,
        uint outcomeIndex,
        uint numberOfOutcomes,
        uint amount,
        bool isPath1
    ) internal returns (uint goodMoneyReceived) {
        if (isPath1) {
            // Path #1: Sell outcome i tokens directly to GM
            goodMoneyReceived = _quoteExactInputSingle(amount);
        } else {
            // Step 1: The "burn" might give you 'amount' GM if you had a full set.
            goodMoneyReceived = amount;

            // Step 2: Subtract the cost of acquiring the other outcomes.
            for (uint j = 0; j < numberOfOutcomes; j++) {
                if (j != outcomeIndex) {
                    // Suppose you need to acquire amount of outcome j
                    // from the i->j or GM->j pool. This is purely illustrative.
                    goodMoneyReceived -= _quoteExactOutputSingle(amount);
                }
            }
        }
    }

    function _quoteExactOutputSingle(uint amount) internal returns (uint) {}

    function _quoteExactInputSingle(uint amount) internal returns (uint) {}
}
