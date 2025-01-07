import random


def get_L(x, y, for_swap):
    L_prev = 0
    L_new = (1 << 128) - 1
    for i in range(256):
        L_prev = L_new
        L_new = (L_prev**2 + x * y) // (2 * L_prev - y)
        if L_prev == L_new:
            break
    if for_swap:
        return L_new
    else:
        return L_new + 1


def test_get_L(max_bit):
    x = random.randint(1, (1 << max_bit - 1))
    y = random.randint(1, (1 << max_bit - 1))
    L = get_L(x, y, True)
    return (L**2 <= (x + L) * y) and ((L + 1) ** 2 > (x + (L + 1)) * y), x, y


correct = True

print("-" * 20)
print("max_bit = 64")
for _ in range(32):
    result, x, y = test_get_L(64)
    print(result & correct)
    correct &= result

print("-" * 20)
print("max_bit = 96")
for _ in range(32):
    result, x, y = test_get_L(96)
    print(result & correct)
    correct &= result

print("-" * 20)
print("max_bit = 128")
for _ in range(32):
    result, x, y = test_get_L(128)
    print(result & correct)
    correct &= result
