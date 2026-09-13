l = [1, 4, 3, 6]
print(l)
l.sort(reverse=True)
print(l.count(1))
print(l)
m = l
m[0] = 0   # correct way to update list element
l.insert(1, 899)
m=[900,1000,1100]
k=l+m
print(k)
l.extend(m)
print(l)