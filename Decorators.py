def decorator(func):
    def wrapper():
        print("Before function runs")
        func()
        print("After function runs")
    return wrapper
@decorator
def greet():
    print("Hello World")
greet()