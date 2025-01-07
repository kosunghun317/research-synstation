import numpy as np
import matplotlib.pyplot as plt


# Function to calculate Y(t)
def supply_over_time(M, H, time_range):
    t = np.linspace(0, time_range, 1000)  # Create a time array from 0 to time_range
    Y_t = M * (1 - 2 ** (-t / H))  # Apply the formula
    return t, Y_t


# Function to plot the result
def plot_supply(M, H, time_range):
    t, Y_t = supply_over_time(M, H, time_range)

    plt.figure(figsize=(8, 6))
    plt.plot(t, Y_t, label=f"M = {M/10**6:.2f} million, H = {H} days")
    plt.axhline(
        y=M, color="r", linestyle="--", label="Maximum Emission (M)"
    )  # maximum supply
    # halving lines
    for i in range(1, 5):
        if i == 1:
            order = "st"
        elif i == 2:
            order = "nd"
        elif i == 3:
            order = "rd"
        else:
            order = "th"
        plt.axvline(x=i * H, color="g", linestyle="--", label=f"{i}{order} Halving")

    # grid, title and labels
    plt.grid(True)
    plt.title("Emission over Time")
    plt.xlabel("Time (t)")
    plt.ylabel("Emission (Y(t))")
    plt.legend()

    # save the plot
    plt.savefig("plots/SYN_emission.png")

    # show the plot
    plt.show()


if __name__ == "__main__":
    # 1B Total Supply, Halving every 365 days, 4 years
    M = 1_000_000_000 * 0.5
    H = 180
    time_range = 4 * H

    plot_supply(M, H, time_range)
