class person:
    name = "Ramesh"
    occupation = "Software Engineer"
    networth = 10
    def info(self):
        print(f"{self.name} is a {self.occupation}")

a = person()
a.name = "RK"
a.occupation = "Software Engineer"
print(a.name, a.occupation)

b = person()
b.name = "Guhana"
b.occupation = "HR"
print(b.name, b.occupation)
a.info()
b.info()