
# Case 1: Lists
a = [1, 2, 43]
b = [1, 2, 43]

print(a is b)   # False (different memory objects)
print(a == b)   # True  (same values)


# Case 2: String + Integer comparison (wrong mix example)
a1 = 4
b1 = "4"

print(a1 is b1)   # False
print(a1 == b1)   # False (different types)


# Case 3: Small integers (Python optimizes caching)
a2 = 3
b2 = 3

print(a2 is b2)   # True (same memory for small ints)
print(a2 == b2)   # True


# Case 4: None comparison
a3 = None
b3 = None

print(a3 is b3)   # True (None is singleton in Python)
print(a3 == b3)   # True