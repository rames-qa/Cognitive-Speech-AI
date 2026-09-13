import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# Parameters
lam = 2e-6                     # Constant failure rate (2x10^-6 failures/hour)
t = np.linspace(0, 100000, 200) # Operating time in hours
R = np.exp(-lam * t)           # Exponential reliability equation

# Setup plot window
fig, ax = plt.subplots(figsize=(6.4, 4.8), dpi=120)
ax.set_xlim(-2000, 102000)
ax.set_ylim(0.81, 1.01)
ax.set_xlabel("Time (hours)", fontsize=10)
ax.set_ylabel("Reliability", fontsize=10)
ax.grid(True)

# Graph elements
line, = ax.plot([], [], color='#1f77b4', linewidth=2, label=r"$R(t) = e^{-\lambda t}$")
point, = ax.plot([], [], 'ro', markersize=6)

def init():
    line.set_data([], [])
    point.set_data([], [])
    return line, point

def update(frame):
    x = t[:frame+1]
    y = R[:frame+1]
    line.set_data(x, y)
    if frame > 0:
        point.set_data([t[frame]], [R[frame]])
    return line, point

ani = animation.FuncAnimation(
    fig, update, frames=len(t), init_func=init, interval=30, blit=True, repeat=True
)

# Export as animated GIF for PowerPoint insertion
ani.save("reliability_animation.gif", writer="pillow", fps=30)
plt.show()