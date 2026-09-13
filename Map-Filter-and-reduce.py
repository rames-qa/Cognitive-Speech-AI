from functools import reduce
# Function for map
def cube(x):
    return x * x * x
# List
l = [1, 2, 4, 5, 6, 3]
# MAP: cube each item
mapped_result = list(map(cube, l))
print("Map (Cube)=", mapped_result)
# FILTER: even numbers
filtered_result = list(filter(lambda x: x % 2 == 0, l))
print("Filter (Even numbers)=", filtered_result)
# REDUCE: sum of all elements
reduced_result = reduce(lambda x, y: x + y, l)
print("Reduce (Sum)=", reduced_result)