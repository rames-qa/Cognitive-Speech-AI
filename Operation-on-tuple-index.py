tuple1 = (0,2,3,4,56,33,23,)
res = tuple1.count(3)
try:
    res = tuple1.index(2,4,5)
except ValueError:
    res = "Element not found in given range"
print('Count of 3 in tuple is =', res)