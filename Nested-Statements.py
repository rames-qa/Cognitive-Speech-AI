a=int(input("Enter your age="))
print("You age is=",a)
#conditional operators
#>,<,>=,<=,==,!=
print(a>18)
print(a<18)
print(a>=18)
print(a<=18)
print(a==18)
print(a!=18)

if(a>18):
    print("You can drive")
    print("Yes")
else:
    print("You cannot drive")
    print("No")
print("Yay!")

#if else conditions
appleprice=210
budget=200
if(appleprice<=budget):
    print("Alexa , add 1kg apple to the cart.")
else:
    print("Alexa , do not add apple to the cart.")

#else if conditions
appleprice=10
budget=200
if(budget-appleprice>50):
    print("Alexa , add 1kg apple to the cart.")
elif(budget-appleprice>70):
    print("Its Okay you can buy")
else:
    print("Alexa , do not add apple to the cart.")

#elif Contions operation 
num= int(input("Enter the value of Num="))
if(num<0):
    print("Number is Negative.")
    print("I an not  happy now")
elif(num==0):
    print("Number is zero.")
elif(num==99):
    print("Number is Special.")
else:
    print("Number is positive.")
    print("I an happy now")

