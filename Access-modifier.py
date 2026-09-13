class Employee:
    def __init__(self):
        self.name = "Ramesh"   # public variable

emp = Employee()
print(emp.name)



#Protected (_variable)
class Employee:
    def __init__(self):
        self._salary = 50000

class Programmer(Employee):
    def show(self):
        print(self._salary)

p = Programmer()
p.show()

#Private (__variable)
class Employee:
    def __init__(self):
        self.__salary = 50000

    def show(self):
        print(self.__salary)

e = Employee()
e.show()
