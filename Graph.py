import numpy as np
import matplotlib.pyplot as plt

lam = 2e-6
t = np.linspace(0, 100000, 1000)
R = np.exp(-lam * t)

plt.plot(t, R)
plt.xlabel("Time (hours)")
plt.ylabel("Reliability")
plt.grid(True)
plt.show()
