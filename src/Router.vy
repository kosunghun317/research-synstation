# pragma version ^0.4.0
# @license MIT

"""
Router for finding optimal path for buying/selling outcome tokens
Use ternary search to find the optimal path


For Buying:
    1. GM => O_i
    2. GM => O_j for j in [n] => Swap O_j into GM for j != i

For Selling:
    1. O_i => GM
    2. GM => O_j for j != i => burn O_j for j in [n] => GM
"""
