#Strings are immutable
a="!!!Ramesh!! !!!!!!!!!Ramesh"
print(len(a))
print(a.upper())
print(a.lower())
print(a.rstrip("!"))
print(a.rstrip("Ramesh"))
print(a.split(" "))
blogHeading="intoduction  to js"  
print(blogHeading.capitalize())  
str1 = "Welcome to the Console!!!"
print(len(str1))
print(len(str1.center(50)))
print(a.count("Ramesh"))

str1="Welcome to the console!!!"
print(str1.endswith("!!!"))
print(str1.endswith("to",4,10))

str1="He's name is Dan.He is an honest man."
print(str1.find("ishh"))
#print(str1.index("ishh"))
str1="Welcome to the comsole"
print(str1.isalnum())
str1="Welcome"
print(str1.isalpha())
 
str1="Hello World"
print(str1.islower())

str1="We wish you a Merry Christmas\n"
print(str1)
print(str1.isprintable())

str1="       "  #using spacebar
print(str1.isspace())
str2=" "
print(str2.isspace())

str1="World Health Organization"
print(str1.istitle())

str2="To kill a mocking bird"
print(str2.istitle())

str1="python is a interpreted languge"
print(str1.startswith("Python"))

str1="python is a interpreted language"
print(str1.swapcase())

str1="He is name is Dan.Dan is an honest man."
print(str1.title())
