s1={2,4,6,8}
s2={1,3,5,7}
print(s1.union(s2))
s1.update(s2)
print(s1,s2)



cities1 = {"Bangalore","Chennai","Hydrabad","Mumbai"}
print(cities1)
cities2 = {"Karnataka","Tamilnadu","Telangna","Maharashtra"}
print(cities2)
cities1.intersection_update(cities2)
print(cities1)