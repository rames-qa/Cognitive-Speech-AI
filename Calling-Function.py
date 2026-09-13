def average(*numbers):
    if len(numbers) == 0:
        return 0   # handle empty input

    total = 0
    for i in numbers:
        total = total + i

    return total / len(numbers)


# Calling the function
c = average(5, 6, 7, 1)
print("Average is =", c)


def name(fname, mname="ramesh", lname="whatson"):
    print("Hello" , fname, mname, lname)


# Calling the name function
name("My", "Mrinal", "Guhana")