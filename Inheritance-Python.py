class Employee:
    def __init__(self, name, id):
        self.name = name
        self.id = id

    def showDetails(self):
        print(f"The name of Employee {self.id} is {self.name}")


# Child class inherits Employee
class Programmer(Employee):
    def showLanguage(self):
        print("Language= Java")


# Object of child class
e1 = Programmer("Ramesh", 400)
e1.showDetails()      # inherited method
e1.showLanguage()     # child method