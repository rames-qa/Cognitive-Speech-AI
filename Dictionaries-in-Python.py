dict={707:"Mrinal" , 505:"Guhana",808:"Shubam"}
print(dict[505])
info={'name':'Karthik','Age':19,'eligible':True}
print(info)
print(info['name'])
print(info.get('name'))
for key in info.keys():
    print(f"The value corresponding to the key{key} is {info[key]}")
    
    
print(info.items())
for key,value in info.items():
    print(f"The value corresponding to the key{key} is {info[key]}")