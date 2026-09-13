class Person:

    def __init__(self, n, o):
        print("Hey I am a person")
        self.name = n
        self.occ = o

    def info(self):
        print(f"{self.name} is a {self.occ}")


a = Person("Ramesh", "Developer")
b = Person("Guhana", "HR")
c = Person("Kumar", "Software Engineer")

a.info()
b.info()
c.info()