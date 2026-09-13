# FOR LOOP EXAMPLE
for i in range(12):
    if i == 10:
        break
    print("100 x", i+1, "=", 100 * (i+1))
    print("Skip the iteration")
    continue


# WHILE LOOP EXAMPLE
i = 0
while True:
    print(i)
    i = i + 1
    if i % 100 == 0:
        break