countries=("India","Spain","Italy","England","Germany")
temp=list(countries)
temp.append("Russia")
temp.pop(3)
temp[2]="Finland"
countries=tuple(temp)
print(countries)


