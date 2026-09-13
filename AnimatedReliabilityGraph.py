import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# Parameters
lam = 2e-6                     # Constant failure rate (2x10^-6 failures/hour)
t = np.linspace(0, 100000, 200) # Time range 0 to 100,000 hours
R = np.exp(-lam * t)           # Exponential Reliability equation

# Setup Plot
fig, ax = plt.subplots(figsize=(8, 5))
ax.set_xlim(0, 100000)
ax.set_ylim(0.75, 1.02)
ax.set_xlabel("Time (hours)", fontsize=11, fontweight='bold')
ax.set_ylabel("Reliability R(t)", fontsize=11, fontweight='bold')
ax.set_title("Reliability vs Time (Exponential Decay)", fontsize=13, fontweight='bold')
ax.grid(True, linestyle='--', alpha=0.7)

# Animated Elements
line, = ax.plot([], [], lw=2.5, color='#1f77b4', label="R(t) = exp(-λt)")
point, = ax.plot([], [], 'ro', markersize=6)
status_text = ax.text(0.45, 0.85, '', transform=ax.transAxes, fontsize=10, 
                      bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", edgecolor="gray"))

def init():
    line.set_data([], [])
    point.set_data([], [])
    status_text.set_text('')
    return line, point, status_text

def update(frame):
    x = t[:frame]
    y = R[:frame]
    line.set_data(x, y)
    
    if frame > 0:
        current_t = t[frame - 1]
        current_R = R[frame - 1]
        point.set_data([current_t], [current_R])
        status_text.set_text(f"Time: {current_t:,.0f} hrs\nReliability: {current_R * 100:.2f}%")
        
    return line, point, status_text

ani = animation.FuncAnimation(
    fig, update, frames=len(t), init_func=init, interval=30, blit=True, repeat=True
)

# 1. Save as GIF for PowerPoint Insertion
ani.save("reliability_animation.gif", writer="pillow", fps=30)
print("Saved: reliability_animation.gif")

# 2. Save as Standalone Interactive HTML File
with open("reliability_animation.html", "w") as f:
    f.write(ani.to_jshtml())
print("Saved: reliability_animation.html")

plt.legend(loc="upper right")
plt.tight_layout()
plt.show()