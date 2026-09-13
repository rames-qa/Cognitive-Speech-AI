marks=[3,5,6,7,"Mrinal",True, 36,2,3,5]
print(marks)
print(type(marks))
print(marks[0])
print(marks[1])
print(marks[2])
print(marks[3])
print(marks[4])
print(marks[5])

print(marks[-3]) #negative index
print(marks[len(marks)-3]) #positive index

print(marks[5-3]) #positive index
print(marks[2]) #positive index
print(marks)
print(marks[1:-1])
print(marks[1:4:2])
lst=[i*i for i in range(10)]
print(lst)
lst=[i*i for i in range(10) if i%2==0]
print(lst)
