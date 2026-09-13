import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# Parameters
lam = 2e-6
t = np.linspace(0, 100000, 200)
R = np.exp(-lam * t)

# Figure setup matching Figure_2 layout
fig, ax = plt.subplots(figsize=(6.4, 4.8), dpi=120)

ax.set_xlim(-2000, 102000)
ax.set_ylim(0.81, 1.01)
ax.set_xlabel("Time (hours)", fontsize=10)
ax.set_ylabel("Reliability", fontsize=10)
ax.grid(True)

line, = ax.plot([], [], color='#1f77b4', linewidth=1.5)

def init():
    line.set_data([], [])
    return line,

def update(frame):
    line.set_data(t[:frame+1], R[:frame+1])
    return line,

ani = animation.FuncAnimation(
    fig, update, frames=len(t), init_func=init, interval=30, blit=True, repeat=True
)

plt.tight_layout()

# Save animation as GIF
ani.save("reliability_animation.gif", writer="pillow", fps=30)
plt.show()