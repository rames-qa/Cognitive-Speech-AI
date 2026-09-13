x=12  #Global variable
print(x)
def my_function():
    global x
    x=5  #Local variable
    y=4
    print(x+y)
    print(f"The Local x is {x}")
    print("Hello Guhana")
    
my_function()
print(f"The Global x is {x}")