import numpy as np
import matplotlib.pyplot as plt

lam = 2e-6                     # Failure rate
t = np.linspace(0,100000,1000)

R = np.exp(-lam*t)             # Reliability equation

plt.plot(t,R,linewidth=2)
plt.xlabel("Time (hours)")
plt.ylabel("Reliability")
plt.title("Reliability vs Time")
plt.grid(True)
plt.show()


