# Higher-order function
def appl(fx, value):
    return fx(value) + 6


# Lambda functions
double = lambda x: x * 2
cube = lambda x: x * x * x
avg = lambda x, y, z: (x + y + z) / 3


# Function calls
print(double(5))
print(cube(5))
print(avg(3, 5, 10))

# Passing lambda into function
print(appl(lambda x: x * x * x, 2))