ep1 = {25145, 23322, 47237, 32311, 23147}
ep2 = {23134, 24132, 23532, 25697, 44890}

ep1.update(ep2)   # combine sets
print("After update:", ep1)

ep1.pop()         # removes random element
print("After pop:", ep1)

ep1.clear()       # empties set
print("After clear:", ep1)