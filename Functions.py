def calculateGmean(a, b):
    mean = (a * b) / (a + b)
    print("Geometric-like mean:", mean)

def isGreater(a, b):
    if a > b:
        print("First number is greater")
    elif a == b:
        print("Both numbers are equal")
    else:
        print("Second number is greater")

# Call functions
a = 9
b = 8
calculateGmean(a, b)
isGreater(a, b)
pass

c = 8
d = 74
gmean2 = (c * d) / (c + d)
print("Second mean:", gmean2)