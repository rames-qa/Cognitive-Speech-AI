class Employee:
    company = "TCS"

    @staticmethod
    def greet():
        print("Welcome to the company")

    def show(self):
        print(f"Employee works in {self.company}")


# Call static method
Employee.greet()

e1 = Employee()
e1.show()