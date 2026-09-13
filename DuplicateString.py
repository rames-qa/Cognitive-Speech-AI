char= "Programming"
duplicates = set([c for c in char if char.count(c) > 1])

print("Duplicate characters=", duplicates)