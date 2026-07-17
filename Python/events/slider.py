import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider

# Create a figure and axis
fig, ax = plt.subplots()
plt.subplots_adjust(bottom=0.25)  # Make space for the slider

# Generate data for the plot
x = np.linspace(0, 10, 100)
y = np.sin(x)

ax.plot(x, y)

# Define the initial value of the slider
x_initial = 5

# Create a slider widget
ax_slider = plt.axes([0.25, 0.15, 0.65, 0.03])
slider = Slider(ax_slider, 'Slice', 0, 10, valinit=x_initial)

# Define the update function for the slider
def update(val):
    x = slider.val
    ax.clear()
    ax.plot(x, np.sin(x))
    fig.canvas.draw_idle()

# Register the update function with the slider
slider.on_changed(update)

plt.show()