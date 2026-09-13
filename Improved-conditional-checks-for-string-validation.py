#Normal Correct Code (No import needed)
str1 = "Guhana"
str2 = "Mrinal"

cond1 = (len(str1) == 6)      # True
cond2 = (str1 == str2)        # False
cond3 = ("a" in str1 and "z" in str2)  # False

print(cond1, cond2, cond3)

#Import built-in functions explicitly
from builtins import len

str1 = "hello"
str2 = "world"

cond1 = (len(str1) == 5)
cond2 = (str1 == str2)
cond3 = ("a" in str1 and "z" in str2)

print(cond1, cond2, cond3)

#Using a module import (not necessary but allowed)
import string  # not used here, just for demonstration

str1 = "abd"
str2 = "adb"

cond1 = (len(str1) == 3)
cond2 = (str1 == str2)
cond3 = ("a" in str1 and "z" in str2)

print(cond1, cond2, cond3)